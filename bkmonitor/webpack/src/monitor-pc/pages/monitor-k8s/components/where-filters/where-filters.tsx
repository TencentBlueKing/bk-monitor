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

import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CancelToken } from 'monitor-api/cancel';
import { getSceneViewDimensionValue } from 'monitor-api/modules/scene_view';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import ConditionInput, {
  type IConditionItem,
} from '../../../../pages/strategy-config/strategy-config-set-new/monitor-data/condition-input';

import type { IViewOptions } from '../../typings/book-mark';
import type { ICommonItem } from 'fta-solutions/pages/event/typings/event';
import type { VariableModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import './where-filters.scss';

export interface IWhereFiltersProps {
  panel: VariableModel;
  variableName: string;
}
export interface IWhereFiltersEvent {
  onChange: (value: IConditionItem[]) => void;
}
@Component
export default class WhereFilters extends tsc<IWhereFiltersProps, IWhereFiltersEvent> {
  /** 图表接口数据 */
  @Prop({ type: Object, required: true }) panel: VariableModel;
  @Prop({ type: String, default: 'custom_metric_filters' }) variableName: string;
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('dashboardId') readonly dashboardId!: string;
  loading = false;
  cancelToken = null;
  dimensionList: ICommonItem[] = [];
  value = [];
  created() {
    try {
      const value = this.viewOptions[this.variableName];
      this.value = Array.isArray(value) ? value : JSON.parse(this.viewOptions[this.variableName]);
    } catch {
      this.value = [];
    }
    this.getPanelData();
  }
  async getPanelData() {
    if (this.panel?.targets?.[0]) {
      this.loading = true;
      const [item] = this.panel.targets;
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.viewOptions.filters,
        ...this.viewOptions.variables,
      });
      if (this.cancelToken) {
        this.cancelToken?.();
        this.cancelToken = null;
      }
      const data = await (this as any).$api[item.apiModule]
        [item.apiFunc](
          {
            ...variablesService.transformVariables(item.data),
          },
          {
            cancelToken: new CancelToken(cb => (this.cancelToken = cb)),
          }
        )
        .catch(() => []);
      this.dimensionList = data;
    }
  }
  async getDimensionValue(field: string) {
    return await getSceneViewDimensionValue({
      field: field,
      id: this.dashboardId,
      scene_id: this.$route.query?.sceneId,
      type: this.$route.query?.sceneType,
      apm_app_name: this.viewOptions.filters?.app_name,
      apm_service_name: this.viewOptions.filters?.service_name,
    }).catch(() => []);
  }
  handleConditionChange(condition: IConditionItem[]) {
    const value = this.value?.filter(item => item.value?.length);
    const newValue = condition.filter(item => item.value?.length);
    if (JSON.stringify(value) === JSON.stringify(newValue)) return;
    this.value = structuredClone(condition);
    this.$emit(
      'change',
      condition.filter(item => item.value?.length)
    );
  }
  /**
   * 用于适配初始化 data ready 后 返回初始化值
   */
  async handleGetOptionsList() {
    return {
      [this.variableName]: structuredClone(this.value),
    };
  }
  render() {
    return (
      <div class='where-filters'>
        <ConditionInput
          conditionList={structuredClone(this.value)}
          dimensionsList={this.dimensionList}
          getDataApi={this.getDimensionValue}
          title=''
          onChange={this.handleConditionChange}
        />
      </div>
    );
  }
}
