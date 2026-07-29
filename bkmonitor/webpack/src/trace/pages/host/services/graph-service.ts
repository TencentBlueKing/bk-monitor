/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import {
  getHostMetricGroupPanelOrder,
  getHostViewsPanels,
  getProcessMetricGroupPanelOrder,
  getProcessViewsPanels,
} from 'monitor-api/modules/performance';

import type { MetricGroupPanelOrder } from '../types/panel-order';
import type { HostViewsRowPanel } from '../types/panels';

/** 主机指标分组面板排序缓存：整页生命周期内只取一次 */
let hostMetricGroupPanelOrderCache: MetricGroupPanelOrder[] | null = null;

/**
 * @description: 获取主机视图面板
 * @returns {Promise<HostViewsRowPanel[]>} 主机视图面板
 */
export const getHostViewsPanelsApi = async (): Promise<HostViewsRowPanel[]> => {
  return await getHostViewsPanels();
};

/** 进程视图面板缓存：整页生命周期内只取一次，后续打开进程详情直接复用 */
let processViewsPanelsCache: HostViewsRowPanel[] | null = null;
/** 进程指标分组面板排序缓存：整页生命周期内只取一次 */
let processMetricGroupPanelOrderCache: MetricGroupPanelOrder[] | null = null;

/**
 * @description: 获取进程视图面板（带模块级缓存）
 * @param forceRefresh 是否强制刷新（默认 false）：
 * - false：优先复用模块级缓存，缓存为空时才发起请求
 * - true：忽略现有缓存，强制重新请求并用最新结果覆盖缓存（如保存/重置排序配置后调用）
 * @returns {Promise<HostViewsRowPanel[]>} 进程视图面板
 */
export const getProcessViewsPanelsApi = async (forceRefresh = false): Promise<HostViewsRowPanel[]> => {
  if (!processViewsPanelsCache || forceRefresh) {
    processViewsPanelsCache = await getProcessViewsPanels().catch(() => []);
  }
  return processViewsPanelsCache;
};

/**
 * @description: 获取指标分组面板排序配置（带模块级缓存）
 * @param forceRefresh 是否强制刷新（默认 false）：
 * - false：优先复用模块级缓存，缓存为空时才发起请求
 * - true：忽略现有缓存，强制重新请求并用最新结果覆盖缓存（如保存/重置排序配置后调用）
 * @returns {Promise<MetricGroupPanelOrder[]>} 指标分组面板排序配置
 */
export const getHostMetricGroupPanelOrderApi = async (forceRefresh = false): Promise<MetricGroupPanelOrder[]> => {
  if (!hostMetricGroupPanelOrderCache || forceRefresh) {
    hostMetricGroupPanelOrderCache = await getHostMetricGroupPanelOrder();
  }
  return hostMetricGroupPanelOrderCache;
};

/**
 * @description: 获取进程指标分组面板排序配置（带模块级缓存）
 * @param forceRefresh 是否强制刷新（默认 false）：
 * - false：优先复用模块级缓存，缓存为空时才发起请求
 * - true：忽略现有缓存，强制重新请求并用最新结果覆盖缓存（如保存/重置排序配置后调用）
 * @returns {Promise<MetricGroupPanelOrder[]>} 进程指标分组面板排序配置
 */
export const getProcessMetricGroupPanelOrderApi = async (forceRefresh = false): Promise<MetricGroupPanelOrder[]> => {
  if (!processMetricGroupPanelOrderCache || forceRefresh) {
    processMetricGroupPanelOrderCache = await getProcessMetricGroupPanelOrder().catch(() => []);
  }
  return processMetricGroupPanelOrderCache;
};
