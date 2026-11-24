# 前端重构规格：Vite + Vue 3 单文件组件

下个会话照这份开工。开工第一步：把现在的 `web/index.html` 复制成 `.tmp/index-legacy.html`（回退用，不进 git），之后 `web/` 原地替换。

## 目标

`web/index.html` 从「1360 行单文件原生页」改成 Vite + Vue 3 + `.vue` 单文件组件的工程，功能与样式与现在等价，`server.py` 只改静态文件服务。

## 范围

改：

- `web/`：拆成 Vite 工程（入口 HTML、`src/`、`package.json`、`vite.config.js`、构建产物 `dist/`）。
- `server.py`：`INDEX` 指向 `web/dist/index.html`，新增 `/assets/*` 静态资源路由（只允许 `web/dist` 下的文件，拒绝 `..`）。
- `docs/ui-checklist.md`：步骤与 DOM 结构对不上的地方就地改。

不改：

- `agent/` 全部代码、`/ask` `/abort` `/sessions` `/model` `/prompt` `/files` 的协议与 cookie 机制、NDJSON 事件格式。
- `deliverables/生物信息/report.ipynb`、`skills/`、`run_server.sh`。

## 目录形状

```
web/
  index.html            只有 <div id="app"> 和 <script type="module" src="/src/main.js">
  package.json          vue + vite（devDependencies 只这两个）
  vite.config.js        base '/'，build.outDir 'dist'
  src/
    main.js             createApp(App).mount('#app')
    App.vue             布局骨架：左栏 / 主区 / 右栏 / 输入区
    styles/base.css     现有 CSS 变量、基础样式、断点一处 860px
    lib/markdown.js     mdToHtml 原样搬
    lib/ids.js          idInfo / describeId 原样搬
    composables/
      useSessions.js    会话列表、建/删/改名/选中、标题
      useStream.js      fetch + getReader 按行读 NDJSON，事件分派
      useRail.js        右栏开关、窄屏 matchMedia、跳过一屏浮出
    components/
      SessionList.vue   左栏：新建、改名、删除、当前项
      Conversation.vue  主区滚动容器
      TurnBlock.vue     一轮：问句 + 答案 + 思考块 + 过程块 + 徽章 + 计量
      Question.vue      问句 + 右上角复制
      Answer.vue        正文 + 右上角复制 + 失败告警条
      ThinkBlock.vue    流式思考，完成后收起
      ProcessBlock.vue  工具调用行、`is_error` 红字
      EvidenceBadge.vue 「引用 N 条」+ 每行名称 / 站点 / 编号
      MetaRow.vue       字数、思考字数、token、工具调用次数
      TrajectoryRail.vue 右栏轨迹，按轮收起，覆盖层 + 遮罩
      Composer.vue      输入框、`/` 技能菜单、`@` 文件、发送、中止
      ModelMenu.vue     底部模型座位 + 平铺清单
      PromptSheet.vue   `/prompt` 折叠面板
      FileView.vue      文件预览
```

## 结果（可检查）

1. `cd web && npm install && npm run build` 成功，产物在 `web/dist`。
2. `./run_server.sh` 后 `/` 返回 200，页面能加载 JS 与 CSS（`/assets/*` 200）。
3. 功能对照：流式追字、思考块收起、过程块与右栏轨迹、引用徽章与名称、复制、中止 0.8 秒内结束、旧会话回放（`.tmp/sessions/*.json`）、窄屏（<860px）右栏覆盖层、长历史跳到最新、整轮失败红条。
4. `docs/ui-checklist.md` 44 步人工走查逐条通过。

## 失败处理

- 构建失败或走查不过：把 `.tmp/index-legacy.html` 复制回 `web/index.html` 临时顶住，旧文件在验收通过前不删。
- `npm install` 无网络或装不上：停下来报错，不在无依赖的情况下硬改。

## 介入点

- 类型：不引 TypeScript，保持 JS。
- Markdown：不引库，沿用 `mdToHtml`。
- 状态管理：不引 Pinia，用 `reactive` 单例 + `provide/inject`。
- 样式：沿用现有 CSS 变量与 860px 断点，不改视觉；要改视觉另开一轮。

## 已知偏离

`web/node_modules` 与 `web/dist` 是工作区规则里的「禁放目录」，但 Vite 工程必须同根。做法：

- `web/.gitignore` 写 `node_modules/`、`dist/`。
- `python3 scripts/check-expiry.py` 会打印 1 项「禁放目录」，属已知偏离，回复里说明。
- 收尾不删 `node_modules`（下次还要用），`dist` 保留以便服务直接跑。

## 落地记录（2026-11-19）

照上面的规格做完了，`web/` 已是 Vite + Vue 3 工程，`server.py` 只改静态文件服务（`INDEX` 指向 `web/dist/index.html`，新增 `/assets/*`，越界与缺失一律 404）。

与规格的差别：

- 多一个 `devDependencies`：`@vitejs/plugin-vue`。单文件组件必须靠它编译，只装 `vue` + `vite` 跑不起来。
- `MetaRow.vue` 没建：计量行就两行模板，直接写在 `Question.vue` 与 `Answer.vue` 里。
- 多两个组件：`CopyButton.vue`（剪贴板与图标切换三处共用）、`RecordCard.vue`（轨迹卡）；文件树拆成 `FileView.vue` + 递归的 `FileNode.vue`。
- 状态没有用 `provide/inject`：`composables/` 三个模块各自导出模块级 `reactive` 单例，组件直接 import。
- 右栏轨迹不再随事件追加：直接从 `turns[].events` 推导（`TrajectoryRail.vue` 的 `recordsOf`），实时与回放同一套渲染，分组单位统一成「第 N 问」。`loadTrajectory` 与 `pushTrajectory` 随之消失，会话切换只请求一次 `/sessions/<id>/turns`。
- 旧页留在 `.tmp/index-legacy.html`，未删。

## 动效（2026-11-19，取值已被 2026-11-21 的重做取代）

「样式不改视觉」这条按新指令放开了一半：加动效，不动布局、字号、行宽与颜色值。

加的十处，全部纯 CSS，不引依赖，时长只取 `--t1`(160ms) 与 `--t2`(200ms) 两档，位移不超过 6px：

| 位置 | 效果 |
|---|---|
| `.turn` | 新一问淡入并上浮 4px |
| `.answer` | 答案替换流式区时淡入，缓解高度突变 |
| `.wrap` | 换会话时整块淡入（`chat.gen` 变化重建） |
| `.menu-box` / `.menu` | 输入框菜单上浮、会话菜单下落 |
| `.rightbar.floating` | 窄屏覆盖层从右侧滑出，收起滑回 |
| `.backdrop` | 遮罩同步淡入淡出 |
| `.right-open` / `.jump` | 浮出按钮淡入加位移，不再闪现 |
| `.rec` | 轨迹卡悬停时底色与边框过渡 |
| `.copy` | 按下时缩到 0.92 |

配套的机制改动：

- 右栏显隐从 `v-show`（`display` 切换，无法过渡）改成 `.closed` 类。窄屏 `closed` 走 `translateX(100%)` 滑出，宽屏 `closed` 仍是 `display: none`，因为常驻栏收起必须真的让出宽度。
- `rail.floating` 在窄屏恒为 true，`closeRail()` 不再清它；媒体查询变化时窄屏设 `floating = true` 再收起，否则窄屏自动收起会退化成宽屏的 `display: none`。
- 遮罩、右上角面板图标、「跳到最新」从 `hidden` 属性改成 `.shown` 类，用 `visibility` 加延迟过渡实现淡出后不可点。右上角图标改成与右栏内收起按钮同一图形、同一尺寸（28×28）的图标按钮。
- 「跳到最新」从 `position: fixed; bottom: 104px` 改成挂在 `Composer.vue` 的 `.composer-wrap` 上（`absolute; left: 50%; bottom: calc(100% + var(--s2)); transform: translate(-50%, …)`）：水平居中于输入区（即主区中心），输入框长高到 8 行时按钮跟着上移，不再被盖住；滚动函数改成 `useRail.js` 的 `scrollToLatest()`，两个组件共用。
- `chat.gen` 每次换会话加一，`.wrap` 用它当 `key`，重建一次播淡入。

性能红线：`.stream`、`.think` 与流式期间重建的文字节点不加任何 `transition`/`animation`；`prefers-reduced-motion: reduce` 下仍全关（实测 `animation-name` 与 `transition-duration` 均为 none/0s）。

服务端顺带修两处：`/` 与 `/index.html` 加 `Cache-Control: no-store`（否则重新构建后浏览器可能拿旧 `index.html` 去请求已删除的哈希资源）；根路径改用 `urlparse(self.path).path` 比较，带查询串也能打开。

## 第二轮改造（2026-11-21）：亮色工作台与动效规范

上一节记的是深色版当时的取值。这一轮把界面按产品级重做，动效从「十处各自调参数」改成一整套规范，当前值以 `styles/base.css` 的 `:root` 与 `docs/motion.md` 为准：

- **配色**：暖灰画布 `#f6f4f1`、白面 `#fff`、浅凹槽 `#efece6`，全页一个强调蓝 `#2f56d6`，语义色只留给右栏记录的 6px 圆点。
- **字号六档**：12.5 / 13.5 / 14.5 / 15 / 16 / 18px；行宽 74ch、行高 1.7；圆角 6 / 8 / 12px。
- **布局**：左栏 240px、正文列 74ch 居中、右栏 380px，右栏默认收起成 56px 窄条，条上只有一个展开按钮，与展开后的收起按钮同一格（`30×30`，同一像素位置）。`<1080px` 右栏改覆盖层，左栏 216px。
- **动效令牌**：`--t-press 90` / `--t1 160` / `--t2 240` / `--t3 300` / `--t-out 140`，进入 `--ease-out`、退出 `--ease-in`；按压统一 `scale(.94–.98)`；浮层开合用 `<Transition name="pop"> / <Transition name="pop-down">`。
- **图标**：换成 `lucide-vue-next`，原先手写的 SVG 全删。
- **修的两处细节**：轨迹记录行 `.head` 从 `align-items: baseline` 改 `center`（行首圆点没有基线，`用户` 与记录名会错开 2–3px）；复制按钮连点只留一个复位计时器，否则前一次点击会提前熄灭勾选态。

实测：连开连合右栏 6 次宽度 380 / 56 交替、终态正确；连开关菜单 6 次残留 0 节点；减弱动态下时长 `1e-05s`；回放 21 条记录与连开合 6 次期间无 `longtask`。
