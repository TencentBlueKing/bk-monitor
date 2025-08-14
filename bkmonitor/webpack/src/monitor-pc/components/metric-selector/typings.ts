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

export interface CheckedboxListEvents {
  onChange: CheckedboxListVlaue;
}

export interface CheckedboxListProps {
  list: ICheckedboxList[];
  value: CheckedboxListVlaue;
}

export type CheckedboxListVlaue = Record<string, string[]>;

export interface ICheckedboxList {
  checked?: string[];
  children?: ICheckedboxList[];
  count?: number;
  id: string;
  name: string;
  show?: boolean;
}
export interface MetricPopoverEvents {
  onShowChange: boolean;
}

export interface MetricPopoverProps {
  show?: boolean;
  targetId: string;
  width?: number;
}
export type MetricSelectorEvents = MetricPopoverEvents & {
  onChecked: (obj: { checked: boolean; id: string }) => void;
  onSelected: MetricDetail;
};
export type MetricSelectorProps = MetricPopoverProps & {
  defaultScenario?: string;
  getMetricData?: TGetMetricData;
  isPromql?: boolean;
  metricId?: string;
  metricIds?: string[];
  metricKey?: string;
  multiple?: boolean;
  scenarioList?: any;
  type?: MetricType;
};
export type TGetMetricData = (
  params: Record<string, any>
) => any | Promise<{ metricList: IMetricDetail[] }> | { metricList: IMetricDetail[] };
