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
 * alarm-center-apm.tsx —— APM 场景下的告警中心包装组件
 *
 * 本组件是 AlarmCenter 的 APM 适配层，通过 Vue 3 的 provide/inject 机制
 * 将 APM 专属的行为注入到通用的 AlarmCenter 中，取代原先基于条件编译
 * （#if IS_APM_MONITOR）的方案。
 *
 * 组件层级关系：
 *   alarm-center-apm-entry.ts          ← 独立构建入口，createApp 挂载根组件
 *     └─ AlarmCenterApm (本文件)       ← APM 适配层，注入桥接 & hooks
 *         └─ AlarmCenter               ← 通用告警中心，通过 inject 消费 hooks
 *
 * 职责：
 *   1. 从 alarm-center-apm-entry 注入的 bridgeProps / bridgeEmit 中获取
 *      Vue 2 宿主传递的属性和事件回调
 *   2. 将宿主的 timeRange、refreshInterval 等属性同步到 alarmStore
 *   3. 通过 provide(ALARM_CENTER_APM_HOOKS_KEY, hooks) 向 AlarmCenter 注入
 *      APM 专属回调（条件变更、查询语句变更、筛选模式变更），AlarmCenter
 *      在对应操作时会调用这些回调，从而通知 Vue 2 宿主
 *   4. 同时 provide handleAlarmTrendChartZoomChange 供趋势图子组件使用
 *   5. 管理 window.APM_QUERY_STRING 的生命周期
 */
import { defineComponent, inject, onBeforeUnmount, provide, watch } from 'vue';

import AlarmCenter from './alarm-center';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { CommonCondition } from './typings';
import type { EMode } from '../../components/retrieval-filter/typing';

/**
 * AlarmCenter 消费的 APM 专属回调接口。
 * AlarmCenter 通过 inject(ALARM_CENTER_APM_HOOKS_KEY) 获取此对象，
 * 在用户操作时调用对应方法将事件桥接回 Vue 2 宿主。
 * 当 inject 得到 null 时表示非 APM 场景，AlarmCenter 会退化为标准模式
 * （例如显示页头 AlarmCenterHeader）。
 */
export interface AlarmCenterApmHooks {
  /** 检索条件变更时回调，将新的条件列表通知宿主 */
  onConditionChange?: (condition: CommonCondition[]) => void;
  /** 查询语句变更时回调，将新的查询字符串通知宿主 */
  onQueryStringChange?: (queryString: string) => void;
  /** 筛选模式（UI / 语句）变更时回调，将新的模式通知宿主 */
  onFilterModeChange?: (mode: EMode) => void;
}

/** provide/inject key —— AlarmCenter 用此 key 获取 APM 回调钩子 */
export const ALARM_CENTER_APM_HOOKS_KEY = Symbol('alarmCenterApmHooks');
/** provide/inject key —— 从 alarm-center-apm-entry 注入的宿主属性（reactive 对象） */
export const BRIDGE_PROPS_KEY = Symbol('bridgeProps');
/** provide/inject key —— 从 alarm-center-apm-entry 注入的宿主事件发射器 */
export const BRIDGE_EMIT_KEY = Symbol('bridgeEmit');

export default defineComponent({
  name: 'AlarmCenterApm',
  setup() {
    const alarmStore = useAlarmCenterStore();

    /**
     * 从 alarm-center-apm-entry 的 app.provide() 中获取桥接数据：
     * - bridgeProps: Vue 2 宿主传入的响应式属性（timeRange / refreshInterval 等）
     * - bridgeEmit:  向 Vue 2 宿主抛出事件的函数
     */
    const bridgeProps = inject(BRIDGE_PROPS_KEY, {} as Record<string, any>);
    const bridgeEmit = inject(BRIDGE_EMIT_KEY, (() => {}) as (event: string, ...args: unknown[]) => void);

    /** 将宿主传入的 queryString 挂到 window 上，供非 Vue 组件（如接口请求层）读取 */
    if (bridgeProps.queryString) {
      window.APM_QUERY_STRING = bridgeProps.queryString;
    }

    /** 趋势图缩放事件 → 通知宿主调整时间范围 */
    const handleAlarmTrendChartZoomChange = (v: [number, number]) => {
      bridgeEmit('alarmTrendChartZoomChange', v);
    };
    provide('handleAlarmTrendChartZoomChange', handleAlarmTrendChartZoomChange);

    /**
     * 监听宿主属性变化，同步到 alarmStore。
     * 宿主通过 handle.update({ timeRange, refreshInterval, ... }) 推送新值，
     * reactive 代理会触发此 watcher，从而驱动 AlarmCenter 内部刷新。
     */
    watch(
      bridgeProps,
      () => {
        alarmStore.refreshImmediate = bridgeProps.refreshImmediate;
        alarmStore.refreshInterval = Number(bridgeProps.refreshInterval);
        alarmStore.timeRange = bridgeProps.timeRange;
      },
      {
        immediate: true,
        deep: true,
      }
    );

    /**
     * 构造 APM hooks 并通过 provide 注入到 AlarmCenter。
     * AlarmCenter 在检索条件、查询语句、筛选模式变更时会调用这些回调，
     * 从而将变更事件桥接回 Vue 2 宿主。
     */
    const apmHooks: AlarmCenterApmHooks = {
      onConditionChange: condition => bridgeEmit('conditionChange', condition),
      onQueryStringChange: queryString => bridgeEmit('queryStringChange', queryString),
      onFilterModeChange: mode => bridgeEmit('filterModeChange', mode),
    };
    provide(ALARM_CENTER_APM_HOOKS_KEY, apmHooks);

    /** 组件卸载时清理全局变量 */
    onBeforeUnmount(() => {
      window.APM_QUERY_STRING = '';
    });
  },
  render() {
    return <AlarmCenter />;
  },
});
