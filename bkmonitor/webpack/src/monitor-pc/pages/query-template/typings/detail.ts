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

import type { QueryVariablesTransformResult } from '../components/utils/query-variable-tool';
import type { AggCondition, AggFunction, IVariableSubmitParams } from './index';

export type ConditionDetailTagItem = Omit<AggCondition, 'value'> & { value: QueryVariablesTransformResult<string>[] };
export interface IDetailEvents {
  onClose: () => void;
}

export interface IDetailProps {
  visible: boolean;
}

export interface IQueryConfig {
  data_source_label: string;
  data_type_label: string;
  functions: (AggFunction | string)[];
  group_by: string[];
  metric_id: string;
  metrics: { alias: string; field: string; method: string }[];
  table: string;
  where: (AggCondition | string)[];
}

export interface QueryTemplateDetail {
  alias: string;
  can_delete: boolean;
  can_edit: boolean;
  description: string;
  expression: string;
  functions: (AggFunction | string)[];
  id: number;
  name: string;
  query_configs: IQueryConfig[];
  space_scope: number[];
  unit: string;
  variables: IVariableSubmitParams[];
}
