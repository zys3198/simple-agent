<script setup>
import { inject, ref } from 'vue';

const props = defineProps({ node: Object });
const openFile = inject('openFile');
const open = ref(false);
const kids = ref([]);
const loaded = ref(false);

async function toggle() {
  open.value = !open.value;
  if (!open.value || loaded.value) return;
  loaded.value = true;
  kids.value = (await (await fetch(`/files?path=${encodeURIComponent(props.node.path)}`)).json()).entries || [];
}
</script>

<template>
  <button class="fnode" type="button" @click="node.dir ? toggle() : openFile(node.path)">
    <span class="n">{{ node.dir ? node.name + '/' : node.name }}</span>
    <span class="size">{{ node.dir ? '' : node.size }}</span>
  </button>
  <div v-if="node.dir" v-show="open" class="fdir">
    <FileNode v-for="e in kids" :key="e.path" :node="e" />
  </div>
</template>
