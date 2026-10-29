# P2 UI 基线

状态：BLOCKED。

已用登录态打开 `http://appdev.woa.com:8001/#/retrieve/38131?spaceUid=bkcc__5000140&bizId=5000140`。地址停在检索路由，没有跳到登录页。页面停在 `Loading... Init resources... Load runtime... Prepare search...`。webpack-dev-server 报编译错误并阻止刷新，涉及 `@blueking/bkui-library` 缺少 `h` 和 `reactive`。检索界面没有出现。

`migration-project/artifacts/visual/p3/` 里的纯色图只证明比较器能写报告。`packages/web-v3/.ai-native/` 里的本地图片也不作为基线。

因此 P4 不能做默认态、交互态、异常态和弹层的视觉回归。
