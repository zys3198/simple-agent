<script setup>
import { ref } from 'vue';

const props = defineProps({ rec: Object });
const open = ref(false);
</script>

<template>
  <div class="rec" :class="['tone-' + (rec.tone || 'model'), { open }]" @click="open = !open">
    <div class="head">
      <span class="kind">{{ rec.kind }}</span>
      <span class="name">{{ rec.name }}</span>
      <span class="num">{{ rec.num }}</span>
    </div>
    <pre>{{ rec.body || '（这条记录没有可展开的内容）' }}</pre>
  </div>
</template>
