<script setup>
import { nextTick, onMounted, ref, watch } from 'vue';
import { chat } from '../composables/useStream.js';
import { rail } from '../composables/useRail.js';
import TurnBlock from './TurnBlock.vue';

const scroll = ref(null);
let near = true;   // 上翻过一屏后不再自动跟到底

function updateJump() {
  const el = scroll.value;
  if (!el) return;
  rail.jump = chat.turns.length > 0
    && el.scrollHeight - el.scrollTop - el.clientHeight >= el.clientHeight;
}

function follow() {
  const el = scroll.value;
  if (!el) return;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
  updateJump();
}

function onScroll() {
  const el = scroll.value;
  near = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
  updateJump();
}

function toLatest() {
  const el = scroll.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
  near = true;
  updateJump();
}

/* 换会话（turns 整体替换）直接落到底部；流式追字只在贴底时跟随 */
watch(() => chat.turns, async () => {
  await nextTick();
  toLatest();
});
watch(chat.turns, () => {
  if (near) nextTick(follow);
}, { deep: true });

onMounted(toLatest);
</script>

<template>
  <main ref="scroll" class="scroll" @scroll.passive="onScroll">
    <div class="wrap" :key="chat.gen">
      <TurnBlock v-for="(t, i) in chat.turns" :key="i" :turn="t" />
    </div>
  </main>
</template>
