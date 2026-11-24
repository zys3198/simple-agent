<script setup>
import { onMounted, provide, ref } from 'vue';
import FileNode from './FileNode.vue';

const entries = ref([]);
const preview = ref(null);   // {path, text} 或 {path, error}

async function openFile(path) {
  const res = await fetch(`/file?path=${encodeURIComponent(path)}`);
  const data = await res.json();
  preview.value = res.ok ? { path, text: data.text } : { path, error: data.error || '读不了这个文件' };
}

provide('openFile', openFile);

onMounted(async () => {
  entries.value = (await (await fetch('/files?path=')).json()).entries || [];
});
</script>

<template>
  <div>
    <FileNode v-for="e in entries" :key="e.path" :node="e" />
    <div id="fileview">
      <template v-if="preview">
        <div class="empty-note">{{ preview.path }}</div>
        <pre v-if="preview.text !== undefined">{{ preview.text }}</pre>
        <div v-else class="empty-note">{{ preview.error }}</div>
      </template>
    </div>
  </div>
</template>
