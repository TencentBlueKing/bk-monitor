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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getVariableValue } from 'monitor-api/modules/grafana';
import { NEW_NUMBER_CONDITION_METHOD_LIST, NEW_STRING_CONDITION_METHOD_LIST } from 'monitor-pc/constant/constant';

import UiSelector from '../../../../components/retrieval-filter/ui-selector';
import {
  type EMethod,
  type IFilterField,
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  ECondition,
  EFieldType,
} from '../../../../components/retrieval-filter/utils';
import CommonItem from '../components/common-form-item';
import { type IIssueConfig, LEVEL_LIST } from '../type';

import type { ICommonItem, MetricDetail } from '../typings/index';

import './issue-agg.scss';

interface IEvents {
  onChange?: IIssueConfig;
}

interface IProps {
  dimensions?: ICommonItem[];
  metricData?: MetricDetail[];
  readonly?: boolean;
  value?: IIssueConfig;
}

@Component({
  name: 'IssueAgg',
})
export default class IssueAgg extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];
  @Prop({ type: Object, default: () => null }) value: IIssueConfig;
  @Prop({ type: Array, default: () => [] }) dimensions: ICommonItem[];

  /** 根据 detectionConfig.data 中的 level 计算默认告警级别 */
  // get defaultLevels(): number[] {
  //   const levels = this.detectionConfig?.data?.map(item => item.level).filter(Boolean);
  //   // 去重并排序
  //   return [...new Set(levels)].sort((a, b) => a - b);
  // }

  localValue: IIssueConfig = {
    aggregate_dimensions: [],
    conditions: [],
    alert_levels: [],
  };

  /** 维度值缓存 */
  dimensionValueCache: Record<string, { id: string; name: string }[]> = {};

  /** 获取维度字段列表（用于条件选择器） */
  get filterFields(): IFilterField[] {
    return this.dimensions.map(item => ({
      alias: `${item.name}（${item.id}）`,
      is_option_enabled: true,
      name: String(item.id),
      type: EFieldType.keyword,
      supported_operations: (item?.type === 'number'
        ? NEW_NUMBER_CONDITION_METHOD_LIST
        : NEW_STRING_CONDITION_METHOD_LIST
      ).map(m => ({
        alias: m.name,
        value: m.id as EMethod,
      })),
    }));
  }

  get conditions() {
    return this.localValue.conditions.map(item => {
      const field = this.filterFields.find(f => f.name === item.key);
      const method = (field?.supported_operations || []).find(m => m.value === item.method);
      return {
        key: { id: field?.name || item.key, name: field?.alias || item.key },
        condition: {
          id: item.condition === 'and' ? ECondition.and : ECondition.or,
          name: item.condition === 'and' ? 'AND' : 'OR',
        },
        method: { id: method?.value || item.method, name: method?.alias || item.method },
        value: item.value.map(v => ({
          id: v,
          name: v,
        })),
      };
    });
  }

  created() {
    if (this.value) {
      this.localValue.aggregate_dimensions = this.value?.aggregate_dimensions || [];
      this.localValue.alert_levels = this.value?.alert_levels || [];
      this.localValue.conditions = this.value?.conditions || [];
    }
  }

  @Emit('change')
  handleChange() {
    return this.localValue;
  }

  /** 聚合维度变更 */
  handleDimensionsChange(val: string[]) {
    this.localValue.aggregate_dimensions = val;
    this.handleChange();
  }

  /** 条件变更 */
  handleConditionsChange(val: IFilterItem[]) {
    this.localValue.conditions = val.map(item => {
      return {
        key: item.key.id,
        method: item.method.id,
        condition: item.condition.id,
        value: item.value.map(v => v.id),
      };
    });
    this.handleChange();
  }

  /** 告警级别变更 */
  handleLevelsChange(val: number[]) {
    this.localValue.alert_levels = val;
    this.handleChange();
  }

  /** 获取维度值的方法 */
  async getValueFn(params: IGetValueFnParams): Promise<IWhereValueOptionsItem> {
    const field = params.fields?.[0];
    if (!field) {
      return { count: 0, list: [] };
    }

    // 检查缓存是否存在
    if (this.dimensionValueCache[field]) {
      // 使用前端搜索过滤
      const searchValue = params.where?.[0]?.value?.[0] as string;
      const cachedList = this.dimensionValueCache[field];
      if (searchValue) {
        const filteredList = cachedList.filter(
          item =>
            item.name?.toLowerCase().includes(searchValue.toLowerCase()) ||
            item.id?.toLowerCase().includes(searchValue.toLowerCase())
        );
        return { count: filteredList.length, list: filteredList };
      }
      return { count: cachedList.length, list: cachedList };
    }

    // 获取第一个有维度的指标的元数据
    const metricWithAggDim = this.metricData.find(m => m.agg_dimension?.length > 0);
    if (!metricWithAggDim) {
      return { count: 0, list: [] };
    }

    const { data_source_label, metric_field, data_type_label, result_table_id, index_set_id } = metricWithAggDim;
    if (!data_source_label || !metric_field || !data_type_label) {
      return { count: 0, list: [] };
    }

    const requestParams = {
      bk_biz_id: this.$store.getters.bizId,
      type: 'dimension',
      params: {
        data_source_label,
        data_type_label,
        field,
        metric_field,
        result_table_id: result_table_id || '',
        where: [],
        ...(data_source_label === 'bk_log_search' ? { index_set_id } : {}),
      },
    };

    try {
      const { data } = await getVariableValue(requestParams, { needRes: true });
      const result = Array.isArray(data) ? data.map(item => ({ id: item.value, name: item.label })) : [];
      // 缓存结果
      this.dimensionValueCache[field] = result;
      return {
        count: result.length,
        list: result,
      };
    } catch {
      return { count: 0, list: [] };
    }
  }

  render() {
    return (
      <div class='issue-agg-container'>
        <CommonItem
          title={this.$t('聚合维度')}
          isRequired
          show-semicolon
        >
          <bk-select
            class='dimension-select'
            v-model={this.localValue.aggregate_dimensions}
            behavior='simplicity'
            disabled={this.readonly}
            is-tag-width-limit={false}
            placeholder={this.$t('请选择聚合维度')}
            size='small'
            display-tag
            multiple
            searchable
            onChange={this.handleDimensionsChange}
          >
            {this.dimensions.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.id}
              >
                {`${item.name} (${item.id})`}
              </bk-option>
            ))}
          </bk-select>
        </CommonItem>
        <CommonItem
          title={this.$t('过滤条件')}
          show-semicolon
        >
          <UiSelector
            class='condition-select'
            scopedSlots={{
              addBtn: click => {
                return (
                  <div
                    class='cus-add-btn'
                    onClick={click}
                  >
                    <span class='icon-monitor icon-mc-add' />
                  </div>
                );
              },
            }}
            addBtnAlign={'right'}
            fields={this.filterFields}
            getValueFn={this.getValueFn}
            hasAllType={false}
            hasConditionChange={true}
            hasInput={false}
            kvTagHasHideBtn={false}
            value={this.conditions as unknown as IFilterItem[]}
            zIndex={9999}
            onChange={this.handleConditionsChange}
          />
        </CommonItem>
        <CommonItem
          title={this.$t('生效告警级别')}
          isRequired
          show-semicolon
        >
          <bk-checkbox-group
            class='levels-checkbox'
            v-model={this.localValue.alert_levels}
            onChange={this.handleLevelsChange}
          >
            {LEVEL_LIST.map(level => (
              <bk-checkbox
                key={level.id}
                value={level.id}
              >
                <i class={`icon-monitor ${level.icon}`} />
                {level.name}
              </bk-checkbox>
            ))}
          </bk-checkbox-group>
        </CommonItem>
      </div>
    );
  }
}
