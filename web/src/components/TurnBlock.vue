<script setup>
import Question from './Question.vue';
import ProcessBlock from './ProcessBlock.vue';
import Answer from './Answer.vue';
import EvidenceBadge from './EvidenceBadge.vue';

defineProps({ turn: Object });
</script>

<template>
  <section class="turn">
    <Question :question="turn.question" />
    <div class="a">
      <ProcessBlock :turn="turn" />
      <div class="errs">
        <div v-for="(e, i) in turn.errors" :key="i" class="tool-err">{{ e }}</div>
      </div>
      <div v-if="turn.text" class="stream">{{ turn.text }}</div>
      <div v-if="turn.phase === 'failed'" class="alert" role="alert">
        <b>这一轮没有结果</b>
        <div>{{ turn.error }}</div>
      </div>
      <template v-if="turn.phase === 'done'">
        <Answer :turn="turn" />
        <EvidenceBadge :verification="turn.verification" />
      </template>
    </div>
  </section>
</template>
