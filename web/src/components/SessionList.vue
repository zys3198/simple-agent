<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { MoreHorizontal, Plus } from 'lucide-vue-next';
import {
  state, createSession, selectSession, fetchTurns, renameSession, deleteSession,
} from '../composables/useSessions.js';
import { chat, replay } from '../composables/useStream.js';

const search = ref('');
const menu = ref(null);        // {session, top, left}
const menuTrigger = ref(null); // 菜单关闭后把焦点还给触发它的按钮
const renaming = ref('');      // 正在改名的会话 id
const renameValue = ref('');

const relTime = ts => {
  const d = (Date.now() / 1000 - ts) / 60;
  if (d < 1) return '刚刚';
  if (d < 60) return `${Math.floor(d)} 分钟前`;
  if (d < 60 * 24) return `${Math.floor(d / 60)} 小时前`;
  const t = new Date(ts * 1000);
  return `${t.getMonth() + 1} 月 ${t.getDate()} 日`;
};

const rows = computed(() => {
  const kw = search.value.trim().toLowerCase();
  return state.list.filter(s => !kw
    || (s.title || '新会话').toLowerCase().includes(kw)
    || (s.q || '').toLowerCase().includes(kw));
});

async function pick(id) {
  if (chat.busy) return;
  if (!(await selectSession(id))) return;
  replay(await fetchTurns(id));
}

async function create() {
  if (chat.busy) return;
  await createSession();
  replay([]);
}

function openMenu(event, session) {
  const box = event.currentTarget.getBoundingClientRect();
  menuTrigger.value = event.currentTarget;
  menu.value = { session, top: box.bottom + 4, left: box.left + 8 };
  setTimeout(() => document.addEventListener('click', closeMenu, { once: true }), 0);
}

function closeMenu() {
  menu.value = null;
}

function startRename() {
  const session = menu.value.session;
  closeMenu();
  renaming.value = session.id;
  renameValue.value = session.title || '';
}

/* 输入框随 v-if 挂载时就聚焦并全选 */
function focusRename(el) {
  if (!el) return;
  el.focus();
  el.select();
}

async function commitRename(session) {
  if (renaming.value !== session.id) return;
  renaming.value = '';
  const title = renameValue.value.trim();
  if (!title || title === session.title) return;
  await renameSession(session.id, title);
}

async function remove() {
  const session = menu.value.session;
  closeMenu();
  if (!confirm(`删除会话「${session.title || '新会话'}」？记录会一起删掉。`)) return;
  const wasCurrent = state.current && state.current.id === session.id;
  await deleteSession(session.id);
  if (!wasCurrent) return;
  const first = state.list[0];
  if (first) await pick(first.id);
  else await create();
}

function onEsc(e) {
  if (e.key !== 'Escape') return;
  const wasOpen = !!menu.value;
  closeMenu();
  renaming.value = '';
  if (wasOpen && menuTrigger.value) menuTrigger.value.focus();
}

onMounted(() => document.addEventListener('keydown', onEsc));
onUnmounted(() => document.removeEventListener('keydown', onEsc));
</script>

<template>
  <aside class="sidebar">
    <div class="side-head">
      <div class="brand"><b>Agent</b></div>
      <button class="btn" type="button" @click="create"><Plus :size="15" :stroke-width="1.75" />新建会话</button>
      <input id="search" v-model="search" type="search" placeholder="搜索会话标题或首个问题" aria-label="搜索会话">
    </div>
    <div id="rows" role="list">
      <div v-if="!rows.length" class="row hint">{{ state.list.length ? '没有匹配的会话' : '还没有会话' }}</div>
      <div v-for="s in rows" :key="s.id" class="row" role="listitem" tabindex="0"
           :aria-current="state.current && state.current.id === s.id"
           :data-open="menu && menu.session.id === s.id ? 'true' : null"
           @click="pick(s.id)"
           @keydown.enter.prevent="pick(s.id)"
           @keydown.space.prevent="pick(s.id)">
        <input v-if="renaming === s.id" id="rename" :ref="focusRename" v-model="renameValue"
               aria-label="会话标题"
               @click.stop
               @keydown.enter.prevent="$event.target.blur()"
               @keydown.esc.prevent="renaming = ''"
               @blur="commitRename(s)">
        <template v-else>
          <span class="t">{{ s.title || '新会话' }}</span>
          <span class="m">{{ s.count ? s.count + ' 轮问答 · ' : '' }}{{ relTime(s.updated) }}</span>
        </template>
        <button class="more" type="button" aria-label="会话操作" @click.stop="openMenu($event, s)">
          <MoreHorizontal :size="16" :stroke-width="1.75" class="ico" />
        </button>
      </div>
    </div>
    <div class="side-foot">{{ state.list.length }} 个会话</div>

    <Transition name="pop-down">
      <div v-if="menu" class="menu" :style="{ top: menu.top + 'px', left: menu.left + 'px' }">
        <button type="button" @click="startRename">重命名</button>
        <button type="button" class="danger" @click="remove">删除会话</button>
      </div>
    </Transition>
  </aside>
</template>

<style scoped>
.row.hint { cursor: default; color: var(--muted); }
</style>
