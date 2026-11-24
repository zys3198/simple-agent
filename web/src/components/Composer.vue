<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue';
import { ArrowDown } from 'lucide-vue-next';
import { state, refresh, createSession, clearContext, pickModel } from '../composables/useSessions.js';
import { chat, ask, abort, replay } from '../composables/useStream.js';
import { rail, scrollToLatest } from '../composables/useRail.js';
import ModelMenu from './ModelMenu.vue';

const ta = ref(null);
const value = ref('');
const items = ref([]);     // [{label, sub, run}]
const index = ref(0);
const locked = ref(false); // 弹窗（模型/技能）打开后不被输入变化重算

const commands = [
  { name: 'skill', hint: '点名一个技能，先读正文再答' },
  { name: 'clear', hint: '清空本会话的模型上下文（记录保留）' },
  { name: 'new', hint: '新建会话' },
];

function setMenu(list, lock = false) {
  items.value = list;
  index.value = 0;
  locked.value = lock;
}

function closeMenu() {
  items.value = [];
  locked.value = false;
}

function pick(item) {
  if (item && item.run) item.run();
}

function commandMenu(fragment) {
  const hits = commands.filter(c => c.name.startsWith(fragment.toLowerCase()));
  setMenu(hits.map(c => ({
    label: `/${c.name}`,
    sub: c.hint,
    run: () => (c.name === 'skill' ? skillMenu() : c.name === 'clear' ? doClear() : doNew()),
  })));
}

/* 模型清单平铺一行一个：带 auto/ codex/ 前缀，同一个后端再排名字 */
function modelMenu() {
  value.value = '';
  grow();
  const models = (state.spec && state.spec.models) || [];
  setMenu(models.map(m => ({
    label: m.id,
    sub: `${m.id === state.model ? '当前 · ' : ''}${m.name}`,
    run: () => doPickModel(m.id),
  })), true);
}

function skillMenu() {
  value.value = '';
  grow();
  const skills = (state.spec && state.spec.skills) || [];
  setMenu(skills.map(s => ({
    label: `/${s.name}`,
    sub: s.description,
    run: () => {
      value.value = `/${s.name} `;
      closeMenu();
      grow();
      focus();
    },
  })), true);
}

async function fileMenu(fragment) {
  const slash = fragment.lastIndexOf('/');
  const dir = slash >= 0 ? fragment.slice(0, slash) : '';
  const prefix = slash >= 0 ? fragment.slice(slash + 1) : fragment;
  let data;
  try {
    data = await (await fetch(`/files?path=${encodeURIComponent(dir)}`)).json();
  } catch (err) { return closeMenu(); }
  const hits = (data.entries || []).filter(e => e.name.toLowerCase().startsWith(prefix.toLowerCase()));
  setMenu(hits.slice(0, 40).map(e => ({
    label: e.dir ? `${e.name}/` : e.name,
    sub: e.dir ? '目录' : `${e.size} 字节`,
    run: () => {
      if (e.dir) {
        insertReference(e.path + '/', fragment);
        fileMenu(e.path + '/');
        locked.value = true;
      } else {
        insertReference(e.path, fragment);
      }
    },
  })));
}

function insertReference(path, fragment) {
  value.value = value.value.replace(new RegExp(`@${fragment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`), `@${path} `);
  grow();
  focus();
}

function renderMenu() {
  if (locked.value) return;
  const v = value.value;
  let m;
  if ((m = v.match(/^\/([a-z0-9-]*)$/i))) return commandMenu(m[1]);
  if ((m = v.match(/(?:^|\s)@([^\s]*)$/))) return fileMenu(m[1]);
  closeMenu();
}

async function doPickModel(id) {
  await pickModel(id);
  closeMenu();
  focus();
}

async function doClear() {
  closeMenu();
  await clearContext();
  chat.ctxBase = '上下文已清空';
  chat.ctxRound = '';
}

async function doNew() {
  if (chat.busy) return;
  closeMenu();
  await createSession();
  replay([]);
}

function focus() { if (ta.value) ta.value.focus(); }

function grow() {
  const el = ta.value;
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
}

function onInput(e) {
  value.value = e.target.value;
  grow();
  renderMenu();
}

function onBlur() {
  // 点座位/技能弹窗也会先触发 blur，锁住时不能在 120ms 后把弹窗关掉
  setTimeout(() => { if (!locked.value) closeMenu(); }, 120);
}

/* 菜单开着时方向键与 Enter 归菜单，其余归输入框 */
function menuKey(e) {
  if (!items.value.length) return false;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    index.value = (index.value + (e.key === 'ArrowDown' ? 1 : items.value.length - 1)) % items.value.length;
    return true;
  }
  if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
    e.preventDefault();
    pick(items.value[index.value]);
    return true;
  }
  if (e.key === 'Escape') { e.preventDefault(); closeMenu(); return true; }
  return false;
}

function onKeydown(e) {
  if (menuKey(e)) return;
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
}

async function send() {
  const text = value.value.trim();
  if (!text || chat.busy) return;
  value.value = '';
  grow();
  closeMenu();
  const final = await ask(text);
  if (final) {
    if (final.session) state.current = final.session;
    await refresh();
  }
  await nextTick();
  focus();
}

function onEsc(e) {
  if (e.key === 'Escape' && chat.busy) { e.preventDefault(); abort(); }
}

onMounted(() => {
  document.addEventListener('keydown', onEsc);
  focus();
});
onUnmounted(() => document.removeEventListener('keydown', onEsc));
</script>

<template>
  <footer>
    <div class="composer-wrap">
      <Transition name="pop">
        <div v-if="items.length" class="menu-box" role="listbox" aria-label="命令与引用">
          <button v-for="(it, i) in items" :key="i" class="mitem" type="button" role="option"
                  :aria-selected="i === index" @mousedown.prevent="pick(it)">
            <b>{{ it.label }}</b>
            <small>{{ it.sub }}</small>
          </button>
        </div>
      </Transition>
      <div class="composer">
        <textarea id="q" ref="ta" rows="1" :value="value"
                  placeholder="问一个问题，/ 命令、@ 文件" aria-label="问题"
                  @input="onInput" @keydown="onKeydown" @blur="onBlur"></textarea>
        <button v-if="chat.busy" class="btn" type="button" title="中止当前回合（Esc）" @click="abort()">停止</button>
        <button class="btn primary" type="button" @click="send">发送问题</button>
      </div>
      <ModelMenu @open="modelMenu" />
      <button class="jump" :class="{ shown: rail.jump }" type="button" @click="scrollToLatest()">
        <ArrowDown :size="14" :stroke-width="1.75" /> 跳到最新
      </button>
    </div>
  </footer>
</template>
