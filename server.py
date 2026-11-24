"""最小 web 演示界面：会话历史 + 连续对话。

用法：python server.py  → 浏览器打开 http://localhost:8765

每个浏览器会话一个 agent 对象，agent 的 context 跨请求保留，所以能接着上一轮追问。
会话记录（问题、过程事件、答案、核验结果）落盘到 `.tmp/sessions/<id>.json`，
重启进程后历史仍可查看；模型侧的上下文不落盘，重启后旧会话只能看、不能接着追问。

接口：
  GET  /                     页面
  GET  /prompt               默认模型、可选模型、轮次上限、系统提示词、工具与技能清单
  GET  /files?path=          工作目录树（延迟展开，一层一层取）
  GET  /file?path=           单个文本文件内容（超限截断）
  POST /model {model}        切换当前会话使用的模型
  POST /abort                中止当前会话正在跑的回合
  GET  /sessions             会话列表（按最近更新排序）+ 当前会话 id
  POST /sessions             新建空会话并切换过去
  POST /sessions/<id>/select 切换当前会话
  POST /sessions/<id>/rename {title}
  POST /sessions/<id>/delete
  GET  /sessions/<id>/turns  该会话的完整记录（用于回放）
  POST /ask  {question}      NDJSON 流：事件逐条推，最后一条是 final
"""

import asyncio
import json
import mimetypes
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agent import Agent
from agent.config import available_models
from agent.prompts import build_system_prompt
from agent.skills import load_skills

MODEL = "auto/deepseek-v4.1-flash"
MAX_TURNS = 14
SKILLS = load_skills().skills
MODELS = available_models()
ROOT = Path(__file__).parent

# 文件面板只让人看工作目录里的文本，不跟到仓库根，也不进 .git
FILE_DENY = {".git", "__pycache__", "node_modules"}
FILE_MAX_BYTES = 200_000
INDEX = ROOT / "web" / "dist" / "index.html"
DIST = ROOT / "web" / "dist"
STORE = ROOT / ".tmp" / "sessions"
VERIFY = ROOT / "skills" / "evidence-discipline" / "scripts" / "verify.py"

# 客户端只用这几类事件画过程，其余（message_start 等带整条消息的）不入库
KEPT_EVENTS = {
    "turn_start", "request_start", "message_end", "tool_execution_start", "tool_execution_end",
    "loop_stop", "forced_final_answer",
}


@dataclass
class Turn:
    question: str
    answer: str
    turns: int
    calls: int
    verification: dict
    events: list[dict]
    at: float
    reasoning: str = ""


@dataclass
class Session:
    """一条会话：模型侧上下文 + 可回放的记录。"""

    id: str
    title: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)
    model: str = MODEL
    agent: Agent = None
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.agent is None:
            self.agent = Agent(model=self.model, max_turns=MAX_TURNS, force_final_answer=True)
            self.agent.cancelled = self.cancel

    def set_model(self, model: str) -> None:
        """换模型不重开上下文：已发生的对话原样留着，下一轮用新模型。"""
        self.model = model
        self.agent.model = model
        self.save()

    def meta(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "updated": self.updated,
            "count": len(self.turns),
            "q": self.turns[0].question if self.turns else "",
            "model": self.model,
        }

    def path(self) -> Path:
        return STORE / f"{self.id}.json"

    def save(self) -> None:
        STORE.mkdir(parents=True, exist_ok=True)
        body = {"id": self.id, "title": self.title, "created": self.created, "updated": self.updated,
                "model": self.model, "turns": [asdict(t) for t in self.turns]}
        self.path().write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Session":
        body = json.loads(path.read_text(encoding="utf-8"))
        session = cls(id=body["id"], title=body["title"], created=body["created"], updated=body["updated"],
                      model=body.get("model", MODEL))
        session.turns = [Turn(**t) for t in body["turns"]]
        return session

    def add(self, turn: Turn) -> None:
        self.turns.append(turn)
        self.updated = turn.at
        if not self.title:
            title = " ".join(turn.question.split())
            self.title = title[:40] + ("…" if len(title) > 40 else "")
        self.save()


SESSIONS: dict[str, Session] = {}
STORE_LOCK = threading.Lock()


def load_all() -> None:
    if not STORE.is_dir():
        return
    for path in sorted(STORE.glob("*.json")):
        try:
            session = Session.load(path)
        except (json.JSONDecodeError, KeyError, TypeError):
            continue  # 坏文件跳过，不影响其他会话
        SESSIONS[session.id] = session


def new_session() -> Session:
    with STORE_LOCK:
        session = Session(id=uuid.uuid4().hex[:12])
        SESSIONS[session.id] = session
        session.save()
    return session


def brief_events(events: list[dict]) -> list[dict]:
    """只留客户端要画的事件，去掉带整条消息的，控制落盘体积。"""
    kept = []
    for event in events:
        if event.get("type") not in KEPT_EVENTS:
            continue
        kept.append({k: v for k, v in event.items() if k != "message"})
    return kept


def expand_skill_prefix(question: str) -> str:
    """输入框里的 /技能名：把该技能正文摆到问题前面，让模型先读它再作答。"""
    name, _, rest = question.partition(" ")
    if not name.startswith("/") or not rest.strip():
        return question
    skill = next((s for s in SKILLS if s.name == name[1:]), None)
    if skill is None:
        return question
    return f"用技能 {skill.name}（正文：{skill.file_path}）回答下面的问题，先读该技能再动手。\n\n{rest.strip()}"


def verify_citations(answer: str, since: float) -> dict:
    """答案核验交给技能脚本，server 不认任何标识符格式。"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(answer)
        path = fh.name
    try:
        proc = subprocess.run(
            [sys.executable, str(VERIFY), "--answer-file", path, "--since", str(since)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    finally:
        Path(path).unlink(missing_ok=True)


def stream_answer(session: Session, question: str, prompt: str, write) -> None:
    """question 是用户原话（入库与展示），prompt 是展开 /技能 之后真正发给模型的话。"""
    inbox: queue.Queue = queue.Queue()
    done = object()
    events: list[dict] = []
    started = time.time()

    def work() -> None:
        def on_event(ev: dict) -> None:
            events.append(ev)
            inbox.put(("event", ev))

        with session.lock:
            session.cancel.clear()
            try:
                res = asyncio.run(session.agent.ask(prompt, on_event=on_event))
                inbox.put(("result", res))
            except Exception as exc:  # noqa: BLE001 —— 任何崩溃都要让前端看到原因，而不是白屏
                inbox.put(("failure", repr(exc)))
        inbox.put(done)

    threading.Thread(target=work, daemon=True).start()

    while True:
        item = inbox.get()
        if item is done:
            break
        if isinstance(item, tuple) and item[0] == "result":
            res = item[1]
            answer = res.answer
            if session.cancel.is_set() and not answer.strip():
                answer = "已中止。上面是中断前的过程记录，需要完整答案请重新提问。"
            verification = verify_citations(answer, started)
            session.add(
                Turn(
                    question=question,
                    answer=answer,
                    turns=res.turns,
                    calls=len(res.tool_calls),
                    verification=verification,
                    events=brief_events(events),
                    at=time.time(),
                    reasoning="".join(
                        ev["text"] for ev in events if ev.get("type") == "reasoning_delta" and ev.get("text")
                    ),
                )
            )
            write(
                {
                    "type": "final",
                    "answer": answer,
                    "turns": res.turns,
                    "calls": len(res.tool_calls),
                    "verification": verification,
                    "session": session.meta(),
                }
            )
        elif isinstance(item, tuple) and item[0] == "failure":
            write({"type": "failure", "message": item[1]})
        elif isinstance(item, tuple) and item[0] == "event":
            write({"type": "event", "event": item[1]})


def _encode(obj):
    """事件里带消息对象（dataclass），序列化成普通字典。"""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    raise TypeError(f"不可序列化的类型：{type(obj).__name__}")


class Handler(BaseHTTPRequestHandler):
    def _cookie_sid(self) -> str:
        jar = SimpleCookie(self.headers.get("Cookie") or "")
        return jar["sid"].value if "sid" in jar else ""

    def _current(self) -> Session | None:
        return SESSIONS.get(self._cookie_sid())

    def _send_json(self, payload, status: int = 200, cookie: str = "") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", f"sid={cookie}; Path=/; SameSite=Lax")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def _safe_path(self) -> Path | None:
        """只允许工作目录以内的路径，越界一律 None。"""
        raw = parse_qs(urlparse(self.path).query).get("path", [""])[0].lstrip("/")
        target = (ROOT / raw).resolve()
        return target if target == ROOT or ROOT in target.parents else None

    def _files(self) -> None:
        target = self._safe_path()
        if target is None or not target.is_dir():
            self._send_json({"error": "没有这个目录"}, status=404)
            return
        entries = []
        for entry in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
            if entry.name in FILE_DENY or entry.name.startswith("."):
                continue
            entries.append({
                "name": entry.name,
                "path": str(entry.relative_to(ROOT)),
                "dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        self._send_json({"path": "" if target == ROOT else str(target.relative_to(ROOT)), "entries": entries})

    def _file(self) -> None:
        target = self._safe_path()
        if target is None or not target.is_file():
            self._send_json({"error": "没有这个文件"}, status=404)
            return
        if target.stat().st_size > FILE_MAX_BYTES:
            self._send_json({"error": f"文件超过 {FILE_MAX_BYTES // 1000}KB，看不了"}, status=400)
            return
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self._send_json({"error": "不是文本文件"}, status=400)
            return
        self._send_json({"path": str(target.relative_to(ROOT)), "text": text})

    def _session_id(self) -> str:
        """路径第二段：/sessions/<id>/<action>"""
        parts = self.path.strip("/").split("/")
        return parts[1] if len(parts) > 2 else ""

    def _asset(self) -> None:
        """只发 web/dist 里的构建产物，越界与不存在一律 404。"""
        target = (DIST / self.path.lstrip("/")).resolve()
        if DIST.resolve() not in target.parents or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path in ("/", "/index.html"):
            body = INDEX.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/assets/"):
            self._asset()
        elif self.path == "/prompt":
            prototype = Agent(model=MODEL)
            context, _ = prototype._build()
            self._send_json(
                {
                    "model": MODEL,
                    "models": MODELS,
                    "max_turns": MAX_TURNS,
                    "system_prompt": build_system_prompt(),
                    "tools": [{"name": t.name, "description": t.description} for t in context.tools],
                    "skills": [{"name": s.name, "description": s.description} for s in SKILLS],
                }
            )
        elif self.path.startswith("/files"):
            self._files()
        elif self.path.startswith("/file"):
            self._file()
        elif self.path == "/sessions":
            rows = sorted((s.meta() for s in SESSIONS.values()), key=lambda m: m["updated"], reverse=True)
            self._send_json({"sessions": rows, "current": self._cookie_sid()})
        elif self.path.startswith("/sessions/") and self.path.endswith("/turns"):
            session = SESSIONS.get(self._session_id())
            if session is None:
                self._send_json({"error": "没有这个会话"}, status=404)
                return
            self._send_json({"session": session.meta(), "turns": [asdict(t) for t in session.turns]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/sessions":
            session = new_session()
            self._send_json({"session": session.meta()}, cookie=session.id)
            return
        if self.path == "/model":
            session = self._current() or new_session()
            model = str(self._body().get("model", ""))
            if model not in {m["id"] for m in MODELS}:
                self._send_json({"error": f"没有这个模型：{model}"}, status=400)
                return
            session.set_model(model)
            self._send_json({"session": session.meta()}, cookie=session.id)
            return
        if self.path == "/clear":
            session = self._current()
            if session is not None:
                session.agent.reset()
                session.cancel.clear()
            self._send_json({"ok": True})
            return
        if self.path == "/abort":
            session = self._current()
            if session is not None:
                session.cancel.set()
            self._send_json({"ok": True})
            return
        if self.path.startswith("/sessions/"):
            action = self.path.rstrip("/").split("/")[-1]
            session = SESSIONS.get(self._session_id())
            if session is None:
                self._send_json({"error": "没有这个会话"}, status=404)
                return
            if action == "select":
                self._send_json({"session": session.meta()}, cookie=session.id)
            elif action == "rename":
                title = " ".join(str(self._body().get("title", "")).split())[:80]
                if not title:
                    self._send_json({"error": "标题不能为空"}, status=400)
                    return
                session.title = title
                session.save()
                self._send_json({"session": session.meta()})
            elif action == "delete":
                with STORE_LOCK:
                    SESSIONS.pop(session.id, None)
                    session.path().unlink(missing_ok=True)
                self._send_json({"ok": True})
            else:
                self.send_error(404)
            return
        if self.path != "/ask":
            self.send_error(404)
            return

        question = str(self._body().get("question", "")).strip()
        if not question:
            self._send_json({"error": "question required"}, status=400)
            return
        session = self._current() or new_session()
        prompt = expand_skill_prefix(question)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", f"sid={session.id}; Path=/; SameSite=Lax")
        self.end_headers()

        def write(payload: dict) -> None:
            self.wfile.write((json.dumps(payload, ensure_ascii=False, default=_encode) + "\n").encode())

        try:
            stream_answer(session, question, prompt, write)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 用户关掉页面，线程自行结束

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    load_all()
    server = ThreadingHTTPServer(("0.0.0.0", 8765), Handler)
    print(f"Agent demo: http://localhost:8765  ({len(SESSIONS)} 条历史会话)")
    server.serve_forever()
