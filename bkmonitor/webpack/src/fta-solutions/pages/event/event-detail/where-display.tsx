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
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { getVariableValue } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils/utils';
import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from 'monitor-pc/constant/constant';
import {
  ICommonItem,
  IWhereItem,
  MetricDetail
} from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import './where-display.scss';

interface IProps {
  value: IWhereItem[];
  groupByList: ICommonItem[];
  metric: MetricDetail;
  allWhereValueMap?: Map<string, ICommonItem[]>;
  readonly?: boolean;
  allNames?: { [key: string]: string };
}
interface IEvent {
  onValueMapChange?: Map<string, ICommonItem[]>;
}
/**
 * 用于策略详情条件的数据展示
 */
@Component
export default class WhereDisplay extends tsc<IProps, IEvent> {
  /** where条件 */
  @Prop({ default: () => [], type: Array }) value: IWhereItem[];
  /** 维度列表 */
  @Prop({ default: () => [], type: Array }) groupByList: ICommonItem[];
  /** 指标数据 */
  @Prop({ type: Object }) metric: MetricDetail;
  /* 所有变量数据（避免重复调接口） */
  @Prop({ type: Map, default: () => new Map() }) allWhereValueMap: Map<string, ICommonItem[]>;
  /* 只读，无需调用接口获取数据 */
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  /* 只读情况下从父组件获取维度名 */
  @Prop({ default: () => ({}), type: Object }) allNames: any;

  /** 维度名 */
  whereNameMap: Map<string | number, string | TranslateResult> = new Map();

  /** 方法名 */
  methodNameMap: Map<string, string> = new Map();

  /** 条件可选项数据 */
  whereValueMap: Map<string, ICommonItem[]> = new Map();

  valueKey = random(8);

  created() {
    if (!this.readonly) {
      this.handleGetWhereOption();
      this.groupByList.forEach(item => this.whereNameMap.set(item.id, item.name));
    }
    const methodList = [...STRING_CONDITION_METHOD_LIST, ...NUMBER_CONDITION_METHOD_LIST];
    methodList.forEach(item => this.methodNameMap.set(item.id, item.name));
  }

  @Emit('valueMapChange')
  handleValueMap(mapObject: Map<string, ICommonItem[]>) {
    return mapObject;
  }

  /** 获取条件的可选项数据 */
  async handleGetWhereOption() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { data_source_label, data_type_label, metric_field, result_table_id } = this.metric;
    const promiseList = this.value.map(item => {
      const params = {
        params: {
          field: item.key,
          data_source_label,
          data_type_label,
          metric_field,
          result_table_id,
          where: []
        },
        type: 'dimension'
      };
      if (this.allWhereValueMap.get(item.key)) {
        this.whereValueMap.set(item.key, this.allWhereValueMap.get(item.key));
        return null;
      }
      return getVariableValue(params).then(res => {
        this.whereValueMap.set(
          item.key,
          res.map(set => ({ id: set.label, name: set.value }))
        );
        /* 将变量保存在父组件 */
        const valueMap = new Map(this.allWhereValueMap);
        valueMap.set(
          item.key,
          res.map(set => ({ id: set.label, name: set.value }))
        );
        this.handleValueMap(valueMap);
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
    return names.toString() || `${this.$t('空')}`;
  }

  getFieldName(item) {
    if (this.readonly) {
      return this.allNames[item?.key] || item.key;
    }
    return this.whereNameMap.get(item.key) || item.key;
  }

  render() {
    return (
      <span class='where-display-wrap'>
        {this.value.map((item, index) => (
          <span class='where-item'>
            {!!item.condition && !!index ? <span class='where-condition'>{` ${item.condition} `}</span> : undefined}
            <span class='where-field'>{` ${this.getFieldName(item)} `}</span>
            <span class='where-method'>{` ${this.methodNameMap.get(item.method) || item.method} `}</span>
            <span
              class='where-content'
              key={this.valueKey}
            >
              {this.handleValue(item.value, item.key)}
            </span>
          </span>
        ))}
      </span>
    );
  }
}
