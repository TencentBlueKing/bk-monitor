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

import type { IHostMetricInfo } from './host';

/** 集群信息（前端从主机模块的 topo_link 中提取） */
export interface IHostCluster {
  id: string;
  name: string;
}

/**
 * 主机列表表格行：在接口的指标数据上扩展前端派生字段，
 * 派生字段用于排序、模糊搜索、快捷过滤与唯一标识，避免渲染时重复计算。
 */
export interface IHostListRow extends IHostMetricInfo {
  /** 集群列表（用于「集群名」过滤/展示） */
  bkClusters: IHostCluster[];
  /** 集群名拼接串（模糊搜索用） */
  clusterNames: string;
  /** 模块名拼接串（模糊搜索用） */
  moduleNames: string;
  /** 进程名拼接串（模糊搜索用） */
  processNames: string;
  /** 行唯一 id：优先 bk_host_id，回退 ip|cloud */
  rowId: string;
  /** 未恢复告警总数 */
  totalAlarmCount: number;
}

/** 快捷过滤卡片分类 key */
export type EHostQuickCategory = 'alarm' | 'cpu' | 'disk' | 'mem';

/** 快捷过滤卡片配置 */
export interface IHostQuickCard {
  /** 图标字体类名（icon-monitor） */
  icon: string;
  /** 分类 key */
  key: EHostQuickCategory;
  /** 卡片名称（i18n key） */
  name: string;
}

/** 快捷过滤卡片统计（各分类命中主机数） */
export type IHostQuickCardStats = Record<EHostQuickCategory, number>;

/** 指标聚合方式 */
export type EHostAggMethod = 'avg' | 'max' | 'min';

/** 采集状态展示配置 */
export interface IHostStatusConfig {
  /** 圆点颜色 */
  color: string;
  /** 状态名称（i18n key） */
  name: string;
}
