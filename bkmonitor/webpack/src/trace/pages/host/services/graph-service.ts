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

import { getMockProcessMetricGroupPanelOrder, getMockProcessViewsPanels } from '../mock/process-metric';

import type { MetricGroupPanelOrder } from '../types/panel-order';
import type { HostViewsRowPanel } from '../types/panels';

/**
 * @description: 获取主机视图面板
 * @param scene 场景类型
 * @returns {Promise<HostViewsRowPanel[]>} 主机视图面板
 */
export const getHostViewsPanels = async (): Promise<HostViewsRowPanel[]> => {
  return [];
};

/** 进程视图面板缓存：整页生命周期内只取一次，后续打开进程详情直接复用 */
let processViewsPanelsCache: HostViewsRowPanel[] | null = null;
/** 进程指标分组面板排序缓存：整页生命周期内只取一次 */
let processMetricGroupPanelOrderCache: MetricGroupPanelOrder[] | null = null;

/**
 * @description: 获取进程视图面板（带模块级缓存）
 * @returns {Promise<HostViewsRowPanel[]>} 进程视图面板
 */
export const getProcessViewsPanels = async (): Promise<HostViewsRowPanel[]> => {
  if (!processViewsPanelsCache) {
    processViewsPanelsCache = getMockProcessViewsPanels();
  }
  return processViewsPanelsCache;
};

/**
 * @description: 获取指标分组面板排序配置
 * @returns {Promise<MetricGroupPanelOrder[]>} 指标分组面板排序配置
 */
export const getHostMetricGroupPanelOrder = async (): Promise<MetricGroupPanelOrder[]> => {
  return [];
};

/**
 * @description: 获取进程指标分组面板排序配置（带模块级缓存）
 * @returns {Promise<MetricGroupPanelOrder[]>} 进程指标分组面板排序配置
 */
export const getProcessMetricGroupPanelOrder = async (): Promise<MetricGroupPanelOrder[]> => {
  if (!processMetricGroupPanelOrderCache) {
    processMetricGroupPanelOrderCache = getMockProcessMetricGroupPanelOrder();
  }
  return processMetricGroupPanelOrderCache;
};
