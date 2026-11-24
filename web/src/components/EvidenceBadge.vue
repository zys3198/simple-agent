<script setup>
import { computed } from 'vue';
import { idInfo, describeId } from '../lib/ids.js';

const props = defineProps({ verification: Object });

const cited = computed(() => (props.verification && props.verification.cited) || []);
const rows = computed(() => {
  const byId = new Map(((props.verification && props.verification.ledger) || []).map(r => [r.identifier, r]));
  return cited.value.map(id => {
    const hit = byId.get(id) || {};
    return {
      id,
      info: idInfo(id),
      title: describeId(id, hit.snippet || '').title,
      sub: describeId(id, hit.snippet || '').sub,
      src: hit.source || '',
    };
  });
});
</script>

<template>
  <div class="badges">
    <details class="badge">
      <summary>引用 {{ cited.length }} 条</summary>
      <template v-if="cited.length">
        <div v-for="r in rows" :key="r.id" class="idrow">
          <div class="idhead">
            <a v-if="r.info.url" class="title" :href="r.info.url" target="_blank" rel="noopener">{{ r.title }}</a>
            <span v-else class="title">{{ r.title }}</span>
            <span class="site">{{ r.info.site }}</span>
          </div>
          <span class="idmeta">{{ [r.id, r.sub].filter(Boolean).join(' · ') }}</span>
          <a v-if="/^https?:/.test(r.src)" class="src" :href="r.src" target="_blank" rel="noopener">工具调用：{{ r.src }}</a>
        </div>
      </template>
      <div v-else class="badge-note">答案里没有可核验的标识符</div>
    </details>
  </div>
</template>
