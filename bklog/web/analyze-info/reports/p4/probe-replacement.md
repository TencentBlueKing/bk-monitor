# V2 观测边界修复

本批修改针对此前已有的诊断代码，不是 V3 业务功能修复。

- Store dispatch 保留原 handler 返回值 / Promise 身份和同步异常；不再新增 after/error 订阅调用。原 before 订阅保留。
- HTTP 服务包装保留原 config 对象和返回值，不再注入 __bklogTraceparent；axios 原先生成 Traceparent 的逻辑恢复。
- Worker 检索只读取原 searchHeaders.Traceparent，不再为探针覆盖请求头。
- recordAnalyze 只接收显式 parentSpanId；没有因果证据时不从并发共享栈推断父节点。
- stage 仍是诊断提示，不作为 UI ready 证明。payload 摘要不作为完整响应。

新增测试从实际 Store dispatch 和 HTTP request 方法提取执行体，分别在探针启用/关闭下校验返回值、Promise 身份、同步错误、config 身份、订阅次数。24 项核心校准已通过；12 项受控浏览器校准通过。这些结果不能替代真实 V2/V3 业务验收。

## 本地只读观测发现

初始化环境、用户、空间、菜单接口正常响应。公告接口返回 404 HTML；首次发现脚本误将 HTML 当作登录失败。该次 discovery 状态无效，后续已修正为明确的登录状态/跳转依据，不将任意 HTML 或 403 当作登录过期。

AI SDK getSessions 是 GET 读取；plusSession 是 POST 新增，且挂载时会自动调用。本阶段阻止自动新增，不返回伪成功。只读捕获中 AI 功能仍保持受阻，不能宣布完整基准可用。

所有尚未分类的接口都阻止。未知依赖导致的未就绪不列为产品缺陷。原始完整日志和凭据未写入本报告。

## 试点运行记录（不计业务验收）

检索行展开配方已完成四个 UI checkpoint：查询就绪、KV 筛选、JSON 切换、恢复并收起。筛选的 level 值由完整 NDJSON 第0行 origin_data 校验。流包含52个事件（meta、50行、done）。

定位器迭代发现并纠正：JSON标签原始文本含空白；field-value外层容器与内层值节点同名；外层文本还包含字段名称。修正来自模板源码，使用带 data-field-name 的值节点，无随机 first 选择。此前运行均保留 INVALID_RUN，不列产品缺陷。

空间完整列表曾被 Playwright 内部调试缓存驱逐；增加 CDP 完整响应回取，只接受 URL、method、body 唯一对应的真实 requestId。遇歧义仍失败，不重发请求凑基准。

首次自回放执行了四个检查点，但导出历史请求使用 Date.now，导致完整签名不匹配；因此保留 INVALID_SELF_REPLAY。正在按场景固定 Date 时钟重新采集。没有删除时间参数或放宽为仅匹配路径。旧趋势/总数请求的取消需保留，并验证后续成功替换；不能当作残缺成功响应。
