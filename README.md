# simple-agent

一个通用 agent 内核 + 领域技能 + 对话界面。内核不认识任何领域；领域知识全在 `skills/` 目录里，改领域只加技能目录，不改内核。

内核照 [pi](https://github.com/earendil-works/pi) 的 `packages/agent/src/agent-loop.ts` 用 Python 逐函数移植：轮次预算、工具参数校验、工具异常转错误结果、中止、收束都在。工具只有 pi 的默认四件 `read` / `write` / `edit` / `bash`。

自带三个生物医学技能，用两个一手数据库回答「基因与疾病关联」类问题，并核验答案里每个标识符是不是真被工具返回过：

| 技能 | 做什么 |
|---|---|
| `skills/open-targets-graphql` | Open Targets Platform 的 GraphQL 查询脚本：名称转 id、疾病→靶点、靶点→疾病、一对关联的逐条证据（含 PMID） |
| `skills/pubmed-eutils` | NCBI E-utilities：检索、摘要、文献元数据 |
| `skills/evidence-discipline` | 输出格式与判据；`scripts/verify.py` 拿本轮落盘的原始响应与答案比对，给出引用数、未核验数、覆盖率 |

## 目录

```
agent/            内核：loop、消息、工具、技能发现、提示词、LLM 接入（OpenAI 兼容 SSE）
skills/           领域技能，每个目录一份 SKILL.md + references/ + scripts/
server.py         最小 web 服务：起 agent、把事件按 NDJSON 逐条推给浏览器、会话落盘
web/              Vue 3 + Vite 前端（三栏、流式渲染、右栏轨迹账本）
docs/             架构与实现说明、动效规范、界面走查清单、两份课程报告
```

## 跑起来

需要 Python 3.10+ 与 PyYAML；前端需要 Node 18+。

```bash
pip install pyyaml

# 前端（产物进 web/dist，server.py 直接发它）
cd web && npm install && npm run build && cd ..

# 起服务
./run_server.sh          # http://localhost:8765
```

模型走 OpenAI 兼容网关。默认从 `~/.pi/agent/models.json` 里取 `magpie` 这个 provider，也可以用环境变量直接给：

```bash
export BIOAGENT_BASE_URL=https://your-gateway/v1
export BIOAGENT_API_KEY=sk-...
export BIOAGENT_PROVIDER=magpie        # 换用 models.json 里的别的 provider
python3 server.py
```

`run_server.sh` 用 `PYTHON` 环境变量指定解释器（默认 `python3`）。

## 一次提问发生了什么

1. 模型拿到系统提示词（工具清单 + 技能清单 + cwd），自己决定先读哪份 `SKILL.md`。
2. 用 `bash` 跑技能自带的查询脚本，原始响应落 `.tmp/responses/`。
3. 循环继续，直到拿到足够证据或轮次预算用完。
4. 答案里的每个标识符交给 `skills/evidence-discipline/scripts/verify.py`，与本轮原始响应比对；数字写回答案下方，前端渲染成「引用 N 条」徽章。

证据链是这个项目的主线：让「模型说的」变成「工具真返回过的」，并且可计数。它有边界——台账记的是「工具输出里出现过」，`bash` 里 `echo` 一个 id 同样能进台账，所以它是有效检查，不是密码学证明。

## 两份课程报告

- `docs/report-bio.ipynb`：生物医学方向的报告（作业要求的设计、实现、示例、结果、局限，以及「证据从哪来、工具是否提高可靠性」两问）。
- `docs/report-web.md`：前端方向的报告（三栏布局、流式协议层、渲染性能、样式刻度与动效、响应式断点、可访问性）。

## 说明

作业与课程相关的内容（姓名、学号）随报告一起公开；代码里没有凭据，模型网关地址与 key 从环境变量或本机配置读取。
