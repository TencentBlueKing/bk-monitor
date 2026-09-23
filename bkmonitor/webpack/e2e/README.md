# E2E 公共运行配置

本目录仅维护脱敏公共基础设施：Playwright 配置与依赖检查。项目依赖及锁文件固定运行版本。

```bash
pnpm e2e:doctor
pnpm e2e:install
```

`doctor` 检查 Node、项目依赖、Chromium 与产物忽略规则；`install` 安装项目版本对应的 Chromium，浏览器缓存可跨分支复用。

调用 Playwright 配置时提供 `BKMONITOR_E2E_RUN_DIR`（项目 `.e2e-runs/` 内的单次目录）与 `BKMONITOR_E2E_BASE_URL`。可选 `BKMONITOR_E2E_VIEWPORT`、`BKMONITOR_E2E_HEADED`、`BKMONITOR_E2E_STORAGE_STATE`；认证状态文件必须在该次目录内。

配置只执行该次目录中的用例，使用 Chromium、单 worker、零重试，输出 HTML/JSON、截图、视频及失败 trace。数据、凭据、一次性用例及报告保留在已忽略的本地运行目录，不提交到 Git。

AI 工作流与相关脚本由独立私有 skills 仓库维护；本目录不复制、安装或同步 skills，公共命令不依赖私有目录。共享配置不得包含环境内网地址、账号、Cookie、Token 或本机绝对路径。
