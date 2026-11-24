/* 会话、模型与系统提示词：全站只有这一份状态 */
import { reactive } from 'vue';

export const state = reactive({
  list: [],       // [{id,title,updated,count,q,model}]
  current: null,  // 当前会话的 meta
  spec: null,     // /prompt 的返回
  model: '',
});

export async function refresh() {
  const data = await (await fetch('/sessions')).json();
  state.list = data.sessions;
  if (!state.current && data.current) state.current = data.sessions.find(s => s.id === data.current) || null;
  if (state.current) state.model = state.current.model || state.model;
}

export async function loadSpec() {
  state.spec = state.spec || await (await fetch('/prompt')).json();
  state.model = (state.current && state.current.model) || state.spec.model;
}

export async function createSession() {
  const data = await (await fetch('/sessions', { method: 'POST' })).json();
  state.current = data.session;
  await refresh();
  return state.current;
}

export async function selectSession(id) {
  const res = await fetch(`/sessions/${id}/select`, { method: 'POST' });
  if (!res.ok) { await refresh(); return null; }
  state.current = (await res.json()).session;
  await refresh();
  return state.current;
}

export async function fetchTurns(id) {
  const data = await (await fetch(`/sessions/${id}/turns`)).json();
  return data.turns || [];
}

export async function renameSession(id, title) {
  await fetch(`/sessions/${id}/rename`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }),
  });
  if (state.current && state.current.id === id) state.current.title = title;
  await refresh();
}

export async function deleteSession(id) {
  await fetch(`/sessions/${id}/delete`, { method: 'POST' });
  if (state.current && state.current.id === id) state.current = null;
  await refresh();
}

export async function pickModel(id) {
  const res = await fetch('/model', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: id }),
  });
  if (!res.ok) return;
  state.current = (await res.json()).session;
  state.model = state.current.model;
}

export async function clearContext() {
  await fetch('/clear', { method: 'POST' });
}
