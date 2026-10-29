# 原生升级基线已归档

V3 的活动源码和默认开发入口已统一为 `src`。请使用本目录的 `pnpm dev`、`pnpm test`、`pnpm build`。

旧源码、构建配置和测试保存在 `architecture-archive/src-native-20261028.tar.gz`，附逐文件校验清单。

- `pnpm verify:baseline`：验证归档与逐文件 SHA-256。
- `pnpm test:baseline`：在临时目录中运行冻结的历史对照测试。

原说明保存在 [归档说明](architecture-archive/README.native-20261028.md)。归档内容不参与应用运行或构建。
