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

import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ItemSkeleton from '@/skeleton/item-skeleton';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';
import DOMPurify from 'dompurify';
import { escape as _escape } from 'lodash-es';

import { BK_LOG_STORAGE } from '../../../store/store.type';
import $http from '@/api';
import store from '@/store';

import './agg-chart.scss';

// 缓存操作符映射
const OPERATOR_MAPPING = {
  is: '=',
  'is not': '!=',
};

@Component
export default class AggChart extends tsc<object> {
  @Prop({ type: String, required: true }) fieldName!: string;
  @Prop({ type: String, required: true }) fieldType!: string;
  @Prop({ type: Boolean, default: false }) parentExpand!: boolean;
  @Prop({ type: Object, required: true }) retrieveParams!: any;
  @Prop({ type: Boolean, default: false }) isFrontStatistics!: boolean;
  @Prop({ type: Object, default: () => ({}) }) statisticalFieldData!: any;
  @Prop({ type: Number, default: 5 }) limit!: number;
  @Prop({ type: Array }) colorList!: string[];

  // 状态变量
  showAllList = false;
  listLoading = false;
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
  // 获取翻译函数
  t = window.mainComponent.$t.bind(window.mainComponent);

  // 缓存计算
  private cachedTopFiveList: [string, number][] = [];
  private cachedShowFiveList: [string, number][] = [];
  private cachedShowValidCount = 0;
  private cachedShowTotalCount = 0;

  get unionIndexList() {
    return store.getters.unionIndexList;
  }

  get isUnionSearch() {
    return store.getters.isUnionSearch;
  }

  // 优化计算属性：缓存计算结果
  get topFiveList() {
    if (!this.cachedTopFiveList.length) {
      const totalList = Object.entries(this.statisticalFieldData)
        .filter(([key]) => !['__validCount', '__totalCount'].includes(key))
        .sort((a, b) => Number(b[1]) - Number(a[1]));

      for (const item of totalList) {
        const markList = item[0].toString().match(/(<mark>).*?(<\/mark>)/g) || [];
        if (markList.length) {
          item[0] = markList.map(m => m.replace(/<mark>/g, '').replace(/<\/mark>/g, '')).join(',');
        }
      }

      this.cachedTopFiveList = this.showAllList ? totalList : totalList.slice(0, 5);
    }
    return this.cachedTopFiveList;
  }

  get showFiveList() {
    if (!this.cachedShowFiveList.length) {
      this.cachedShowFiveList = this.isFrontStatistics ? this.topFiveList : this.fieldValueData.values;
    }
    return this.cachedShowFiveList;
  }

  get showValidCount() {
    if (!this.cachedShowValidCount) {
      this.cachedShowValidCount = this.isFrontStatistics
        ? this.statisticalFieldData.__validCount || 0
        : this.fieldValueData.field_count;
    }
    return this.cachedShowValidCount;
  }

  get showTotalCount() {
    if (!this.cachedShowTotalCount) {
      this.cachedShowTotalCount = this.isFrontStatistics
        ? this.statisticalFieldData.__totalCount || 0
        : this.fieldValueData.total_count;
    }
    return this.cachedShowTotalCount;
  }

  get watchQueryParams() {
    const { datePickerValue, ip_chooser, addition, timezone, keyword } = store.state.indexItem;
    return { datePickerValue, ip_chooser, addition, timezone, keyword };
  }

  /**
   * 当前查询模式 0：ui，1:sql
   */
  get searchMode() {
    return store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE];
  }

  @Watch('watchQueryParams', { deep: true })
  watchPicker() {
    if (this.isFrontStatistics) {
      return;
    }
    this.queryFieldFetchTopList(this.limitSize);
  }

  @Emit('distinctCount')
  emitDistinctCount(val: number) {
    return val;
  }

  mounted() {
    if (!this.isFrontStatistics) {
      this.queryFieldFetchTopList(this.limit);
    }
  }

  // 使用CSS变量优化样式处理
  getCssVar(index: number) {
    return {
      '--bar-bg-color': this.colorList?.[index % this.colorList.length] || '#5AB8A8',
      '--percent-text-color': this.colorList?.length ? '#979ba5' : '#5AB8A8',
    };
  }

  getPercentValue(count: number) {
    if (!this.showTotalCount) {
      return '0%';
    }
    // 当百分比 大于1 的时候 不显示后面的小数点， 若小于1% 则展示0.xx 保留两位小数
    const percentage = (count / this.showTotalCount) * 100;
    return `${percentage}%`;
  }

  // 优化百分比计算
  computePercent(count: number) {
    if (!this.showTotalCount) {
      return '0%';
    }
    // 当百分比 大于1 的时候 不显示后面的小数点， 若小于1% 则展示0.xx 保留两位小数
    const percentage = (count / this.showTotalCount) * 100;
    return percentage >= 1 ? `${Math.round(percentage)}%` : '<1%';
  }

  // 添加查询条件
  addCondition = (operator: string, value: any, fieldName: string) => {
    if (this.fieldType === '__virtual__') {
      return;
    }

    const router = this.$router;
    const route = this.$route;
    const mappedOperator = OPERATOR_MAPPING[operator] || operator;

    store
      .dispatch('setQueryCondition', {
        field: fieldName,
        operator: mappedOperator,
        value: [value],
      })
      .then(() => {
        const resolver = new RetrieveUrlResolver({
          keyword: store.getters.retrieveParams.keyword,
          addition: store.getters.retrieveParams.addition,
        });

        router
          .replace({
            query: {
              ...route.query,
              ...resolver.resolveParamsToUrl(),
            },
          })
          .then(() => {
            RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
          });
      });
  };

  // 获取工具提示内容
  getIconPopover = (operator: string, value: any, fieldName: string) => {
    if (this.fieldType === '__virtual__') {
      return this.t('该字段为平台补充 不可检索');
    }
    if (this.filterIsExist(operator, value, fieldName)) {
      return this.t('已添加过滤条件');
    }
    return `${fieldName} ${operator} ${_escape(value)}`;
  };

  // 检查过滤条件是否已存在
  filterIsExist = (operator: string, value: any, fieldName: string) => {
    if (this.fieldType === '__virtual__') {
      return true;
    }

    if (this.searchMode === 0) {
      const mappedOperator = OPERATOR_MAPPING[operator] || operator;
      return store.getters.retrieveParams?.addition?.some(addition => {
        return (
          addition.field === fieldName &&
          addition.operator === mappedOperator &&
          addition.value.toString() === value.toString()
        );
      });
    }

    const formatJsonString = formatResult => {
      if (typeof formatResult === 'string') {
        return DOMPurify.sanitize(formatResult);
      }

      return formatResult;
    };

    // biome-ignore lint/nursery/noShadow: reason
    const getSqlAdditionMappingOperator = ({ operator, field }) => {
      const textType = this.fieldType;

      // biome-ignore lint/nursery/noShadow: reason
      const formatValue = value => {
        let formatResult = value;
        if (['text', 'string', 'keyword'].includes(textType)) {
          if (Array.isArray(formatResult)) {
            formatResult = formatResult.map(formatJsonString);
          } else {
            formatResult = formatJsonString(formatResult);
          }
        }

        return formatResult;
      };

      const mappingKey = {
        // is is not 值映射
        is: val => `${field}: "${formatValue(val)}"`,
        'is not': val => `NOT ${field}: "${formatValue(val)}"`,
        '=': val => `${field}: "${formatValue(val)}"`,
        '!=': val => `NOT ${field}: "${formatValue(val)}"`,
      };

      return mappingKey[operator] ?? operator; // is is not 值映射
    };
    const keyword = getSqlAdditionMappingOperator({ operator, field: fieldName })?.(value) ?? value;
    return store.getters.retrieveParams?.keyword.indexOf(keyword) >= 0;
  };
  // 查询字段数据
  async queryFieldFetchTopList(limit = 5) {
    if (this.listLoading) {
      return;
    }
    this.limitSize = limit;
    this.listLoading = true;
    this.resetCache();
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

      const res = await $http.request('retrieve/fieldFetchTopList', { data });

      if (res.code === 0) {
        this.emitDistinctCount(res.data.distinct_count);
        Object.assign(this.fieldValueData, res.data);
      }
    } catch (error) {
      console.error(error);
    } finally {
      this.listLoading = false;
    }
  }

  // 重置缓存
  resetCache() {
    this.cachedTopFiveList = [];
    this.cachedShowFiveList = [];
    this.cachedShowValidCount = 0;
    this.cachedShowTotalCount = 0;
  }

  // 渲染函数
  render() {
    const hasData = !!this.showFiveList.length;

    return (
      <div class='retrieve-v2 field-data'>
        {this.listLoading ? (
          <ItemSkeleton
            columns={2}
            rows={this.limit > 6 ? Math.ceil(this.limit / 8) : 2}
            widths={['10%', '90%']}
          />
        ) : hasData ? (
          <ul class='chart-list'>
            {this.showFiveList.map((item, index) => {
              const [value, count] = item;
              const percent = this.computePercent(count);
              const percentValue = this.getPercentValue(count);
              const isFiltered = this.filterIsExist('is', value, this.fieldName);
              const isNotFiltered = this.filterIsExist('is not', value, this.fieldName);

              return (
                <li
                  key={`${index}-${value}`}
                  style={this.getCssVar(index)}
                  class='chart-item'
                >
                  <div class='operation-container'>
                    <span
                      class={['bk-icon icon-enlarge-line', { disable: isFiltered }]}
                      v-bk-tooltips={this.getIconPopover('=', value, this.fieldName)}
                      onClick={() => !isFiltered && this.addCondition('is', value, this.fieldName)}
                    />
                    <span
                      class={['bk-icon icon-narrow-line', { disable: isNotFiltered }]}
                      v-bk-tooltips={this.getIconPopover('!=', value, this.fieldName)}
                      onClick={() => !isNotFiltered && this.addCondition('is not', value, this.fieldName)}
                    />
                  </div>
                  <div class='chart-content'>
                    <div class='text-container'>
                      <div
                        class='text-value'
                        v-bk-overflow-tips
                      >
                        {value}
                      </div>
                      <div class='percent-value'>
                        <span>
                          {count}
                          {this.t('条')}
                        </span>{' '}
                        {percent}
                      </div>
                    </div>
                    <div class='percent-bar-container'>
                      <div
                        style={{ width: percentValue }}
                        class='percent-bar'
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <div class='error-container'>{this.t('暂无字段数据')}</div>
        )}
      </div>
    );
  }
}
