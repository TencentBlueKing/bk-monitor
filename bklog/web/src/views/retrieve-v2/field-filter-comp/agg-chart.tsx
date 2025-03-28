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

import { Component, Prop, Watch, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { RetrieveUrlResolver } from '@/store/url-resolver';
import _escape from 'lodash/escape';

import $http from '@/api';
import store from '@/store';

import './agg-chart.scss';

@Component
export default class AggChart extends tsc<object> {
  @Prop({ type: String, required: true }) fieldName: string;
  @Prop({ type: String, required: true }) fieldType: string;
  @Prop({ type: Boolean, default: false }) parentExpand: boolean;
  @Prop({ type: Object, required: true }) retrieveParams: any;
  @Prop({ type: Boolean, default: false }) isFrontStatistics: boolean;
  @Prop({ type: Object, default: () => ({}) }) statisticalFieldData: any;
  @Prop({ type: Number, default: 5 }) limit: number;
  showAllList = false;
  listLoading = false;
  mappingKay = {
    // is is not 值映射
    is: '=',
    'is not': '!=',
  };
  limitSize = 5;
  route = window.mainComponent.$route;
  fieldValueData = {
    name: '',
    columns: [],
    types: [],
    limit: 5,
    total_count: 0,
    field_count: 0,
    values: [],
  };
  t = window.mainComponent.$t.bind(window.mainComponent);
  get unionIndexList() {
    return store.getters.unionIndexList;
  }
  get isUnionSearch() {
    return store.getters.isUnionSearch;
  }
  get topFiveList() {
    const totalList = Object.entries(this.statisticalFieldData);
    totalList.sort((a, b) => Number(b[1]) - Number(a[1]));
    totalList.forEach(item => {
      const markList = item[0].toString().match(/(<mark>).*?(<\/mark>)/g) || [];
      if (markList.length) {
        item[0] = markList.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, '')).join(',');
      }
    });
    return this.showAllList ? totalList : totalList.filter((item, index) => index < 5);
  }
  get showFiveList() {
    return this.isFrontStatistics ? this.topFiveList : this.fieldValueData.values;
  }
  get showValidCount() {
    return this.isFrontStatistics ? this.statisticalFieldData.__validCount : this.fieldValueData.field_count;
  }
  get showTotalCount() {
    return this.isFrontStatistics ? this.statisticalFieldData.__totalCount : this.fieldValueData.total_count;
  }
  get watchQueryParams() {
    const { datePickerValue, ip_chooser, addition, timezone, keyword } = store.state.indexItem;
    return { datePickerValue, ip_chooser, addition, timezone, keyword };
  }

  @Watch('watchQueryParams', { deep: true })
  watchPicker() {
    if (this.isFrontStatistics) return;
    this.queryFieldFetchTopList(this.limitSize);
  }

  @Emit('distinctCount')
  emitDistinctCount(val) {
    return val;
  }

  mounted() {
    if (!this.isFrontStatistics) this.queryFieldFetchTopList(this.limit);
  }

  // 计算百分比
  computePercent(count) {
    const percentageNum = count / this.showTotalCount;
    // 当百分比 大于1 的时候 不显示后面的小数点， 若小于1% 则展示0.xx 保留两位小数
    const showPercentageStr = percentageNum >= 0.01 ? Math.round(+percentageNum.toFixed(2) * 100) : 0.01;
    return `${showPercentageStr}%`;
  }
  addCondition(operator, value) {
    if (this.fieldType === '__virtual__') return;

    const router = this.$router;
    const route = this.$route;
    // const store = this.$store;

    store.dispatch('setQueryCondition', { field: this.fieldName, operator, value: [value] }).then(() => {
      const query = { ...route.query };

      const resolver = new RetrieveUrlResolver({
        keyword: store.getters.retrieveParams.keyword,
        addition: store.getters.retrieveParams.addition,
      });

      Object.assign(query, resolver.resolveParamsToUrl());

      router.replace({
        query,
      });
    });
  }
  getIconPopover(operator, value) {
    if (this.fieldType === '__virtual__') return this.t('该字段为平台补充 不可检索');
    if (this.filterIsExist(operator, value)) return this.t('已添加过滤条件');
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
      const indexSetIDs = this.isUnionSearch
        ? this.unionIndexList
        : [window.__IS_MONITOR_COMPONENT__ ? this.route.query.indexId : this.route.params.indexId];
      this.listLoading = true;
      const data = {
        ...this.retrieveParams,
        agg_field: this.fieldName,
        limit,
        index_set_ids: indexSetIDs,
      };
      const res = await $http.request('retrieve/fieldFetchTopList', {
        data,
      });
      if (res.code === 0) {
        await this.$nextTick();
        this.emitDistinctCount(res.data.distinct_count);
        Object.assign(this.fieldValueData, res.data);
      }
    } catch (error) {
      console.error(error);
    } finally {
      this.listLoading = false;
    }
  }

  render() {
    return (
      <div
        class='retrieve-v2 field-data'
        v-bkloading={{ isLoading: this.listLoading }}
      >
        {!!this.showFiveList.length ? (
          <div>
            {/* <div class='title'>{this.t('字段内容分布')}</div> */}
            <ul class='chart-list'>
              {this.showFiveList.map(item => (
                <li class='chart-item'>
                  <div class='operation-container'>
                    <span
                      class={['bk-icon icon-enlarge-line', this.filterIsExist('is', item[0]) ? 'disable' : '']}
                      v-bk-tooltips={this.getIconPopover('=', item[0])}
                      onClick={() => this.addCondition('is', item[0])}
                    ></span>
                    <span
                      class={['bk-icon icon-narrow-line', this.filterIsExist('is not', item[0]) ? 'disable' : '']}
                      v-bk-tooltips={this.getIconPopover('!=', item[0])}
                      onClick={() => this.addCondition('is not', item[0])}
                    ></span>
                  </div>
                  <div class='chart-content'>
                    <div class='text-container'>
                      <div
                        class='text-value'
                        v-bk-overflow-tips
                      >
                        {item[0]}
                      </div>
                      <div class='percent-value'>
                        {<span>{item[1] + this.t('条')}</span>} {this.computePercent(item[1])}
                      </div>
                    </div>
                    <div class='percent-bar-container'>
                      <div
                        style={{ width: this.computePercent(item[1]) }}
                        class='percent-bar'
                      ></div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div class='error-container'>{!this.listLoading && this.t('暂无字段数据')}</div>
        )}
      </div>
    );
  }
}
