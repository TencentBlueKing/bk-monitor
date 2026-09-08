import { listTraces } from 'monitor-api/modules/llm_web';

import { PAGE_LIMIT, SESSION_GROUP_FIELD, TRACE_GROUP_FIELD } from '../constants';

import type { ILlmTraceItem, ILlmTraceListData, LlmViewMode } from '../typings';

/** 一次列表查询所依赖的全部上下文 */
export interface ILlmQueryContext {
  appName: string;
  endTime: number;
  keyword: string;
  offset: number;
  serviceName: string;
  /** 排序参数：升序为字段名，降序加 - 前缀，空串表示不排序 */
  sort: string;
  startTime: number;
  viewMode: LlmViewMode;
}

/** 组装 list_traces 请求参数：两个视角只有分组字段不同，bk_biz_id 由请求层自动注入 */
export function createListParams(ctx: ILlmQueryContext) {
  return {
    app_name: ctx.appName,
    service_name: ctx.serviceName,
    start_time: ctx.startTime,
    end_time: ctx.endTime,
    group_field: ctx.viewMode === 'session' ? SESSION_GROUP_FIELD : TRACE_GROUP_FIELD,
    keyword: ctx.keyword,
    sort: ctx.sort,
    offset: ctx.offset,
    limit: PAGE_LIMIT,
  };
}

/** 拉取一页分组数据，失败时返回空列表交由调用方结束加载态 */
export async function fetchLlmTraceList(ctx: ILlmQueryContext, cancelToken): Promise<ILlmTraceItem[]> {
  const data: ILlmTraceListData = await listTraces(createListParams(ctx), { cancelToken }).catch(() => null);
  return data?.items ?? [];
}
