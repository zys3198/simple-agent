<script setup>
import { computed } from 'vue';
import { mdToHtml } from '../lib/markdown.js';
import CopyButton from './CopyButton.vue';

const props = defineProps({ turn: Object });

const html = computed(() => mdToHtml(props.turn.answer || '（没有返回正文）'));
const meta = computed(() => {
  const t = props.turn;
  const parts = [`${t.answer.length} 字`];
  if (t.reasoning) parts.push(`思考 ${t.reasoning.length} 字`);
  if (t.usage.p || t.usage.c) parts.push(`↑${t.usage.p} ↓${t.usage.c}`);
  parts.push(`${t.calls} 次工具调用`);
  return parts;
});
</script>

<template>
  <div class="answer">
    <div v-html="html"></div>
    <div class="msg-meta">
      <span v-for="p in meta" :key="p">{{ p }}</span>
      <CopyButton :text="turn.answer" corner />
    </div>
  </div>
</template>
