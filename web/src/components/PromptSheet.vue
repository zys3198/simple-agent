<script setup>
import { onMounted } from 'vue';
import { state, loadSpec } from '../composables/useSessions.js';

onMounted(loadSpec);
</script>

<template>
  <details id="spec" class="process">
    <summary>系统提示词与工具清单</summary>
    <div id="speclist" class="steps">
      <pre v-if="state.spec">{{ state.spec.system_prompt }}</pre>
      <div v-for="t in (state.spec ? state.spec.tools : [])" :key="t.name" class="step tool">
        <span class="who">{{ t.name }}</span>
        <span class="what">{{ t.description.split('\n')[0] }}</span>
      </div>
    </div>
  </details>
</template>
