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

import type {
  IMetricDetail,
  MetricDetail,
  MetricType,
} from '../../pages/strategy-config/strategy-config-set-new/typings';

export type TGetMetricData = (
  params: Record<string, any>
) => { metricList: IMetricDetail[] } | Promise<{ metricList: IMetricDetail[] }> | any;

export type MetricSelectorProps = {
  type?: MetricType;
  metricId?: string;
  scenarioList?: any;
  metricKey?: string;
  isPromql?: boolean;
  defaultScenario?: string;
  multiple?: boolean;
  metricIds?: string[];
  getMetricData?: TGetMetricData;
} & MetricPopoverProps;

export type MetricSelectorEvents = {
  onSelected: MetricDetail;
  onChecked: (obj: { checked: boolean; id: string }) => void;
} & MetricPopoverEvents;

export interface MetricPopoverProps {
  targetId: string;
  show?: boolean;
  width?: number;
}
export interface MetricPopoverEvents {
  onShowChange: boolean;
}

export type CheckedboxListVlaue = Record<string, string[]>;
export interface CheckedboxListProps {
  list: ICheckedboxList[];
  value: CheckedboxListVlaue;
}
export interface CheckedboxListEvents {
  onChange: CheckedboxListVlaue;
}
export interface ICheckedboxList {
  id: string;
  name: string;
  count?: number;
  checked?: string[];
  show?: boolean;
  children?: ICheckedboxList[];
}
