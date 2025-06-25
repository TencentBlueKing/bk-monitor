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

import { isEn } from '@/i18n/i18n';
import { listAlertTags } from 'monitor-api/modules/alert';

import { AlarmType } from '../typings';

import type {
  CommonFilterParams,
  QuickFilterItem,
  AnalysisFieldAggItem,
  AnalysisTopNDataResponse,
  AlertTableItem,
  ActionTableItem,
  FilterTableResponse,
  IncidentTableItem,
  TableColumnItem,
} from '../typings';
import type { IFilterField } from '@/components/retrieval-filter/typing';

export abstract class AlarmService<S = AlarmType> {
  isEn = false;
  abstract readonly storageKey: string;
  constructor(public scenes: S = AlarmType.ALERT as S) {
    this.isEn = isEn;
  }
  /**
   * @description: 所有表格列配置 类型继承自 @tdesign/table 的 TableCol 类型
   */
  abstract get allTableColumns(): TableColumnItem[];
  /**
   * @description: 告警分析字段列表
   */
  abstract get analysisFields(): string[];

  /**
   * @description: UI 模式检索字段列表
   */
  abstract get filterFields(): IFilterField[];
  // /**
  //  * @description: 默认表格列字段
  //  */
  // abstract get defaultTableFields(): string[];
  /**
   * @description: 获取告警分析维度字段列表
   * @param {Partial<CommonFilterParams>} params
   */
  async getAnalysisDimensionFields(params: Partial<CommonFilterParams>): Promise<Omit<QuickFilterItem, 'children'>[]> {
    if (this.scenes !== AlarmType.ALERT) {
      return [];
    }
    const data = await listAlertTags({
      ...params,
    }).catch(() => []);
    return data;
  }
  /**
   * @description: 获取告警分析 topN 数据
   * @param {Partial<CommonFilterParams>} params
   * @param {boolean} isAll 是否获取全部数据
   */
  abstract getAnalysisTopNData(
    params: Partial<CommonFilterParams> & { fields: string[] },
    isAll?: boolean
  ): Promise<AnalysisTopNDataResponse<AnalysisFieldAggItem>>;

  /**
   * @description: 获取筛选的 table 数据
   * @param {Partial<CommonFilterParams>} params
   */
  abstract getFilterTableList<
    T = S extends AlarmType.ALERT ? AlertTableItem : S extends AlarmType.INCIDENT ? IncidentTableItem : ActionTableItem,
  >(params: Partial<CommonFilterParams>): Promise<FilterTableResponse<T>>;

  /**
   * @description: 获取快速筛选列表
   * @param {Partial<CommonFilterParams>} params
   */
  abstract getQuickFilterList(params: Partial<CommonFilterParams>): Promise<QuickFilterItem[]>;
}
