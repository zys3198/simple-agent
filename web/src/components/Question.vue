<script setup>
import CopyButton from './CopyButton.vue';

defineProps({ question: String });
</script>

<template>
  <div class="q">
    <div class="q-text">{{ question }}</div>
    <div class="msg-meta">
      <span>{{ question.length }} 字</span>
      <CopyButton :text="question" corner />
    </div>
  </div>
</template>
