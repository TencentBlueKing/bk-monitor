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
/*
 * @Date: 2021-06-11 11:50:26
 * @LastEditTime: 2021-06-30 19:28:43
 * @Description:
 */
/* eslint-disable camelcase */
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText, transformDataKey } from '../../../../../monitor-common/utils/utils';
import MonitorDialog from '../../../../../monitor-ui/monitor-dialog/monitor-dialog.vue';
import PromqlEditor from '../../../../../monitor-ui/promql-editor/promql-editor';
import MetricSelector from '../../../../components/metric-selector/metric-selector';
import { IIpV6Value, INodeType, TargetObjectType } from '../../../../components/monitor-ip-selector/typing';
import { transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import { handleSetTargetDesc } from '../../common';
import StrategyTargetTable from '../../strategy-config-detail/strategy-config-detail-table.vue';
import StrategyIpv6 from '../../strategy-ipv6/strategy-ipv6';
import { dataModeType, EditModeType, MetricDetail, MetricType } from '../typings';

import { IFunctionsValue } from './function-select';
import MonitorDataInput from './monitor-data-input';

import './monitor-data.scss';

interface IMonitorDataProps {
  metricData: MetricDetail[];
  source: string;
  expression: string;
  defaultCheckedTarget: any;
  dataMode: dataModeType;
  readonly: boolean;
  hasAIntelligentDetect: boolean;
  loading: boolean;
  editMode: EditModeType;
  promqlError: boolean;
  expFunctions: IFunctionsValue[];
  dataTypeLabel?: string;
  sourceStep: number | string;
  errMsg?: string;
  hasAiOpsDetect?: boolean;
  showRealtimeStrategy?: boolean;
}
interface IMonitorDataEvent {
  onModeChange: dataModeType;
  onSourceChange: string;
  onExpressionChange: string;
  onDelete: void;
  onAddMetric: { type: MetricType };
  onAddNullMetric: { type: MetricType };
  onTargetChange: any;
  onTargetTypeChange: string;
  onExpressionBlur: string;
  onMethodChange: string;
  onFunctionChange: any;
  onEditModeChange: { mode: EditModeType; hasError: boolean };
  onPromqlEnter: boolean;
  onPromqlBlur: boolean;
  onPromqlFocus: void;
  onExpFunctionsChange: IFunctionsValue[];
  onShowExpress: boolean;
  onSouceStepChange: number;
  onclearErr?: boolean;
}
@Component({
  name: 'monitor-data',
  components: {
    MonitorDialog,
    StrategyTargetTable
  }
})
export default class MyComponent extends tsc<IMonitorDataProps, IMonitorDataEvent> {
  @Prop({
    default: () => [],
    type: Array,
    required: true
  })
  readonly metricData: MetricDetail[];
  @Prop({ default: '', type: String }) source: string;
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: false, type: Boolean }) loading: boolean;
  @Prop({ default: false, type: Boolean }) promqlError: boolean;
  @Prop({ default: '', type: String }) expression: string;
  @Prop({ default: () => ({ target_detail: [] }), type: Object }) defaultCheckedTarget: any;
  @Prop({ default: 'converge', type: String }) dataMode: dataModeType;
  @Prop({ default: 'Edit', type: String }) editMode: EditModeType;
  @Prop({ default: false, type: Boolean }) hasAIntelligentDetect: boolean; // 存在一个只能检测算法
  @Prop({ default: () => [], type: Array }) expFunctions: IFunctionsValue[]; /** 表达式函数 */
  @Prop({ default: 'auto', type: [Number, String] }) sourceStep: number | string; /* source模式下的agg_interval */
  /* 当前的数据类型，用于判断应该弹出哪种指标选择器 */
  @Prop({ default: 'time_series', type: String }) dataTypeLabel: string;
  /* 报错信息 */
  @Prop({ default: '', type: String }) errMsg: string;
  /* 是否包含aiops算法(时序预测，智能异常, 离群) */
  @Prop({ default: false, type: Boolean }) hasAiOpsDetect: boolean;
  /* 是否展示实时选项 */
  @Prop({ default: false, type: Boolean }) showRealtimeStrategy: boolean;
  @Ref('targetContainer') targetContainerRef: HTMLDivElement;
  @Ref('promql-editor') promqlEditorRef: PromqlEditor;
  modeList: { id: string; name: TranslateResult }[];
  // editMode: EditModeType = 'Edit'
  showTopoSelector = false;
  targetList: any = [];
  target: any = {
    targetType: '',
    desc: {
      message: '',
      subMessage: ''
    }
  };
  levelList = [
    { id: 1, name: this.$t('致命'), icon: 'icon-danger' },
    { id: 2, name: this.$t('预警'), icon: 'icon-mind-fill' },
    { id: 3, name: this.$t('提醒'), icon: 'icon-tips' }
  ];
  metricInfoMap: Record<string, TranslateResult> = {};
  metricUrlMap: Record<string, string> = {};
  targetContainerHeight = 0;

  /* 指标选择器 */
  metricSelectorShow = false;

  /* 是否展示未选择ip及云区域的提示 */
  showTargetMessageTip = false;

  // promqlError = false
  // 指标标示名称
  get metricNameLabel() {
    const [{ metricMetaId, data_source_label: dataSourceLabel, data_type_label }] = this.metricData || [];
    if (metricMetaId === 'bk_monitor|log') {
      return this.$t('关键字');
    }
    if (dataSourceLabel === 'bk_log_search') {
      return this.$t('索引集');
    }
    if (metricMetaId === 'custom|event') {
      return this.$t('自定义事件');
    }
    if (metricMetaId === 'bk_monitor|event') {
      return this.$t('系统事件');
    }
    if (data_type_label === 'alert' || metricMetaId === 'bk_fta|event') {
      return this.$t('告警名称');
    }
    if (!dataSourceLabel) {
      if (data_type_label === 'event') {
        return this.$t('事件');
      }
      if (data_type_label === 'log') {
        return this.$t('关键字');
      }
    }
    return this.$t('指标');
  }
  // 指标基础数据
  get metricObjectType() {
    const [{ data_target: dataTarget }] = this.metricData;
    return dataTarget ? dataTarget.replace('_target', '').toLocaleUpperCase() : 'HOST';
  }
  get canActiveRealtime() {
    return this.metricData.length < 2 && this.metricData.every(item => item.canSetRealTimeSearch);
  }
  get canActiveConverge() {
    return this.metricData.some(item => item.metricMetaId !== 'bk_monitor|event');
  }
  get tabTips() {
    return {
      width: 240,
      content:
        this.dataMode === 'converge'
          ? this.$t(
              '汇聚是可以基于存储落地的数据按周期、维度（group by）、条件(where) 进行汇聚计算(MAX/AVG) 得到的结果再进行各种检测算法。所以汇聚至少有1个周期的等待，及时性会慢点，但功能强大。'
            )
          : this.$t(
              '实时是基于链路中的数据点（未落地时），直接进行数据的阈值比对，所以只适用于快速的单点的数据检测场景。像系统事件类就是没有落地存储直接在链路中进行检查。'
            )
    };
  }

  // // 是否可以添加多指标
  // get canAddMetric() {
  //   return this.metricData.every(item => item.canSetMulitpeMetric)
  // }
  // 是否支持源码编辑
  get supportSource() {
    return this.editMode === 'Source' || this.metricData?.[0]?.data_type_label === 'time_series';
    // || this.metricData.every(item => item.canSetMulitpeMetric && item.isNullMetric);
    // return this.metricData.every(item => item.canSetMulitpeMetric || item.isNullMetric);
  }
  get sourceDisabled() {
    return (
      this.dataMode === 'realtime' || !this.metricData.every(item => item.canSetMulitpeMetric || item.isNullMetric)
    );
  }
  /* 当前是否允许转为promql */
  get canToPromql() {
    if (this.editMode === 'Edit') {
      return this.metricData
        .filter(item => !!item.metric_id)
        .every(item => ['custom', 'bk_monitor'].includes(item.data_source_label));
    }
    return true;
  }
  created() {
    this.modeList = [
      {
        id: 'converge',
        name: this.$t('汇聚')
      },
      {
        id: 'realtime',
        name: this.$t('实时')
      }
    ];
    this.metricInfoMap = {
      time_series: this.$t(
        '指标：指标数据即时序数据。数据来源有：监控采集，自定义上报，计算平台，日志平台。可以对数据进行多指标计算和相应的函数功能。'
      ),
      event: this.$t(
        '事件：事件包括平台默认采集的系统事件，还有自定义上报的事件。系统事件未落存储，所以辅助视图是无数据状态。'
      ),
      log: this.$t(
        '日志关键字：日志关键字能力有两种，日志平台基于ES存储判断的日志关键字和基于Agent端进行日志关键字匹配的事件。'
      ),
      alert: this.$t('关联告警：可以基于告警事件/策略进行与或等，判断是否要再进行告警或者进行告警处理等。')
    };
    this.metricUrlMap = {
      time_series: '监控平台/产品白皮书/alarm-configurations/rules.md',
      event: '监控平台/产品白皮书/alarm-configurations/events_monitor.md',
      log: '监控平台/产品白皮书/alarm-configurations/log_monitor.md',
      alert: '监控平台/产品白皮书/alarm-configurations/composite_monitor.md'
    };
    this.targetList = this.defaultCheckedTarget?.target_detail || [];
    // 初始化时监控目标显示
    this.handleSetTargetDesc(
      this.targetList,
      this.metricData?.[0]?.targetType,
      this.defaultCheckedTarget?.node_count || 0,
      this.defaultCheckedTarget?.instance_count || 0
    );
  }
  handleChangeTab(item) {
    if ((item.id === 'realtime' && !this.canActiveRealtime) || (item.id === 'converge' && !this.canActiveConverge)) {
      return;
    }
    this.$emit('modeChange', item.id);
  }
  handleEditModeChange() {
    if (this.dataMode === 'converge') {
      if (this.editMode === 'Edit' && !this.canToPromql) return;
      const mode = this.editMode === 'Source' ? 'Edit' : 'Source';
      const error = mode === 'Edit' ? this.promqlEditorRef.getLinterStatus() : false;
      this.$emit('editModeChange', {
        mode,
        hasError: error
      });
    }
  }

  handleAddTarget() {
    this.showTopoSelector = true;
    this.$nextTick(() => {
      this.targetContainerHeight = this.targetContainerRef?.clientHeight;
    });
  }

  @Emit('targetChange')
  handleTargetSave() {
    this.showTopoSelector = false;
    this.$emit('targetTypeChange', this.target.targetType);
    return this.targetList;
  }

  handleTargetCancel() {
    this.showTopoSelector = false;
    // this.ipSelectKey = random(10);
    // this.targetList = this.defaultCheckedTarget?.target_detail?.slice?.() || [];
    // this.handleSetTargetDesc(this.targetList, this.metricData[0].targetType);
  }

  /**
   * @description 判断是否展示监控目标提示
   */
  getShowTargetMessageTipChange() {
    if (!this.targetList?.length) return false;
    if (this.target.targetType !== 'INSTANCE') return false;
    const cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
    const ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];
    let hasIpDimension = false;
    if (this.editMode === 'Source') {
      const str = this.source;
      const regex = /\(([^)]*)\)/g; // 匹配括号内的内容
      const strList = str.match(regex);
      hasIpDimension =
        !!strList?.length &&
        strList.some(str => ipMap.some(s => new RegExp(s).test(str)) && cloudIdMap.some(s => new RegExp(s).test(str)));
    } else {
      hasIpDimension = this.metricData.some(
        item => item.agg_dimension.some(d => cloudIdMap.includes(d)) && item.agg_dimension.some(d => ipMap.includes(d))
      );
    }
    return !hasIpDimension;
  }

  handleTopoCheckedChange(data: { value: IIpV6Value; nodeType: INodeType; objectType: TargetObjectType }) {
    this.targetList = transformValueToMonitor(data.value, data.nodeType);
    this.target.targetType = data.nodeType;
    this.handleSetTargetDesc(this.targetList, this.target.targetType);
    this.handleTargetSave();
    this.showTargetMessageTip = this.getShowTargetMessageTipChange();
  }

  // 编辑时设置监控目标描述
  handleSetTargetDesc(
    targetList: { count: number; bk_obj_id: string; nodes_count?: number; instances_count?: number; all_host: any[] }[],
    bkTargetType: string,
    nodeCount = 0,
    instance_count = 0
  ) {
    const [{ objectType }] = this.metricData;
    const result = handleSetTargetDesc(targetList, bkTargetType, objectType, nodeCount, instance_count);
    this.target.desc.message = result.message;
    this.target.desc.subMessage = result.subMessage;
  }

  /**
   * @description: promql值更新
   * @param {string} value
   */
  handlePromsqlChange(value: string) {
    this.handleSourceChange(value);
  }
  /* source step 更新 */
  @Emit('souceStepChange')
  handleSourceStepChange(value: number) {
    return value;
  }

  /**
   * @description: promql编辑器聚焦
   */
  handlePromqlFocus() {
    this.$emit('promqlFocus');
  }
  /**
   * @description: promql编辑器enter键事件
   */
  @Emit('promqlEnter')
  handlePromqlEnter(hasError: boolean) {
    return hasError;
  }
  /**
   * @description: promql编辑器失焦事件
   */
  @Emit('promqlBlur')
  handlePromqlBlur(hasError: boolean) {
    return hasError;
  }

  @Emit('delete')
  handleDeleteMetric(v) {
    return v.index;
  }

  @Emit('clear')
  handleClearMetricData() {}

  @Emit('addMetric')
  handleAddMetric(metric) {
    return metric;
  }
  @Emit('addNullMetric')
  handleAddNullMetric(type) {
    return { type };
  }
  @Emit('expressionChange')
  handleExpressionChange(v: string) {
    return v;
  }
  @Emit('expressionBlur')
  handleExpressionBlur(v: string) {
    return v;
  }
  @Emit('expFunctionsChange')
  handleFunctionsChange(functions: IFunctionsValue[]) {
    return functions;
  }
  @Emit('sourceChange')
  handleSourceChange(value: string) {
    return value;
  }
  @Emit('methodChange')
  emitMethodChange(val: string) {
    return val;
  }
  @Emit('functionChange')
  emitFunctionChange(val) {
    return val;
  }
  @Emit('showExpress')
  showExpressChange(val: boolean) {
    return val;
  }
  ipSelect() {
    const [{ targetType, objectType }] = this.metricData;
    if (!this.readonly) {
      return (
        <StrategyIpv6
          showDialog={this.showTopoSelector}
          nodeType={targetType as INodeType}
          objectType={objectType as TargetObjectType}
          checkedNodes={this.targetList || []}
          onChange={this.handleTopoCheckedChange}
          onCloseDialog={v => (this.showTopoSelector = v)}
        />
      );
    }
    const tableData = this.readonly ? transformDataKey(this.defaultCheckedTarget?.detail || []) : [];
    return (
      <monitor-dialog
        v-model={this.showTopoSelector}
        on-change={v => (this.showTopoSelector = v)}
        on-on-cancel={this.handleTargetCancel}
        need-footer={false}
        width='1100'
        title={this.$t('监控目标')}
        zIndex={1002}
      >
        <strategy-target-table
          tableData={tableData}
          targetType={targetType}
          objType={objectType}
        />
      </monitor-dialog>
    );
  }

  handleMetricSelectShow(v: boolean) {
    this.metricSelectorShow = v;
  }
  handleSelectMetric(value) {
    const copyStr = value.promql_metric;
    copyText(copyStr, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  @Emit('clearErr')
  handleMonitorDataMouseenter() {
    return true;
  }

  render() {
    const isSource = id => id === 'realtime' && this.editMode === 'Source';
    const isTabDisabled = (id: string) =>
      (id === 'realtime' && (!this.canActiveRealtime || this.hasAiOpsDetect)) ||
      (id === 'converge' && !this.canActiveConverge) ||
      (this.readonly && this.dataMode !== id) ||
      isSource(id);
    const tabContent = id => {
      if (!this.metricData?.every(item => item.metric_field)) return this.$t('添加指标');
      if (isSource(id)) return this.$t('源码模式不支持实时检测');
      if (this.hasAiOpsDetect) return this.$t('智能检测算法不支持实时检测');
      return !this.canActiveRealtime ? this.$t('多指标暂不支持实时检测') : this.$t('系统事件只支持实时检测');
    };
    // const tableProps = (id: string) => {
    //   if(isTabDisabled(id)) {
    //     return {
    //       'v-bk-tooltips': {
    //         content: 'sdfsdfsdf'
    //       }
    //     }
    //   }
    //   return {}
    // }
    return (
      <div
        class='monitor-data'
        v-bkloading={{ isLoading: this.loading }}
      >
        <bk-alert type='info'>
          <div slot='title'>
            {this.metricInfoMap[this.metricData?.[0]?.data_type_label || 'time_series']}
            <a
              class='info-url'
              target='blank'
              href={`${window.bk_docs_site_url}markdown/${
                this.metricUrlMap[this.metricData?.[0]?.data_type_label || 'time_series']
              }`}
            >
              {this.$t('查看更多文档')}
            </a>
          </div>
        </bk-alert>
        <div class='monitor-data-metric'>
          {!this.metricData.some(item => item.data_type_label === 'alert') && (
            <div class='metric-tab'>
              <div class='metric-tab-left'>
                {this.modeList
                  .filter(item => (item.id === 'realtime' ? this.showRealtimeStrategy : true))
                  .map((item, index) => (
                    <span
                      key={item.id}
                      v-en-style='width: 80px'
                      class={[
                        'tab-item',
                        {
                          'tab-active': this.dataMode === item.id,
                          'tab-disable': isTabDisabled(item.id)
                        }
                      ]}
                      style={{ marginLeft: index > 0 ? '-1px' : '' }}
                      on-click={() => !this.readonly && !isTabDisabled(item.id) && this.handleChangeTab(item)}
                      v-bk-tooltips={{
                        maxWidth: 240,
                        content:
                          this.dataMode === item.id
                            ? (() => {
                                if (item.id === 'converge') {
                                  return this.$t(
                                    '汇聚是可以基于存储落地的数据按周期、维度（group by）、条件(where) 进行汇聚计算(MAX/AVG) 得到的结果再进行各种检测算法。所以汇聚至少有1个周期的等待，及时性会慢点，但功能强大。'
                                  );
                                }
                                return this.$t(
                                  '实时是基于链路中的数据点（未落地时），直接进行数据的阈值比对，所以只适用于快速的单点的数据检测场景。像系统事件类就是没有落地存储直接在链路中进行检查。'
                                );
                              })()
                            : tabContent(item.id),
                        disabled: isTabDisabled(item.id) ? false : this.dataMode !== item.id,
                        allowHTML: false
                        // disabled: !this.metricData?.every(item => item.metric_field)
                        //  || !isTabDisabled(item.id)
                        //  || this.readonly
                      }}
                    >
                      <span class='bd-hover'>{item.name}</span>
                    </span>
                  ))}
                {/* {<i class="icon-monitor icon-tips tips-icon" v-bk-tooltips={this.tabTips}></i>} */}
              </div>
            </div>
          )}
          {this.supportSource && (
            <div class='monitor-data-tool'>
              <div class='tool-left'>
                {/* {this.editMode === 'Edit' ? <bk-dropdown-menu trigger="click">
                <div slot="dropdown-trigger">
                  <span class="primary-btn">
                    <span>{this.$t('查询模板')}</span>
                    <span class="icon-monitor icon-mc-triangle-down"></span>
                  </span>
                </div>
              </bk-dropdown-menu> : <span class="primary-btn disable">
                <span>{this.$t('查询模板')}</span>
                <span class="icon-monitor icon-mc-triangle-down"></span>
              </span>} */}
                {this.editMode === 'Source' && (
                  <div
                    class='metric-copy-btn'
                    id='metric-copy-btn-select-id'
                    onClick={() => this.handleMetricSelectShow(true)}
                  >
                    <span>{this.$t('指标选择')}</span>
                    <span class='icon-monitor icon-arrow-down'></span>
                  </div>
                )}
                <MetricSelector
                  show={this.metricSelectorShow}
                  type={MetricType.TimeSeries}
                  targetId={'#metric-copy-btn-select-id'}
                  isPromql={true}
                  onShowChange={(v: boolean) => this.handleMetricSelectShow(v)}
                  onSelected={this.handleSelectMetric}
                ></MetricSelector>
              </div>
              <div class='tool-right'>
                <span
                  class={['metric-tab-right', { 'mode-disable': this.dataMode === 'realtime' || !this.canToPromql }]}
                  v-bk-tooltips={{
                    content: this.$t('目前仅支持{0}切换PromQL', [
                      `${this.$t('监控采集指标')}、${this.$t('自定义指标')}`
                    ]),
                    disabled: !(this.dataMode === 'realtime' || !this.canToPromql)
                  }}
                  on-click={this.handleEditModeChange}
                >
                  <i class='icon-monitor icon-switch' />
                  {this.editMode === 'Edit' ? 'PromQL' : 'UI'}
                </span>
              </div>
            </div>
          )}
          {this.editMode === 'Edit' ? (
            <div onMouseenter={this.handleMonitorDataMouseenter}>
              <MonitorDataInput
                class={{ 'alert-metric': this.metricData.some(item => item.data_type_label === 'alert') }}
                readonly={this.readonly}
                metricNameLabel={this.metricNameLabel}
                metricData={this.metricData}
                isRealTimeModel={this.dataMode === 'realtime'}
                expression={this.expression}
                expFunctions={this.expFunctions}
                hasAiOpsDetect={this.hasAiOpsDetect}
                hasAIntelligentDetect={this.hasAIntelligentDetect}
                dataTypeLabel={this.metricData?.[0]?.data_type_label || this.dataTypeLabel}
                onFunctionChange={this.emitFunctionChange}
                onMethodChange={this.emitMethodChange}
                onExpressionBlur={this.handleExpressionBlur}
                on-expression-change={this.handleExpressionChange}
                on-delete={this.handleDeleteMetric}
                on-add-metric={this.handleAddMetric}
                onExpFunctionsChange={this.handleFunctionsChange}
                onAddNullMetric={this.handleAddNullMetric}
                onShowExpress={this.showExpressChange}
              />
            </div>
          ) : (
            <div class='metric-source-wrap'>
              <div class={['metric-source', { 'is-error': this.promqlError }]}>
                {this.loading ? undefined : (
                  <PromqlEditor
                    ref='promql-editor'
                    class='promql-editor'
                    value={this.source}
                    onFocus={this.handlePromqlFocus}
                    executeQuery={this.handlePromqlEnter}
                    // onBlur={(val, hasError: boolean) => this.handlePromqlBlur(hasError)}
                    onChange={this.handlePromsqlChange}
                  />
                )}
              </div>
              <div class='source-options-wrap'>
                <bk-input
                  class='step-input'
                  value={this.sourceStep}
                  min={10}
                  type='number'
                  precision={0}
                  onChange={this.handleSourceStepChange}
                >
                  <div
                    slot='prepend'
                    class='step-input-prepend'
                  >
                    <span>{'Step'}</span>
                    <span
                      class='icon-monitor icon-hint'
                      v-bk-tooltips={{
                        content: this.$t('数据步长'),
                        placements: ['top']
                      }}
                    ></span>
                  </div>
                </bk-input>
              </div>
            </div>
          )}
          {this.supportSource && !!this.errMsg ? <div class='monitor-err-msg'>{this.errMsg}</div> : undefined}
          {this.metricData.some(item => item.canSetTarget) && (
            <div class='ip-wrapper'>
              {!this.targetList.length && !this.target.desc.message.length
                ? [
                    !this.readonly ? (
                      <div
                        class='ip-wrapper-title'
                        on-click={this.handleAddTarget}
                      >
                        <i class='icon-monitor icon-mc-plus-fill'></i>
                        {this.$t('添加监控目标')}
                      </div>
                    ) : (
                      <span>{this.$t('未添加监控目标')}</span>
                    ),
                    <span class='subtitle ml5'>{`(${this.$t('默认为本业务')})`}</span>
                  ]
                : [
                    <i class='icon-monitor icon-mc-tv'></i>,
                    <span
                      class='subtitle'
                      style='color: #63656e;'
                    >
                      {this.target.desc.message}
                      {this.target.desc.subMessage}
                    </span>,
                    this.readonly ? (
                      <span
                        class='ip-wrapper-title'
                        onClick={this.handleAddTarget}
                      >
                        {this.$t('查看监控目标')}
                      </span>
                    ) : (
                      <span
                        class='icon-monitor icon-bianji'
                        onClick={this.handleAddTarget}
                      ></span>
                    ),
                    this.showTargetMessageTip && (
                      <span class='ip-dimension-tip'>
                        <span class='icon-monitor icon-remind'></span>
                        <span>{this.$t('当前维度未选择目标IP与云区域ID，会导致监控目标选择无法生效')}</span>
                        <span
                          class='icon-monitor icon-mc-close'
                          onClick={() => (this.showTargetMessageTip = false)}
                        ></span>
                      </span>
                    )
                  ]}
            </div>
          )}
        </div>
        {this.metricData.some(item => item.canSetTarget) && this.ipSelect()}
        {this.metricData.slice(0, 1).map(
          item =>
            (item.metricMetaId === 'bk_monitor|event' || item.data_type_label === 'alert') && (
              <div class='monitor-event'>
                <span
                  class='monitor-event-title'
                  v-en-style='width: 105px'
                >
                  {this.$t('告警级别')} :
                </span>
                <bk-radio-group v-model={item.level}>
                  {this.levelList.map(radio => (
                    <bk-radio
                      class='monitor-event-radio'
                      value={radio.id}
                    >
                      <i class={['icon-monitor', radio.icon, `status-${radio.id}`]} />
                      {radio.name}
                    </bk-radio>
                  ))}
                </bk-radio-group>
              </div>
            )
        )}
      </div>
    );
  }
}
