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

export interface CompareTarget {
  bk_inst_id?: number;
  bk_obj_id?: string;
  bk_target_cloud_id?: number;
  bk_target_ip?: string;
}

/** 目标对比的单个目标选项（如主机 IP） */
export interface CompareTargetOption {
  /** 目标唯一标识 */
  id: string;
  /** 展示名称，通常为 IP */
  name: string;
}

/**
 * 指标汇聚 Toolbar 的完整状态。
 * 以普通响应式状态对外暴露，替代旧版「变量替换」方式，图表后续直接以 props 消费。
 */
export interface MetricAggregationState {
  /** 列数：1 / 2 / 3 */
  columns: number;
  /** 目标对比选中的目标 列表 */
  compareTargets: CompareTarget[];
  /** 对比方法 */
  compareType: MetricCompareType;
  /** 高亮峰谷值 */
  highlightPeak: boolean;
  /** 汇聚周期，默认 auto */
  interval: string;
  /** 指标搜索关键字 */
  keyword: string;
  /** 汇聚方法，默认 MAX */
  method: string;
  /** 展示统计值 */
  showStatistics: boolean;
  /** 时间对比选中的时间偏移 id 列表 */
  timeShift: string[];
}

/** 对比方法类型：不对比 / 目标对比 / 时间对比 */
export type MetricCompareType = 'none' | 'target' | 'time';

/** 通用下拉选项 */
export interface SelectOption {
  id: string;
  name: string;
}
