/* 一轮问答的状态与 NDJSON 流：聊天区与右栏都从这份 turns 渲染 */
import { reactive } from 'vue';

export const chat = reactive({
  turns: [],
  busy: false,
  gen: 0,        // 换会话就加一，用来重建对话区做一次蒸入
  ctxBase: '',   // 上下文 N 条 · M 字
  ctxRound: '',  // 本轮 ↑p ↓c
});

/* 右栏轨迹只画这几类事件；delta 不进数组，否则每次追字都要重画整栏 */
const KEPT = new Set([
  'turn_start', 'request_start', 'message_end', 'tool_execution_start', 'tool_execution_end',
  'loop_stop', 'forced_final_answer',
]);

function blankTurn(question) {
  return {
    question,
    reasoning: '',
    text: '',
    answer: '',
    verification: null,
    events: [],
    errors: [],          // 工具报错，在聊天区过程块下方露一行
    calls: 0,
    turns: 0,
    usage: { p: 0, c: 0 },
    phase: 'running',    // running | done | failed
    error: '',
    fold: true,          // 过程块展开状态
    railOpen: true,      // 右栏这一问的记录组展开状态
  };
}

export function applyEvent(turn, ev) {
  if (KEPT.has(ev.type)) turn.events.push(ev);
  switch (ev.type) {
    case 'turn_start':
      turn.turns++;
      break;
    case 'reasoning_delta':
      turn.reasoning += ev.text;
      break;
    case 'text_delta':
      turn.text += ev.text;
      break;
    case 'request_start': {
      const chars = (ev.messages || []).reduce((a, m) => a + m.chars, 0);
      chat.ctxBase = `上下文 ${ev.message_count} 条 · ${chars} 字`;
      chat.ctxRound = '';
      break;
    }
    case 'message_end': {
      const u = ev.summary && ev.summary.usage;
      if (u) {
        turn.usage.p += u.prompt_tokens || 0;
        turn.usage.c += u.completion_tokens || 0;
        chat.ctxRound = `本轮 ↑${u.prompt_tokens ?? '-'} ↓${u.completion_tokens ?? '-'}`;
      }
      break;
    }
    case 'tool_execution_start':
      turn.calls++;
      break;
    case 'tool_execution_end':
      if (ev.is_error) turn.errors.push(`${ev.tool_name} 返回错误，已记入右栏轨迹`);
      break;
  }
}

function finish(turn, data) {
  turn.fold = false;   // 完成后收起，需要时点标题展开
  turn.text = '';      // 流式文本已经被带格式的答案取代
  turn.answer = data.answer || '（没有返回正文）';
  turn.verification = data.verification || {};
  turn.phase = 'done';
}

function fail(turn, message) {
  turn.fold = false;
  turn.error = message;
  turn.phase = 'failed';
}

function usageOf(events) {
  const usage = { p: 0, c: 0 };
  for (const ev of events || []) {
    const u = ev.type === 'message_end' && ev.summary && ev.summary.usage;
    if (!u) continue;
    usage.p += u.prompt_tokens || 0;
    usage.c += u.completion_tokens || 0;
  }
  return usage;
}

/* 回放：把落盘的记录装成同一套 turns，聊天区与右栏都走同一份渲染 */
export function replay(rows) {
  chat.turns = (rows || []).map(r => {
    const events = (r.events || []).filter(ev => KEPT.has(ev.type));
    return {
      ...blankTurn(r.question),
      reasoning: r.reasoning || '',
      answer: r.answer,
      verification: r.verification || {},
      events,
      errors: events.filter(ev => ev.type === 'tool_execution_end' && ev.is_error)
        .map(ev => `${ev.tool_name} 返回错误，已记入右栏轨迹`),
      turns: r.turns,
      calls: r.calls,
      usage: usageOf(events),
      phase: 'done',
      fold: false,
    };
  });
  chat.busy = false;
  chat.gen++;
}

/* 返回 final 载荷（含 session meta），调用方据此刷新会话列表 */
export async function ask(question) {
  question = String(question).trim();
  if (!question || chat.busy) return null;
  chat.busy = true;
  chat.turns.push(blankTurn(question));
  const turn = chat.turns[chat.turns.length - 1];   // 取回代理，直接改裸对象不会触发重绘
  let final = null;
  try {
    const res = await fetch('/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        const msg = JSON.parse(line);
        if (msg.type === 'event') applyEvent(turn, msg.event);
        else if (msg.type === 'final') final = msg;
        else if (msg.type === 'failure') fail(turn, msg.message);
      }
    }
    if (final) finish(turn, final);
    else if (turn.phase === 'running') fail(turn, '连接在给出答案前结束。');
  } catch (err) {
    fail(turn, String(err));
  } finally {
    chat.busy = false;
  }
  return final;
}

export async function abort() {
  if (!chat.busy) return;
  await fetch('/abort', { method: 'POST' });
}
