/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
/**
 * trace-explore-apm.tsx —— APM 场景下的 Trace 检索包装组件
 *
 * 本组件是 TraceExplore 的 APM 适配层，通过 Vue 3 的 provide/inject 机制
 * 将 APM 专属的行为注入到通用的 TraceExplore 中。
 *
 * 组件层级关系：
 *   trace-explore-apm-entry.ts          ← 独立构建入口，createApp 挂载根组件
 *     └─ TraceExploreApm (本文件)       ← APM 适配层，注入桥接 & hooks
 *         └─ TraceExplore               ← 通用 Trace 检索，通过 inject 消费 hooks
 *
 * 职责：
 *   1. 从 trace-explore-apm-entry 注入的 bridgeProps / bridgeEmit 中获取
 *      Vue 2 宿主传递的属性和事件回调
 *   2. 将宿主的 timeRange、refreshInterval 等属性同步到 trace explore store
 *   3. 通过 provide(TRACE_EXPLORE_APM_HOOKS_KEY, hooks) 向 TraceExplore 注入
 *      APM 专属回调（条件变更、查询语句变更、筛选模式变更）
 *   4. 同时 provide handleExploreChartZoomChange 供图表子组件使用
 *   5. 管理 window.APM_QUERY_STRING 的生命周期
 */
import { defineComponent, inject, provide, watch } from 'vue';

import type { IWhereItem, EMode } from '../../components/retrieval-filter/typing';
import type { TimeRangeType } from '../../components/time-range/utils';
import { useTraceExploreStore } from '@/store/modules/explore';

import TraceExplore from './trace-explore';

/**
 * TraceExplore 消费的 APM 专属回调接口。
 * TraceExplore 通过 inject(TRACE_EXPLORE_APM_HOOKS_KEY) 获取此对象，
 * 在用户操作时调用对应方法将事件桥接回 Vue 2 宿主。
 * 当 inject 得到 null 时表示非 APM 场景，TraceExplore 会退化为标准模式
 * （例如显示页头 TraceExploreHeader）。
 */
export interface TraceExploreApmHooks {
  /** UI 检索条件（where）变更时回调，将新的条件列表通知宿主 */
  onConditionChange?: (condition: IWhereItem[]) => void;
  /** 查询语句变更时回调，将新的查询字符串通知宿主 */
  onQueryStringChange?: (queryString: string) => void;
  /** 筛选模式（UI / 语句）变更时回调，将新的模式通知宿主 */
  onFilterModeChange?: (mode: EMode) => void;
}

/** provide/inject key —— TraceExplore 用此 key 获取 APM 回调钩子 */
export const TRACE_EXPLORE_APM_HOOKS_KEY = Symbol('traceExploreApmHooks');
/** provide/inject key —— 从 trace-explore-apm-entry 注入的宿主属性（reactive 对象） */
export const BRIDGE_PROPS_KEY = Symbol('bridgeProps');
/** provide/inject key —— 从 trace-explore-apm-entry 注入的宿主事件发射器 */
export const BRIDGE_EMIT_KEY = Symbol('bridgeEmit');
/** provide/inject key —— APM 服务名称 */
export const APM_SERVICE_NAME_KEY = Symbol('APM_SERVICE_NAME');
export default defineComponent({
  name: 'TraceExploreApm',
  setup() {
    const exploreStore = useTraceExploreStore();

    const bridgeProps = inject(BRIDGE_PROPS_KEY, {} as Record<string, any>);
    const bridgeEmit = inject(BRIDGE_EMIT_KEY, (() => {}) as (event: string, ...args: unknown[]) => void);

    const handleExploreChartZoomChange = (v: [number, number]) => {
      bridgeEmit('exploreChartZoomChange', v);
    };
    provide('handleExploreChartZoomChange', handleExploreChartZoomChange);
    provide(APM_SERVICE_NAME_KEY, bridgeProps.viewOptions.filters.service_name);

    watch(
      bridgeProps,
      () => {
        exploreStore.refreshImmediate = bridgeProps.refreshImmediate as string;
        exploreStore.refreshInterval = Number(bridgeProps.refreshInterval);
        exploreStore.timeRange = bridgeProps.timeRange as TimeRangeType;
      },
      {
        immediate: true,
        deep: true,
      }
    );

    const apmHooks: TraceExploreApmHooks = {
      onConditionChange: condition => bridgeEmit('conditionChange', condition),
      onQueryStringChange: queryString => bridgeEmit('queryStringChange', queryString),
      onFilterModeChange: mode => bridgeEmit('filterModeChange', mode),
    };
    provide(TRACE_EXPLORE_APM_HOOKS_KEY, apmHooks);
  },
  render() {
    return <TraceExplore />;
  },
});
