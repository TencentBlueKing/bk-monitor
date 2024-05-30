/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import { Component, Prop, Inject, Watch } from 'vue-property-decorator';
import _escape from 'lodash/escape';
import $http from '@/api';
import './agg-chart.scss';

@Component
export default class AggChart extends tsc<{}> {
  @Prop({ type: String, required: true }) fieldName: string;
  @Prop({ type: String, required: true }) fieldType: string;
  @Prop({ type: Boolean, default: false }) parentExpand: boolean;
  @Prop({ type: Object, required: true }) retrieveParams: any;
  @Prop({ type: Array, required: true }) datePickerValue: Array<string | number>;

  @Inject('addFilterCondition') addFilterCondition;

  showAllList = false;
  shouldShowMore = false;
  listLoading = false;
  mappingKay = {
    // is is not 值映射
    is: '=',
    'is not': '!='
  };
  limitSize = 5;
  fieldValueData = {
    name: '',
    columns: [],
    types: [],
    limit: 5,
    total_count: 0,
    field_count: 0,
    values: []
  };

  get unionIndexList() {
    return this.$store.getters.unionIndexList;
  }
  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }

  mounted() {
    this.queryFieldFetchTopList();
  }

  @Watch('datePickerValue', { deep: true })
  watchPicker() {
    this.queryFieldFetchTopList(this.limitSize);
  }

  // 计算百分比
  computePercent(count) {
    const percentageNum = count / this.fieldValueData.field_count;
    // 当百分比 大于1 的时候 不显示后面的小数点， 若小于1% 则展示0.xx 保留两位小数
    const showPercentageStr =
      percentageNum >= 0.01 ? Math.round(+percentageNum.toFixed(2) * 100) : (percentageNum * 100).toFixed(2);
    return `${showPercentageStr}%`;
  }
  addCondition(operator, value) {
    if (this.fieldType === '__virtual__') return;
    this.addFilterCondition(this.fieldName, operator, value);
  }
  getIconPopover(operator, value) {
    if (this.fieldType === '__virtual__') return this.$t('该字段为平台补充 不可检索');
    if (this.filterIsExist(operator, value)) return this.$t('已添加过滤条件');
    return `${this.fieldName} ${operator} ${_escape(value)}`;
  }
  filterIsExist(operator, value) {
    if (this.fieldType === '__virtual__') return true;
    if (this.retrieveParams?.addition.length) {
      if (operator === 'not') operator = 'is not';
      return this.retrieveParams.addition.some(addition => {
        return (
          addition.field === this.fieldName &&
          addition.operator === (this.mappingKay[operator] ?? operator) && // is is not 值映射
          addition.value.toString() === value.toString()
        );
      });
    }
    return false;
  }
  async queryFieldFetchTopList(limit = 5) {
    this.limitSize = limit;
    try {
      const indexSetIDs = this.isUnionSearch ? this.unionIndexList : [this.$route.params.indexId];
      this.listLoading = true;
      const data = {
        ...this.retrieveParams,
        agg_field: this.fieldName,
        limit,
        index_set_ids: indexSetIDs
      };
      const res = await $http.request('retrieve/fieldFetchTopList', {
        data
      });
      if (res.code === 0) {
        await this.$nextTick();
        this.shouldShowMore = res.data.distinct_count > 5;
        Object.assign(this.fieldValueData, res.data);
      }
    } catch (error) {
    } finally {
      this.listLoading = false;
    }
  }

  render() {
    return (
      <div
        class='field-data'
        v-bkloading={{ isLoading: this.listLoading }}
      >
        <div class='title'>
          <i18n path='{0}/{1}条记录中数量排名前 {2} 的数据值'>
            <span>{this.fieldValueData.field_count}</span>
            <span>{this.fieldValueData.total_count}</span>
            <span>{this.limitSize}</span>
          </i18n>
        </div>
        <ul class='chart-list'>
          {this.fieldValueData.values.map(item => (
            <li class='chart-item'>
              <div class='chart-content'>
                <div class='text-container'>
                  <div
                    v-bk-overflow-tips
                    class='text-value'
                  >
                    {item[0]}
                  </div>
                  <div class='percent-value'>{this.computePercent(item[1])}</div>
                </div>
                <div class='percent-bar-container'>
                  <div
                    class='percent-bar'
                    style={{ width: this.computePercent(item[1]) }}
                  ></div>
                </div>
              </div>
              <div class='operation-container'>
                <span
                  v-bk-tooltips={this.getIconPopover('=', item[0])}
                  class={['bk-icon icon-enlarge-line', this.filterIsExist('is', item[0]) ? 'disable' : '']}
                  onClick={() => this.addCondition('is', item[0])}
                ></span>
                <span
                  v-bk-tooltips={this.getIconPopover('!=', item[0])}
                  class={['bk-icon icon-narrow-line', this.filterIsExist('is not', item[0]) ? 'disable' : '']}
                  onClick={() => this.addCondition('is not', item[0])}
                ></span>
              </div>
            </li>
          ))}
          {!this.showAllList && this.shouldShowMore && (
            <li class='more-item'>
              <span
                onClick={() => {
                  this.showAllList = !this.showAllList;
                  this.queryFieldFetchTopList(100);
                }}
              >
                {this.$t('更多')}
              </span>
            </li>
          )}
        </ul>
      </div>
    );
  }
}
