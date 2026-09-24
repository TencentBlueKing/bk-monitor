/** APM 服务详情调用链过滤条件同步到路由的参数名，切 tab 时由 CommonPage 清掉 */
export const APM_TRACE_ROUTER_QUERY_KEYS = [
  'traceWhere',
  'traceQueryString',
  'traceFilterMode',
  'traceCommonWhere',
  'traceSelectedType',
] as const;

export type ApmTraceRouterQueryKey = (typeof APM_TRACE_ROUTER_QUERY_KEYS)[number];
