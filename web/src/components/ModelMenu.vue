<script setup>
import { computed } from 'vue';
import { state } from '../composables/useSessions.js';
import { chat } from '../composables/useStream.js';

const emit = defineEmits(['open']);

const short = computed(() => (state.model || '').split('/').slice(1).join('/') || state.model || '模型');
const ctx = computed(() => [chat.ctxBase, chat.ctxRound].filter(Boolean).join(' · '));
</script>

<template>
  <div class="seats">
    <button class="seat" type="button" :title="`当前模型 ${state.model}（点这里切换）`" @click="emit('open')">{{ short }}</button>
    <span class="seat-muted">{{ ctx }}</span>
  </div>
</template>
