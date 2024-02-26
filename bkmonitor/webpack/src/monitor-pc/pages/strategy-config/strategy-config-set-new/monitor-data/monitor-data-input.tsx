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
/* eslint-disable no-param-reassign */
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Mixins, Prop, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { getMetricListV2 } from '../../../../../monitor-api/modules/strategies';
import CycleInput from '../../../../components/cycle-input/cycle-input';
import metricTipsContentMixin from '../../../../mixins/metricTipsContentMixin';
import { getPopoverWidth } from '../../../../utils';
// import ConditionInput from './condition-input';
import SimpleConditionInput from '../../../alarm-shield/components/simple-condition-input';
// import IntervalSelect from '../../../../components/cycle-input/interval-select'
import { MetricDetail, MetricType } from '../typings/index';

import FunctionSelect, { IFunctionsValue } from './function-select';
import LogMetricInfo from './log-metric-info';

import './monitor-data-input.scss';

const expressPlaceholders = (type: string) => {
  if (type === 'event') {
    return String(window.i18n.t('支持逻辑表达式 ! || && ( ) , 如 A && B'));
  }
  if (type === 'alert') {
    return `${window.i18n.t('支持')}  ! && ||  () , 如a && !b`;
  }
  return String(window.i18n.t('支持四则运算 + - * / % ^ ( ) ,如(A+B)/100'));
};
interface IMericDataInputProps {
  metricData: MetricDetail[];
  metricNameLabel: string | TranslateResult;
  expression: string;
  isRealTimeModel?: boolean;
  readonly: boolean;
  hasAIntelligentDetect: boolean;
  expFunctions: IFunctionsValue[];
  dataTypeLabel?: string;
  hasAiOpsDetect?: boolean;
}
interface IMetricDataInputEvent {
  onExpressionBlur: string;
  onMethodChange: string;
  onFunctionChange: any;
  onExpFunctionsChange: unknown[];
  onAddNullMetric: string;
  onShowExpress: boolean;
}

@Component({
  name: 'monitor-data-input'
})
class MericDataInput extends Mixins(metricTipsContentMixin) {
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];
  // 是否是实时模式
  @Prop({ type: Boolean, default: false }) isRealTimeModel: boolean;
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ type: String, default: '' }) metricNameLabel: string | TranslateResult;
  @Prop({ type: String, default: '' }) expression: string;
  @Prop({ default: false, type: Boolean }) hasAIntelligentDetect: boolean; // 存在一个智能检测算法
  @Prop({ default: () => [], type: Array }) expFunctions: IFunctionsValue[]; /** 表达式函数 */
  @Prop({ type: String, default: 'time_series' }) dataTypeLabel: string;
  @Prop({ default: false, type: Boolean }) hasAiOpsDetect: boolean;

  hoverDeleteItemIndex = -1;
  levelIconMap: string[] = [, 'icon-danger', 'icon-mind-fill', 'icon-tips'];
  contentLoading = false;
  metricpopoerInstance: any = null;
  isShowExpress = false; // 此值用与单指标时可选填表达式
  dimensionPopInstance = null;
  // 是否可以设置表达式
  get canSetExpress() {
    return this.metricData.length > 1 && this.metricData.every(item => item.canSetMulitpeMetric);
  }
  // 是否可以添加多指标
  get canAddMetric() {
    return this.metricData.every(item => item.canSetMulitpeMetric);
  }
  // 是否关联告警
  // get isAlertMetric() {
  //   return this.metricData.some(item => item.data_type_label === 'alert');
  // }
  // 用于判断表达式的显隐
  get metricLength() {
    return this.metricData.length;
  }

  get isLogSearchType() {
    return this.metricData?.every(
      item => item.metricMetaId === 'bk_log_search|log' && item.metric_type === MetricType.LOG
    );
  }

  @Watch('isShowExpress', { immediate: true })
  @Emit('showExpress')
  showExpressChange(val) {
    return val;
  }
  @Watch('metricData', { immediate: true })
  handleMetricDataChange() {
    if (!this.isLogSearchType) return;
    this.getLogMetricList();
  }
  created() {
    if (
      ['strategy-config-detail', 'strategy-config-edit', 'strategy-config-add'].includes(this.$route.name) &&
      this.metricData.length >= 1 &&
      this.metricData.every(item => item.canSetMulitpeMetric) &&
      this.expression &&
      this.expression !== 'a'
    ) {
      this.isShowExpress = true;
    }
  }

  beforeDestroy() {
    this.handleDestroyPopInstance();
  }

  @Watch('metricLength')
  handleMetricLength(newLen: number) {
    // 当由多指标变为单指标时并且表达式为默认值a时则不显示表达式
    // if (oldLen > 1 && newLen === 1 && this.expression === 'a') {
    //   this.isShowExpress = false;
    // }
    this.isShowExpress = !(newLen === 1 && this.expression === 'a');
  }

  @Emit('delete')
  handleDeleteMetric(item, index) {
    return { item, index };
  }

  @Emit('add-metric')
  handleAddMetric(item?: MetricDetail) {
    const metricItem = item || {};
    const type = item?.data_type_label || this.dataTypeLabel;
    if (['event', 'log', 'alert'].includes(type))
      return {
        type,
        ...metricItem
      };
    return {
      type: MetricType.TimeSeries,
      ...metricItem
    };
  }

  handleAddExpression() {
    if (!this.hasAiOpsDetect && !this.readonly) {
      this.isShowExpress = true;
    }
  }

  handleShowDimensions() {}
  // 监控周期改变
  @Emit('interval-change')
  handleAggIntervalChange(item: MetricDetail, v: number) {
    item.agg_interval = v;
  }
  // 监控条件改变
  @Emit('condition-change')
  handleConditionChange(item: MetricDetail, v: any[]) {
    item.agg_condition = v;
  }

  @Emit('expression-change')
  handleExpressionChange(e: any) {
    return e.target.value.trim?.() || '';
  }
  @Emit('expressionBlur')
  handleExpressionBlur() {
    return this.expression || '';
  }
  @Emit('expFunctionsChange')
  handleFunctionsChange(functions: IFunctionsValue[]) {
    return functions;
  }
  @Emit('methodChange')
  emitMethodChange(metric: MetricDetail, val: string) {
    metric.agg_method = val;
    // 日志检索指标 转换回原始指标
    if (this.isLogSearchType) {
      if (val === 'COUNT') {
        const metricList = metric.metric_id.toString().split('.');
        if (metricList.length > 3) {
          metric.metric_id = metricList.slice(0, 3).join('.');
        }
      } else {
        metric.metric_id = metric.curRealMetric?.metric_id || metric.logMetricList?.[0]?.metric_id || '';
      }
    }
    return val;
  }
  @Emit('functionChange')
  emitFunctionChange(val) {
    return val;
  }
  @Emit('addNullMetric')
  emitAddNullMetric() {
    if (this.dataTypeLabel === 'alert') return 'alert';
    return MetricType.TimeSeries;
  }
  /**
   *
   * @description 获取日志检索指标列表
   */
  async getLogMetricList() {
    if (!this.isLogSearchType) return [];
    const [metric] = this.metricData;
    const data = await getMetricListV2({
      conditions: [
        {
          key: 'related_id',
          value: metric.index_set_id
        }
      ],
      data_source: [['bk_log_search', 'time_series']]
    }).catch(() => []);
    metric.setLogMetricList(data?.metric_list || []);
  }
  handleAddMetricProxy() {
    if (!this.hasAiOpsDetect && !this.readonly) {
      // this.handleAddMetric();
      this.emitAddNullMetric();
    }
  }

  handleGetDimensionList(item: MetricDetail) {
    const longDimension = this.metricData.reduce(
      (pre, cur) => (cur.agg_dimension?.length > pre?.length ? cur.agg_dimension : pre),
      []
    );
    // 监控指标 多指标下不能对cmdb节点进行聚合
    if (item.agg_dimension.length === longDimension.length || longDimension.length === 0) {
      return item.dimensions
        .filter(dim =>
          this.metricData.length > 1 && item.metricMetaId === 'bk_monitor|time_series'
            ? !['bk_inst_id', 'bk_obj_id'].includes(dim.id.toString())
            : true
        )
        .map(item => ({ ...item, disabled: false }));
    }
    return item.dimensions
      .filter(dim =>
        this.metricData.length > 1 && item.metricMetaId === 'bk_monitor|time_series'
          ? !['bk_inst_id', 'bk_obj_id'].includes(dim.id.toString())
          : true
      )
      .map(item => ({ ...item, disabled: !longDimension.includes(item.id) }));
  }
  handleGetConditionDimensionList(item: MetricDetail) {
    // 监控指标 多指标下不能对cmdb节点进行聚合
    return item.rawDimensions.filter(dim =>
      this.metricData.length > 1 && item.metricMetaId === 'bk_monitor|time_series'
        ? !['bk_inst_id', 'bk_obj_id'].includes(dim.id.toString())
        : true
    );
  }

  handleDimensionMouseEnter(e, node) {
    // 每次创建前销毁以前存在的实例
    this.handleDestroyPopInstance();
    this.dimensionPopInstance = this.$bkPopover(e.target, {
      content: node.disabled ? this.$t('多指标的维度需要有包含关系') : node.id,
      placement: 'right',
      zIndex: 9999,
      boundary: document.body,
      appendTo: document.body
    });
    this.dimensionPopInstance.show?.();
  }

  /**
   * 销毁维度popover实例
   */
  handleDestroyPopInstance() {
    if (this.dimensionPopInstance) {
      this.dimensionPopInstance.hide?.(0);
      this.dimensionPopInstance.destroy?.();
      this.dimensionPopInstance = null;
    }
  }

  handleRenderDimensionList(node, ctx, highlightKeyword) {
    const parentClass = 'bk-selector-node bk-selector-member';
    const textClass = 'text';
    const innerHtml = `${highlightKeyword(node.name)}`;
    return (
      <div class={parentClass}>
        <span
          class={textClass}
          domPropsInnerHTML={innerHtml}
          onMouseenter={e => this.handleDimensionMouseEnter(e, node)}
        ></span>
      </div>
    );
  }
  handleRenderDimensionTag(node) {
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
  handleMetricMouseenter(e: MouseEvent, item: MetricDetail) {
    let content = '';
    try {
      content = this.handleGetMetricTipsContent(item);
    } catch (error) {
      // content = `${this.$t('指标不存在')}`;
    }
    if (content) {
      this.metricpopoerInstance = this.$bkPopover(e.target, {
        content,
        placement: 'right',
        theme: 'monitor-metric-input',
        arrow: true,
        flip: false
      });
      this.metricpopoerInstance?.show?.(100);
    }
  }
  handleMetricMouseleave() {
    this.metricpopoerInstance?.hide?.();
    this.metricpopoerInstance?.destroy?.();
    this.metricpopoerInstance = null;
  }
  handleQueryStringChange(e: Event, item: MetricDetail) {
    item.keywords_query_string = String((e.target as any).value).trim();
  }
  render() {
    return (
      <div class='metric-content'>
        {this.metricData.map((item, index) => {
          // 空指标的维度可选项
          const nullMetricGroupByList = item.isNullMetric
            ? item.agg_dimension.map(item => ({ id: item, name: item }))
            : null;
          // 空指标的条件维度可选项
          const nullMetricWhere = item.isNullMetric
            ? item.agg_condition.map(item => ({ id: item.key, name: item.key }))
            : null;
          return (
            <div
              class='metric-content-item mb10'
              key={`${item.id}-${index}`}
              on-mouseenter={() => (this.hoverDeleteItemIndex = index)}
              on-mouseleave={() => (this.hoverDeleteItemIndex = -1)}
            >
              {!this.isRealTimeModel && <span class='item-key'>{item.alias}</span>}
              <div
                class='item-content'
                v-bkloading={{ isLoading: this.contentLoading }}
              >
                {/* =======指标====== */}
                {
                  <div class='form metric-name'>
                    <span
                      class='form-label'
                      style='border-left: 1px solid #dcdee5'
                    >
                      {this.metricNameLabel || this.$t('指标')}
                    </span>
                    <div
                      class='form-content monitor-input metric-wrap'
                      onMouseenter={e => this.handleMetricMouseenter(e, item)}
                      onMouseleave={this.handleMetricMouseleave}
                      on-click={() => !this.readonly && this.handleAddMetric(item)}
                    >
                      <div
                        class='metric-input'
                        id={`set-panel-item-${this.dataTypeLabel}${item.key || ''}`}
                        style='display: flex;align-items: flex-end;'
                      >
                        {item.metric_field_name || item.metric_id || <span class='placeholder'>{this.$t('添加')}</span>}
                      </div>
                    </div>
                  </div>
                }
                {/* =======检索语句====== */}
                {item.canSetQueryString && !item.isNullMetric && (
                  <div class='form'>
                    <span class='form-label'>
                      {this.$t('检索语句')}
                      <LogMetricInfo />
                    </span>
                    <div
                      class='form-content content-wrap'
                      style='min-width: 200px'
                    >
                      <span class='input-content'>{item.localQueryString}</span>
                      <input
                        key='queryString'
                        class='monitor-input input-set'
                        placeholder={String(this.$t('输入'))}
                        v-model={item.localQueryString}
                        onBlur={(e: Event) => this.handleQueryStringChange(e, item)}
                      />
                    </div>
                  </div>
                )}
                {/* =======汇聚方法====== */}
                {!this.isRealTimeModel && item.canSetAggMethod && !item.isNullMetric && (
                  <div class='form'>
                    <span class='form-label'>{this.$t('汇聚')}</span>
                    <bk-select
                      class='select-small'
                      clearable={false}
                      v-model={item.agg_method}
                      popover-width={getPopoverWidth(item?.aggMethodList || [])}
                      onSelected={v => this.emitMethodChange(item, v)}
                    >
                      {item?.aggMethodList.map(option => (
                        <bk-option
                          key={option.id}
                          id={option.id}
                          name={option.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  </div>
                )}
                {/* 指标 */}
                {this.isLogSearchType && item.agg_method !== 'COUNT' && (
                  <div class='form'>
                    <span class='form-label'>{this.$t('指标')}</span>
                    <bk-select
                      class='select-small'
                      clearable={false}
                      popover-min-width=''
                      v-model={item.metric_id}
                      popover-width={getPopoverWidth(item?.logMetricList || [])}
                    >
                      {item.logMetricList?.map(option => (
                        <bk-option
                          key={option.metric_id}
                          id={option.metric_id}
                          name={option.metric_field_name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  </div>
                )}
                {/* =======汇聚周期====== */}
                {!this.isRealTimeModel && item.canSetAggInterval && !item.isNullMetric && (
                  <div class='form'>
                    <span class='form-label'>{this.$t('周期')}</span>
                    <CycleInput
                      class='form-interval'
                      v-model={item.agg_interval}
                      needAuto={false}
                      onChange={(v: number) => this.handleAggIntervalChange(item, v)}
                    />
                    {/* <IntervalSelect
                      value={item.agg_interval}
                      placeholder={String(this.$t('输入'))}
                      list={item.agg_interval_list}
                      on-input={(v: number) => this.handleAggIntervalChange(item, v)}/> */}
                  </div>
                )}
                {/* {
                  !this.isRealTimeModel && item.canSetAggInterval
                    ? <CycleInput
                        v-model={item.agg_interval}
                        onChange={(v: number) => this.handleAggIntervalChange(item, v)} />
                    : undefined
                } */}
                {/* =======维度====== */}
                {!this.isRealTimeModel && item.canSetDimension && !item.isNullMetric && (
                  <div class='form metric-dimension'>
                    <span class='form-label'>{this.$t('维度')}</span>
                    <bk-tag-input
                      class='form-content monitor-input monitor-dimension'
                      v-model={item.agg_dimension}
                      list={nullMetricGroupByList || this.handleGetDimensionList(item)}
                      content-width={getPopoverWidth(
                        nullMetricGroupByList || this.handleGetDimensionList(item),
                        20,
                        190
                      )}
                      placeholder={String(this.$t('选择'))}
                      trigger='focus'
                      has-delete-icon
                      allow-create
                      allow-next-focus={false}
                      search-key={['name', 'id']}
                      tag-tpl={this.handleRenderDimensionTag}
                      tpl={this.handleRenderDimensionList}
                    ></bk-tag-input>
                  </div>
                )}
                {/* =======条件====== */}
                {/* eslint-disable-next-line no-param-reassign */}
                {/* {!item.isNullMetric && <ConditionInput
                  conditionList={item.agg_condition}
                  dimensionsList={nullMetricWhere || this.handleGetConditionDimensionList(item)}
                  metricMeta={{
                    dataSourceLabel: item.data_source_label,
                    dataTypeLabel: item.data_type_label,
                    metricField: item.metric_field,
                    resultTableId: item.result_table_id,
                    indexSetId: item.index_set_id }}
                  on-change={v => this.handleConditionChange(item, v)}
                  key-loading={v => this.contentLoading = v }/>} */}
                {!item.isNullMetric && (
                  <SimpleConditionInput
                    conditionList={item.agg_condition}
                    dimensionsList={nullMetricWhere || this.handleGetConditionDimensionList(item)}
                    metricMeta={{
                      dataSourceLabel: item.data_source_label,
                      dataTypeLabel: item.data_type_label,
                      metricField: item.metric_field,
                      resultTableId: item.result_table_id,
                      indexSetId: item.index_set_id
                    }}
                    hasLeftLabel={true}
                    isHasNullOption={true}
                    on-change={v => this.handleConditionChange(item, v)}
                    onKeyLoading={v => (this.contentLoading = v)}
                  ></SimpleConditionInput>
                )}
                {/* =======函数====== */}
                {!this.isRealTimeModel && item.canSetFunction && !this.hasAiOpsDetect && !item.isNullMetric && (
                  <FunctionSelect
                    v-model={item.functions}
                    onValueChange={this.emitFunctionChange}
                  />
                )}
              </div>
              <div class='item-delete'>
                <div
                  class='item-delete-btn'
                  // eslint-disable-next-line quotes
                  style={{ display: this.hoverDeleteItemIndex === index ? 'flex' : 'none' }}
                  on-click={() => this.handleDeleteMetric(item, index)}
                >
                  <i class='icon-monitor icon-mc-delete-line'></i>
                </div>
              </div>
            </div>
          );
        })}
        {!this.isRealTimeModel && (
          <div class='metric-content-expression form'>
            {/* =======计算表达式====== */}
            {this.canSetExpress || this.isShowExpress
              ? [
                  <div class='expression-left'>
                    <span class='item-key'>
                      <i class='icon-monitor icon-arrow-turn'></i>
                    </span>
                    <div class='form-label'>{this.$t('表达式')}</div>
                    <input
                      class='form-content monitor-input'
                      placeholder={expressPlaceholders(this.metricData[0].data_type_label || this.dataTypeLabel)}
                      onInput={this.handleExpressionChange}
                      onBlur={this.handleExpressionBlur}
                      value={this.expression}
                    />
                    <FunctionSelect
                      class='query-func-selector'
                      isExpSupport
                      value={this.expFunctions}
                      onValueChange={this.handleFunctionsChange}
                    />
                  </div>,
                  !this.readonly && this.canAddMetric && (
                    <button
                      class='expression-right'
                      ref='addMetricBtn'
                      v-bk-tooltips={{
                        content: this.$t('AIOps算法只支持单指标'),
                        disabled: !this.hasAiOpsDetect || this.readonly
                      }}
                      on-click={this.handleAddMetricProxy}
                    >
                      <i class='bk-icon icon-plus'></i>
                      <span class='name'>{`${this.$t('添加')}${this.metricNameLabel}`}</span>
                    </button>
                  )
                ]
              : !this.readonly &&
                this.canAddMetric && (
                  <div
                    class={['expression-right-btn add-metric', { 'is-disabled': this.hasAiOpsDetect || this.readonly }]}
                  >
                    <div
                      class='metric-add-btn'
                      onClick={this.handleAddMetricProxy}
                    >
                      <i class='icon-monitor icon-mc-add'></i>
                      <span
                        v-bk-tooltips={{
                          content: this.$t('AIOps算法只支持单指标'),
                          disabled: !this.hasAiOpsDetect || this.readonly
                        }}
                      >
                        {this.$t('多指标计算')}
                      </span>
                    </div>
                    <div
                      class='expression-add-btn'
                      v-bk-tooltips={{
                        content: this.$t('AIOps算法只支持单指标'),
                        disabled: !this.hasAiOpsDetect || this.readonly
                      }}
                      onClick={this.handleAddExpression}
                    >
                      <i class='icon-monitor icon-mc-add'></i>
                      <span>{this.$t('表达式')}</span>
                    </div>
                  </div>
                )}
          </div>
        )}
        {this.canSetExpress || this.isShowExpress ? (
          <div class='express-tip'>{expressPlaceholders(this.metricData[0].data_type_label || this.dataTypeLabel)}</div>
        ) : undefined}
        {this.readonly && <div class='is-readonly' />}
      </div>
    );
  }
}

export default tsx.ofType<IMericDataInputProps, IMetricDataInputEvent>().convert(MericDataInput);
