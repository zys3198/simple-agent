<script setup>
import { onMounted } from 'vue';
import { state, refresh, loadSpec, selectSession, fetchTurns } from './composables/useSessions.js';
import { replay } from './composables/useStream.js';
import SessionList from './components/SessionList.vue';
import Conversation from './components/Conversation.vue';
import Composer from './components/Composer.vue';
import TrajectoryRail from './components/TrajectoryRail.vue';

onMounted(async () => {
  await refresh();
  await loadSpec();
  if (state.current) {
    replay(await fetchTurns(state.current.id));
  } else if (state.list.length) {
    const first = state.list[0];
    await selectSession(first.id);
    replay(await fetchTurns(first.id));
  }
});
</script>

<template>
  <SessionList />
  <section class="main">
    <header class="topbar">
      <h1 id="title">{{ (state.current && state.current.title) || '新会话' }}</h1>
    </header>
    <Conversation />
    <Composer />
  </section>
  <TrajectoryRail />
</template>
