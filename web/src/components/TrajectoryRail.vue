<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { PanelRightOpen, PanelRightClose, ChevronDown } from 'lucide-vue-next';
import { chat } from '../composables/useStream.js';
import { rail, openRail, closeRail } from '../composables/useRail.js';
import RecordCard from './RecordCard.vue';
import FileView from './FileView.vue';
import PromptSheet from './PromptSheet.vue';

const body = ref(null);

function skillOf(args) {
  const path = (args && (args.path || args.command)) || '';
  const m = String(path).match(/skills\/([a-z0-9-]+)\//);
  return m ? m[1] : '';
}

/* 工具卡片上的名字取用户看得懂的参数：文件取末两级，命令取首行 */
function shortTarget(args) {
  if (args.path) return String(args.path).split('/').filter(Boolean).slice(-2).join('/');
  if (args.command) return String(args.command).split('\n')[0].slice(0, 60);
  return '';
}

/* 一条记录一张卡：只画落盘也留着的几类事件，回放与实时同一套 */
function recordsOf(turn) {
  const recs = [{ kind: '用户', tone: 'user', name: turn.question, num: `${(turn.question || '').length} 字`, body: turn.question }];
  const args = {};
  for (const ev of turn.events) {
    if (ev.type === 'request_start') {
      recs.push({
        kind: '上下文',
        tone: 'ctx',
        name: `${ev.message_count} 条消息`,
        num: `${(ev.messages || []).reduce((a, m) => a + m.chars, 0)} 字`,
        body: (ev.messages || []).map((m, i) => `${i + 1}. ${m.role} · ${m.chars} 字\n${m.preview}`).join('\n\n'),
      });
    } else if (ev.type === 'message_end') {
      const s = ev.summary || {};
      const u = s.usage || {};
      recs.push({
        kind: '模型',
        tone: s.tool_calls && s.tool_calls.length ? 'tool' : 'model',
        name: s.tool_calls && s.tool_calls.length ? s.tool_calls.join(', ') : '正文',
        num: `${s.chars ?? 0} 字 · 思考 ${s.reasoning_chars ?? 0} 字${u.prompt_tokens ? ` · ↑${u.prompt_tokens} ↓${u.completion_tokens}` : ''}`,
        body: ev.message ? (ev.message.reasoning || ev.message.text || '') : '',
      });
    } else if (ev.type === 'tool_execution_start') {
      args[ev.tool_call_id] = ev.args || {};
    } else if (ev.type === 'tool_execution_end') {
      const a = args[ev.tool_call_id] || {};
      const skill = skillOf(a);
      recs.push({
        kind: `${ev.tool_name}${skill ? '·技能' : ''}`,
        tone: ev.is_error ? 'err' : skill ? 'skill' : 'tool',
        name: skill || shortTarget(a) || ev.tool_name,
        num: `${ev.content.length} 字 · ${ev.ms ?? 0}ms`,
        body: `参数：${JSON.stringify(a, null, 2)}\n\n${ev.is_error ? '报错' : '返回'}（${ev.content.length} 字）：\n${ev.content}`,
        err: !!ev.is_error,
      });
    } else if (ev.type === 'loop_stop') {
      recs.push({ kind: '停止', tone: 'err', name: ev.reason, num: '', body: '' });
    } else if (ev.type === 'forced_final_answer') {
      recs.push({ kind: '收束', tone: 'ctx', name: '预算用尽，要求不带工具作答', num: '', body: '' });
    }
  }
  if (turn.phase === 'done') {
    recs.push({
      kind: '答案',
      tone: 'model',
      name: `${turn.answer.length} 字`,
      num: `${turn.turns} 轮 · ${turn.calls} 次工具调用`,
      body: turn.answer,
    });
  }
  return recs;
}

const groups = computed(() => chat.turns.map((t, i) => ({
  turn: t,
  title: `第 ${i + 1} 问：${(t.question || '').slice(0, 24)}`,
  recs: recordsOf(t),
})));

/* 新记录进栏时跟到底，翻上去看旧记录时不打扰 */
watch(() => chat.turns.reduce((a, t) => a + t.events.length, 0), async () => {
  await nextTick();
  const el = body.value;
  if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
});
</script>

<template>
  <aside id="rightbar" class="rightbar" :class="{ floating: rail.floating, closed: !rail.open }">
    <div class="strip">
      <button class="stripbtn" type="button" title="展开右栏" aria-label="展开右栏" @click="openRail()">
        <PanelRightOpen :size="16" :stroke-width="1.75" />
      </button>
    </div>
    <div class="tabs" role="tablist">
      <button role="tab" :aria-selected="rail.tab === 'trajectory'" @click="rail.tab = 'trajectory'">轨迹</button>
      <button role="tab" :aria-selected="rail.tab === 'files'" @click="rail.tab = 'files'">文件</button>
      <button class="collapse" type="button" title="收起右栏" aria-label="收起右栏" @click="closeRail()">
        <PanelRightClose :size="16" :stroke-width="1.75" class="ico" />
      </button>
    </div>
    <div ref="body" class="tabbody">
      <div class="pane" v-show="rail.tab === 'trajectory'">
        <PromptSheet />
        <template v-if="groups.length">
          <template v-for="(g, i) in groups" :key="i">
            <button class="turnmark" type="button" :aria-expanded="String(g.turn.railOpen !== false)"
                    @click="g.turn.railOpen = g.turn.railOpen === false">
              <ChevronDown class="ico chev" :size="14" :stroke-width="2" />
              <span>{{ g.title }}</span>
            </button>
            <div class="turngroup" v-show="g.turn.railOpen !== false">
              <RecordCard v-for="(r, j) in g.recs" :key="j" :rec="r" />
            </div>
          </template>
        </template>
        <div v-else class="empty-note">还没有运行记录</div>
      </div>
      <div class="pane" v-show="rail.tab === 'files'">
        <FileView />
      </div>
    </div>
  </aside>
  <div class="backdrop" :class="{ shown: rail.floating && rail.open }" @click="closeRail()"></div>
  <button class="right-open" :class="{ shown: rail.floating && !rail.open }" type="button"
          title="打开右栏" aria-label="打开右栏" @click="openRail()">
    <PanelRightOpen :size="16" :stroke-width="1.75" class="ico" />
  </button>
</template>
