# P2 UI 基线

状态：检索页已打开。采集向导的视觉基线仍未采集。

已用登录态打开 `http://appdev.woa.com:8001/#/retrieve/38131?spaceUid=bkcc__5000140&bizId=5000140`。地址停在检索路由，没有跳到登录页。页面出现检索界面，并列出查询结果。此前停在初始化文案，是因为 15:44 启动的 webpack 仍拿着旧的 pnpm 依赖图，报 `@blueking/bkui-library` 缺少 `h` 和 `reactive`。清掉 `.cache` 并用当前 npm 依赖重启后，同一地址编译通过，overlay 消失。

`migration-project/artifacts/visual/p3/` 里的纯色图只证明比较器能写报告。`packages/web-v3/.ai-native/` 里的本地图片也不作为基线。

因此 P4 不能做默认态、交互态、异常态和弹层的视觉回归。
