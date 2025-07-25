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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getVariableValue } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils/utils';

import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from '../../../../constant/constant';

import type { ICommonItem, IWhereItem, MetricDetail } from '../../strategy-config-set-new/typings';
import type { TranslateResult } from 'vue-i18n';

import './where-display.scss';

interface IProps {
  groupByList: ICommonItem[];
  metric: MetricDetail;
  value: IWhereItem[];
}
/**
 * 用于策略详情条件的数据展示
 */
@Component
export default class WhereDisplay extends tsc<IProps> {
  /** where条件 */
  @Prop({ default: () => [], type: Array }) value: IWhereItem[];
  /** 维度列表 */
  @Prop({ default: () => [], type: Array }) groupByList: ICommonItem[];
  /** 指标数据 */
  @Prop({ type: Object }) metric: MetricDetail;

  /** 维度名 */
  whereNameMap: Map<number | string, string | TranslateResult> = new Map();

  /** 方法名 */
  methodNameMap: Map<string, string> = new Map();

  /** 条件可选项数据 */
  whereValueMap: Map<string, ICommonItem[]> = new Map();

  valueKey = random(8);

  created() {
    this.handleGetWhereOption();
    this.groupByList.forEach(item => this.whereNameMap.set(item.id, item.name));
    const methodList = [...STRING_CONDITION_METHOD_LIST, ...NUMBER_CONDITION_METHOD_LIST];
    methodList.forEach(item => this.methodNameMap.set(item.id, item.name));
  }

  /** 获取条件的可选项数据 */
  async handleGetWhereOption() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { data_source_label, data_type_label, metric_field, result_table_id, rawDimensions, index_set_id } =
      this.metric;
    const promiseList = this.value
      .filter(item => rawDimensions.some(dim => dim.is_dimension !== false && dim.id === item.key))
      .map(item => {
        const params = {
          params: Object.assign(
            {
              field: item.key,
              data_source_label,
              data_type_label,
              metric_field,
              result_table_id,
              where: [],
            },
            data_source_label === 'bk_log_search'
              ? {
                  index_set_id,
                }
              : {}
          ),
          type: 'dimension',
        };
        return getVariableValue(params).then(res => {
          this.whereValueMap.set(
            item.key,
            res.map(set => ({ id: set.label, name: set.value }))
          );
        });
      });
    await Promise.all(promiseList);
    this.valueKey = random(8);
  }

  /** 处理条件值 */
  handleValue(value, key) {
    const options = this.whereValueMap.get(key) || [];
    const names = value.map(val => {
      const item = options.find(item => item.id === val);
      return item?.name || val;
    });
    return names.toString() || this.$t('- 空 -');
  }

  render() {
    return (
      <span class='where-display-wrap'>
        {this.value.map((item, index) => (
          <span
            key={index}
            class='where-item'
          >
            {!!item.condition && !!index ? <span class='where-condition'>{` ${item.condition} `}</span> : undefined}
            <span
              class='where-field'
              v-bk-tooltips={{
                content: item.key,
                trigger: 'mouseenter',
                zIndex: 9999,
                offset: '0, 6',
                boundary: document.body,
                allowHTML: false,
              }}
            >{` ${this.whereNameMap.get(item.key) || item.key} `}</span>
            <span class='where-method'>{` ${this.methodNameMap.get(item.method) || item.method} `}</span>
            <span
              key={this.valueKey}
              class='where-content'
            >
              {this.handleValue(item.value, item.key)}
            </span>
          </span>
        ))}
      </span>
    );
  }
}
