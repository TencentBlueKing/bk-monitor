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

import { deepClone } from '../../../../monitor-common/utils/utils';
import { recheckInterval } from '../../../../monitor-ui/chart-plugins/utils';
import CycleInput from '../../../components/cycle-input/cycle-input';
import { IntervalType } from '../../../components/cycle-input/typings';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { METHOD_LIST } from '../../../constant/constant';
import SimpleConditionInput from '../../alarm-shield/components/simple-condition-input';
// import ConditionInput from '../../strategy-config/strategy-config-set-new/monitor-data/condition-input';
import FunctionSelect from '../../strategy-config/strategy-config-set-new/monitor-data/function-select';
import { DataRetrievalQueryItem, IDataRetrievalItem, IDataRetrievalView } from '../typings';

import './data-retrieval-item.scss';

@Component
export default class DataRetrievalItem extends tsc<IDataRetrievalItem.IProps, IDataRetrievalItem.IEvent> {
  @Prop({ default: '', type: [String, Object] }) value: IDataRetrievalItem.IValue;
  @Prop({ default: () => [], type: Array }) scenarioList: any;
  @Prop({ type: Object }) compareValue: IDataRetrievalView.ICompareValue;
  @Prop({ type: Number }) index: IDataRetrievalItem.IProps['index'];

  /** 本地数据 */
  localValue: DataRetrievalQueryItem = null;

  /** 实时模式 */
  isRealTimeModel = false;

  /** 指标名展示 */
  get metricValStr() {
    let value = '';
    if (this.localValue.result_table_label_name) {
      const {
        result_table_label_name: resultTableLabelName,
        related_name: relatedName,
        result_table_name: resultTableName,
        metric_field_name: metricFieldName
      } = this.localValue as DataRetrievalQueryItem;
      value = `${resultTableLabelName}/${relatedName}/${resultTableName}/${metricFieldName}`;
    }
    return value;
  }

  /** 计算公式列表 */
  get methodList(): IDataRetrievalItem.IAggMethodList[] {
    const curMethod = this.localValue.aggMethodList;
    return curMethod.length ? curMethod : METHOD_LIST;
  }

  /** 是否为空条件 */
  get whereIsEmpt() {
    return !this.localValue.agg_condition[0]?.key;
  }

  /** 指标支持的维度id */
  get groupByMap() {
    return this.localValue.dimensions.map(item => item.id);
  }

  /** 维度可选项 */
  get metricGroupByList() {
    if (this.localValue.isNullMetric) {
      return this.localValue.agg_dimension.map(item => ({ id: item, name: item }));
    }
    /** 处理无效维度展示 */
    const newGroupBy = deepClone(this.localValue.dimensions);
    this.localValue.agg_dimension.forEach(id => {
      /** 不支持的维度展示维度id */
      if (!this.groupByMap.includes(id)) {
        newGroupBy.push({
          id,
          name: id
        });
      }
    });
    return newGroupBy;
  }

  /** 条件维度可选项 */
  get metricWhereGroupBy() {
    if (this.localValue.isNullMetric) {
      return this.localValue.agg_condition.map(({ key: id }) => ({ id, name: id }));
    }
    /** 处理条件出现不支持的维度 */
    const newGroupBy = deepClone(this.localValue.rawDimensions);
    // this.localValue.agg_condition.forEach(({ key: id }) => {
    //   if (!this.groupByMap.includes(id)) {
    //     newGroupBy.push({
    //       id,
    //       name: id
    //     });
    //   }
    // });
    return newGroupBy;
  }

  @Watch('value', { immediate: true })
  valueChange(val: DataRetrievalQueryItem) {
    this.localValue = deepClone(val) as DataRetrievalQueryItem;
  }

  @Watch('compareValue.tools.timeRange')
  timeRangeChange(v) {
    const [startTime, endTime] = handleTransformToTimestamp(v);
    recheckInterval(this.localValue.agg_interval, endTime - startTime, this.localValue.collect_interval);
    // this.localValue.agg_interval
  }

  @Emit('change')
  emitChange(type?: IDataRetrievalItem.emitType): IDataRetrievalItem.onChange {
    return {
      type,
      value: this.localValue
    };
  }

  /**
   * @description: 清空指标
   */
  handleClearMerticVal() {
    this.$emit('clearMetric');
  }

  /**
   * 展开/隐藏 指标选择器
   */
  @Emit('showMetricSelector')
  handleShowMetricSelector(val = true) {
    return val;
  }

  /**
   * @description: 组件loading
   * @return {boolean}
   */
  @Emit('loadingChange')
  handleLoadingChange(loading: boolean) {
    return loading;
  }

  /**
   * @description: 条件参数值更新
   * @param {*} condition 条件
   */
  handleConditionChaneg(condition) {
    this.localValue.agg_condition = condition;
    this.emitChange('where');
  }

  /**
   * @description: 清除条件值
   */
  handleClearWhereValue() {
    this.emitChange('where-clear-value');
  }
  handleIntervalChange(v: IntervalType) {
    this.localValue.agg_interval = v as any;
    this.emitChange();
  }
  /**
   * @description: agg_method change
   * @param {string} v agg_method
   * @return {*}
   */
  handleMethodChange(v: string) {
    if (v.toLocaleUpperCase() === 'SUM' && this.localValue.agg_interval === 'auto') {
      this.localValue.agg_interval = 60;
    }
    this.emitChange();
  }

  /** 维度可选项 */
  aggDimensionOptionTpl(item) {
    return (
      <div class='agg-dim-option-item'>
        <span
          v-bk-tooltips={{
            content: item.id,
            placement: 'right',
            zIndex: 9999,
            boundary: document.body,
            allowHTML: false
          }}
        >
          {item.name}
        </span>
      </div>
    );
  }

  /** 维度已选项目 */
  aggDimensionTagTpl(node) {
    return (
      <div class='tag'>
        <span
          class='text'
          v-bk-tooltips={{
            content: node.id,
            trigger: 'mouseenter',
            zIndex: 9999,
            offset: '0, 6',
            boundary: document.body,
            allowHTML: false
          }}
        >
          {node.name}
        </span>
      </div>
    );
  }

  render() {
    return (
      <div class='data-retrieval-item-wrap'>
        <div class='query-item-wrap'>
          <div class='query-item-label'>{this.$t('指标')}</div>
          <div
            class='query-item-content'
            onClick={() => this.handleShowMetricSelector(true)}
          >
            <bk-input
              class='metric-selector-target'
              ref='metricInput'
              placeholder={this.$t('选择')}
              value={this.metricValStr}
              clearable={true}
              readonly
              id={`_metric_item_index_${this.index}`}
              onClear={this.handleClearMerticVal}
            />
          </div>
        </div>
        {this.metricValStr
          ? [
              <div class='query-item-group'>
                <div class='query-item-wrap flex-1'>
                  <div class='query-item-label'>{this.$t('汇聚方法')}</div>
                  <div class='query-item-content'>
                    <bk-select
                      vModel={this.localValue.agg_method}
                      onChange={this.handleMethodChange}
                      clearable={false}
                    >
                      {this.methodList.map((method, index) => (
                        <bk-option
                          key={index}
                          id={method.id}
                          name={method.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  </div>
                </div>
                <div class='query-item-wrap flex-1'>
                  <div class='query-item-label'>{this.$t('汇聚周期')}</div>
                  <div class='query-item-content'>
                    <CycleInput
                      minSec={10}
                      needAuto={true}
                      value={this.localValue.agg_interval as any}
                      onChange={this.handleIntervalChange}
                    />
                  </div>
                </div>
              </div>,
              <div class='query-item-group'>
                <div class='query-item-wrap query-item-group-by'>
                  <div class='query-item-label'>{this.$t('维度')}</div>
                  <div class='query-item-content'>
                    <bk-tag-input
                      vModel={this.localValue.agg_dimension}
                      list={this.metricGroupByList}
                      placeholder={String(this.$t('选择'))}
                      trigger='focus'
                      allow-next-focus={false}
                      allow-create={true}
                      search-key={['name', 'id']}
                      tpl={this.aggDimensionOptionTpl}
                      tag-tpl={this.aggDimensionTagTpl}
                      // tooltip-key="id"
                      onChange={() => this.emitChange()}
                    />
                  </div>
                </div>
                <div class='query-item-wrap'>
                  <div class='query-item-label'>{this.$t('条件')}</div>
                  <div class='query-item-content'>
                    <SimpleConditionInput
                      class='query-where-selector-simple'
                      conditionList={this.localValue.agg_condition}
                      dimensionsList={this.metricWhereGroupBy}
                      metricMeta={{
                        dataSourceLabel: this.localValue.data_source_label,
                        dataTypeLabel: this.localValue.data_type_label,
                        metricField: this.localValue.metric_field,
                        resultTableId: this.localValue.result_table_id,
                        indexSetId: this.localValue.index_set_id
                      }}
                      isHasNullOption={true}
                      onChange={this.handleConditionChaneg}
                      onKeyLoading={this.handleLoadingChange}
                    ></SimpleConditionInput>
                    {/* <ConditionInput
                    class={['query-where-selector', { 'is-empt': this.whereIsEmpt }]}
                    conditionList={this.localValue.agg_condition}
                    dimensionsList={this.metricWhereGroupBy}
                    metricMeta={{
                      dataSourceLabel: this.localValue.data_source_label,
                      dataTypeLabel: this.localValue.data_type_label,
                      metricField: this.localValue.metric_field,
                      resultTableId: this.localValue.result_table_id,
                      indexSetId: this.localValue.index_set_id
                    }}
                    on-change={this.handleConditionChaneg}
                    on-key-loading={this.handleLoadingChange}
                    on-clear-value={this.handleClearWhereValue}
                  /> */}
                  </div>
                </div>
                {!this.isRealTimeModel && this.localValue.canSetFunction ? (
                  <div class='query-item-wrap'>
                    <div class='query-item-label'>{this.$t('函数')}</div>
                    <div class='query-item-content'>
                      <FunctionSelect
                        class='query-func-selector'
                        v-model={this.localValue.functions}
                        onValueChange={() => this.emitChange()}
                      />
                    </div>
                  </div>
                ) : undefined}
              </div>
            ]
          : undefined}
      </div>
    );
  }
}
