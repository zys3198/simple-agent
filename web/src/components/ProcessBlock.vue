<script setup>
import { computed } from 'vue';
import { ChevronRight } from 'lucide-vue-next';
import ThinkBlock from './ThinkBlock.vue';

const props = defineProps({ turn: Object });

const label = computed(() => {
  const t = props.turn;
  if (t.phase === 'failed') return '失败';
  if (t.phase === 'done') return `已思考 · ${t.turns} 轮 · ${t.calls} 次工具调用`;
  return t.text ? '生成中…' : 'thinking…';
});
</script>

<template>
  <details class="process" :open="turn.fold" @toggle="turn.fold = $event.target.open">
    <summary>
      <span v-if="turn.phase === 'running'" class="spin"></span>
      <ChevronRight v-else class="chev" :size="14" :stroke-width="2" />
      <span class="label">{{ label }}</span>
    </summary>
    <ThinkBlock :text="turn.reasoning" />
    <div class="steps">
      <div v-if="turn.phase === 'running' && !turn.text" class="step sys thinking">
        <span class="who">thinking…</span>
        <span class="what">正在发请求，等模型开口</span>
      </div>
    </div>
  </details>
</template>
