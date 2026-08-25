# Skill: AAFE Test from PR

Trigger: 用户要按 PR/MR **生成测试用例**、**补测试**、**执行 e2e** 或 **输出报告**，包括直接贴出 PR/MR 链接。

Companion CLI: `aafe test --pr=<url>`（本包能力，不是 `uitest`）。

## Hard

- **只跑** `aafe test`。`aafe` 不在 PATH 时用 `node_modules/.bin/aafe`。
- **禁止**安装或调用 `uitest`、`@aafe/ai-test`、`npx uitest`、`npx uitest init`、`npx uitest from-pr`。
- **禁止**把 `ai-ui-test` / `uitest-from-pr` 写回 `.cursor/`。
- 不要为这条路径安装任何 uitest 依赖。Playwright 由 `aafe e2e enable|install` 按项目选择，不是本口令的前置安装步骤。

## Steps

1. 从用户消息取出 PR/MR URL（GitHub `/pull/` 或工蜂 `/merge_requests/`）。没有链接就问一句，不要编。
2. 生成用例：`aafe test --pr=<url>`。YAML 落 `tests/ui-ai/cases/`。
3. 用户还要求执行 e2e / 出报告：尽量带 `--run`。
   - 用户消息里已有被测页面 URL（不是 PR 链接）→ 先确认该地址角色，再 `aafe test --pr=<url> --run --base-url=<该地址> --url-role=...`。含 `#` 的地址必须用引号，禁止把 hash 丢掉后只拿 origin。
   - 否则**必须停下来询问并等待用户输入本次测试地址**。地址每次可能不同，不要写进 `e2e.baseUrl` / 环境变量，不要猜，不要用 `http://localhost:8080`。
   - 用户给出地址后，若包含页面路径（`#/...`）或查询参数，**必须再确认并等待**：
     - **A** 是目标页面：匹配该路径的用例打开这个完整地址；其它用例复用同一主机、hash/history 模式和查询参数。
     - **B** 不是，只是环境根地址：丢弃 `#` 后的路径和业务参数。
     - **C** 需要根据此地址分析变更（推荐）：提取协议/主机、是否 hash 路由、以及 bizId 等参数，拼到本次变更的各条路由上。
     然后 `--run --base-url=<用户输入> --url-role=target|origin|template`（A/B/C）。
   - 没有路径/参数的纯 origin 可直接 `--run --base-url=<用户输入>`。
   - CLI 返回 `needInput: "baseUrl"` 或 `needInput: "urlRole"` 时同样：问用户，等待，再带齐参数重跑。
   - 业务需登录 / SSO：每次 `--run` **先匿名探测用户地址**（HTTP 200 且未跳转登录则跳过 SSO，适合 Dev 本地代理）；否则再校验登录态，未登录或过期则重新登录并更新 `.aafe/e2e/auth`。无认证且非交互环境会返回 `needInput: "auth"`，引导 `aafe e2e auth --base-url=<url>`。不要把密码写入配置。
4. 只读统一报告 `.aafe/e2e/reports/<runId>/{report.json,index.html}`，不要散落到 `test/ui/`、`playwright-report/`、`test-results/`。
5. 命令提示 `e2e.enabled !== true` → 告诉用户 `aafe e2e enable`，仍然不要装 uitest。
6. Playwright 缺失时报告为 blocked；不要改口去装 uitest。

## Pointers

详细自测分层见 `.ai-agent/skills/minimal-convergent-self-test.md`。任务收尾 UI 走 `aafe test --diff`，不要默认 `--coverage`。
