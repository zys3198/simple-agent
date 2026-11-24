/* 右栏开关：宽屏默认收起成 56px 窄条，窄屏（<1080px）改覆盖层 */
import { reactive } from 'vue';

const narrow = window.matchMedia('(max-width: 1080px)');

export const rail = reactive({
  open: false,
  floating: narrow.matches,   // 窄屏恒为 true，收起靠 translateX 滑出
  tab: 'trajectory',
  jump: false,                // 「跳到最新」是否浮出
});

export function openRail(tab) {
  if (tab) rail.tab = tab;
  rail.floating = narrow.matches;
  rail.open = true;
}

export function closeRail() {
  rail.open = false;
}

/* 主区滚到底并收起「跳到最新」；滚动监听会跟着重算 near */
export function scrollToLatest() {
  const el = document.querySelector('main.scroll');
  if (!el) return;
  el.scrollTop = el.scrollHeight;
  rail.jump = false;
}

narrow.addEventListener('change', () => {
  rail.floating = narrow.matches;
  if (narrow.matches) closeRail();
});
