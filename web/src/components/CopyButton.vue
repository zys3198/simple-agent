<script setup>
import { ref } from 'vue';
import { Copy, Check } from 'lucide-vue-next';

const props = defineProps({ text: String, corner: Boolean });
const done = ref(false);
const hint = ref('复制这条消息');
let timer;   // 连点只留一个复位计时，不提前熄灭

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text || '');
    done.value = true;
    clearTimeout(timer);
    timer = setTimeout(() => (done.value = false), 1200);
  } catch (err) {
    hint.value = '浏览器拒绝了剪贴板访问，请手动选中复制';
  }
}
</script>

<template>
  <button class="copy" :class="{ corner }" type="button" :title="hint" :aria-label="hint"
          :data-done="done ? 'true' : null" @click="copy">
    <Check v-if="done" :size="14" :stroke-width="2" />
    <Copy v-else :size="14" :stroke-width="1.75" />
  </button>
</template>
