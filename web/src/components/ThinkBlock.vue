<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({ text: String });
const el = ref(null);

watch(() => props.text, () => {
  if (el.value) el.value.scrollTop = el.value.scrollHeight;
});
</script>

<template>
  <div ref="el" class="think">{{ text }}</div>
</template>
