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
  K8SPerformanceMetricUnitMap,
  K8sTableColumnKeysEnum,
  SceneEnum,
} from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';

import type { EchartSeriesItem, SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';

export interface AlertK8sEchartSeriesItem extends Omit<EchartSeriesItem, 'data' | 'raw_data'> {
  alias?: string;
  connectNulls: boolean;
  data?: EchartSeriesData[];
  lineStyle?: EchartSeriesLineStyle;
  markPoint?: EchartSeriesMarkPoint;
  sampling?: string;
  showAllSymbol?: 'auto' | boolean;
  showSymbol?: boolean;
  smooth?: boolean | number;
  smoothMonotone?: string;
  z?: number;
  raw_data?: SeriesItem & {
    maxMinValues?: {
      max: number;
      min: number;
    };
  };
}

export interface AlertK8SMetricItem {
  children?: AlertK8SMetricItem[];
  count?: number;
  id: string;
  name: string;
  show_chart?: boolean;
  unit?: string;
  unsupported_resource?: string[];
}

export interface AlertK8SSeriesItem extends SeriesItem {
  name?: string;
}

export type AlertK8sTargetItem = Partial<Record<K8sTableColumnKeysEnum, string>>;

export interface AlertK8sTargetResult {
  resource_type: K8sTableColumnKeysEnum;
  target_list: AlertK8sTargetItem[];
}
export interface EchartSeriesData {
  value?: number;
}

export interface EchartSeriesLineStyle {
  color?: string;
  type?: 'dashed' | 'dotted' | 'solid';
  width?: number;
}

export interface EchartSeriesMarkPoint {
  data?: {
    coord?: [number, number];
    name?: string;
    value?: number;
  }[];
}

export { K8SPerformanceMetricUnitMap, K8sTableColumnKeysEnum, SceneEnum };
