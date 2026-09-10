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

import type { AlarmCenterPanelTabType } from '../../../utils/constant';
import type { EMode, IWhereItem } from '@/components/retrieval-filter/typing';

/** 诊断面板驱动左侧 tab 检索的筛选载荷 */
export interface IDiagnosticPanelFilter {
  /** 调用链：切换到指定应用 */
  appName?: string;
  /** 视图：要选中的维度 id / 展示名 */
  dimensions?: string[];
  filterMode?: EMode;
  /** 主机：按 IP / 主机名选中目标 */
  hostCloudId?: number | string;
  hostIp?: string;
  hostName?: string;
  /** 日志：语句模式关键词 */
  queryString?: string;
  /** 视图：滚动并激活的板块 */
  viewAnchor?: 'dimension-analysis';
  /** UI 模式筛选条件 */
  where?: IWhereItem[];
}

/** 右侧 AI 诊断 → 左侧详情 tab 的导航意图 */
export interface IDiagnosticNavigateIntent {
  filter?: IDiagnosticPanelFilter;
  /** 递增以强制重复触发同一意图 */
  nonce: number;
  tab: AlarmCenterPanelTabType;
}
