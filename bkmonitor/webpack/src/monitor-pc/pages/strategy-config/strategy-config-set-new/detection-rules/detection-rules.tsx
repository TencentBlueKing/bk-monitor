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

import { getUnitInfo } from '../../../../../monitor-api/modules/strategies';
import { deepClone } from '../../../../../monitor-common/utils/utils';
import MonitorSelect from '../../../../components/monitor-select/monitor-select.vue';
import { THRESHOLD_METHOD_LIST } from '../../../../constant/constant';
import AbnormalCluster from '../../../../static/images/svg/abnormal-cluster.svg';
import IntelligentDetect from '../../../../static/images/svg/intelligent-detect.svg';
import PartialNodes from '../../../../static/images/svg/partial-nodes.svg';
import RingRatio from '../../../../static/images/svg/ring-ratio.svg';
import Threshold from '../../../../static/images/svg/threshold.svg';
import TimeSeriesForecasting from '../../../../static/images/svg/time-series-forecasting.svg';
import YearRound from '../../../../static/images/svg/year-round.svg';
import { createOnlyId } from '../../../../utils';
import {
  dataModeType,
  DetectionRuleTypeEnum,
  ICommonItem,
  IDetectionTypeItem,
  IDetectionTypeRuleData,
  MetricDetail
} from '../typings/index';

import { ChartType } from './components/intelligent-detect/intelligent-detect';
import RuleWrapper from './components/rule-wrapper/rule-wrapper';
import { IModelData } from './components/time-series-forecast/time-series-forecast';
import RulesSelect from './rules-select';

import './detection-rules.scss';

interface IDetectionRules {
  unit: string;
  connector: string;
  value: any;
  backfillData: any;
  readonly: boolean;
  metricData: MetricDetail[];
  unitType: string;
  isEdit?: boolean;
  dataMode?: dataModeType;
  needShowUnit: boolean;
}
interface IEvent {
  onUnitChange?: string;
  onChange?: any;
  onConnectorChange?: string;
  onAiopsTypeChange?: ChartType;
  onModelChange: IModelData[];
  onRuleClick: number;
}

@Component({ name: 'DetectionRules' })
export default class DetectionRules extends tsc<IDetectionRules, IEvent> {
  @Prop({ type: String, default: '' }) unit: string;
  @Prop({ default: '', type: String }) unitType: string;
  @Prop({ default: () => [], type: Array }) readonly value: any;
  @Prop({ default: () => [], type: Array }) readonly backfillData: any;
  @Prop({ default: false, type: Boolean }) readonly readonly: boolean;
  @Prop({ default: false, type: Boolean }) readonly isEdit: boolean;
  @Prop({ type: String, default: 'and' }) connector: string;
  @Prop({ default: () => {}, type: Array }) metricData: MetricDetail[];
  @Prop({ default: '', type: String }) dataMode: dataModeType;
  @Prop({ default: false, type: Boolean }) needShowUnit: boolean;

  /** 记录编辑进入第一次localValue值更新 */
  isFirstChange = true;

  unitList: ICommonItem[] = [];

  algorithmRelationship = [
    { id: 'and', name: window.i18n.t('且') },
    { id: 'or', name: window.i18n.t('或') }
  ];

  /** ruleWarp实例列表 */
  ruleWrapRefList: RuleWrapper[] = [];
  /** 已选择的检测规则算法 */
  addType: IDetectionTypeItem[] = [];
  /** 可选的检测规则算法列表 */
  detectionTypeList: IDetectionTypeItem[] = [
    {
      id: DetectionRuleTypeEnum.IntelligentDetect,
      type: 'ai',
      name: window.i18n.tc('单指标异常检测'),
      icon: IntelligentDetect,
      data: undefined,
      tip: '算法说明待产品补充',
      modelData: undefined,
      disabled: false,
      disabledTip: ''
    },
    {
      id: DetectionRuleTypeEnum.TimeSeriesForecasting,
      type: 'ai',
      name: window.i18n.tc('时序预测'),
      icon: TimeSeriesForecasting,
      data: undefined,
      tip: '算法说明待产品补充',
      modelData: undefined,
      disabled: false,
      disabledTip: ''
    },
    {
      id: DetectionRuleTypeEnum.AbnormalCluster,
      type: 'ai',
      name: window.i18n.tc('离群检测'),
      icon: AbnormalCluster,
      data: undefined,
      tip: '算法说明待产品补充',
      modelData: undefined,
      disabled: false,
      disabledTip: ''
    },
    {
      id: DetectionRuleTypeEnum.Threshold,
      type: 'convention',
      name: window.i18n.tc('静态阈值'),
      icon: Threshold,
      data: undefined,
      tip: '算法说明待产品补充',
      disabled: false,
      disabledTip: ''
    },
    {
      id: DetectionRuleTypeEnum.YearRound,
      child: [
        DetectionRuleTypeEnum.SimpleYearRound,
        DetectionRuleTypeEnum.AdvancedYearRound,
        DetectionRuleTypeEnum.YearRoundAmplitude,
        DetectionRuleTypeEnum.YearRoundRange
      ],
      type: 'convention',
      name: window.i18n.tc('同比策略'),
      icon: YearRound,
      data: undefined,
      tip: '算法说明待产品补充',
      disabled: false,
      disabledTip: ''
    },
    {
      id: DetectionRuleTypeEnum.RingRatio,
      child: [
        DetectionRuleTypeEnum.SimpleRingRatio,
        DetectionRuleTypeEnum.AdvancedRingRatio,
        DetectionRuleTypeEnum.RingRatioAmplitude
      ],
      type: 'convention',
      name: window.i18n.tc('环比策略'),
      icon: RingRatio,
      data: undefined,
      tip: '算法说明待产品补充',
      disabled: false,
      disabledTip: ''
    },
    {
      id: DetectionRuleTypeEnum.PartialNodes,
      type: 'convention',
      name: window.i18n.tc('部分节点数'),
      icon: PartialNodes,
      data: undefined,
      tip: '算法说明待产品补充',
      disabled: false,
      disabledTip: ''
    }
  ];
  /** 是否校验过 */
  hasValid = false;

  /** 是否为拨测icmp指标 */
  get isICMP(): boolean {
    return this.metricData[0].isICMP;
  }

  get aggMethod(): string {
    return this.metricData?.[0]?.agg_method || 'AVG';
  }

  get uptimeCheckType(): string {
    return this.metricData?.[0]?.metric_field;
  }

  /** 是否支持智能检测算法 时序预测条件一致 */
  get isCanSetAiops(): boolean {
    const { data_source_label: dataSourceLabel, data_type_label: dataTypeLabel, functions } = this.metricData[0] || {};
    return (
      this.metricData.length === 1 &&
      ['bk_data', 'bk_monitor'].includes(dataSourceLabel) &&
      dataTypeLabel === 'time_series' &&
      !functions?.length
    );
  }

  get getMethodList() {
    return THRESHOLD_METHOD_LIST;
  }

  get uptimeCheckMap() {
    const local = {
      available: DetectionRuleTypeEnum.Threshold,
      task_duration: DetectionRuleTypeEnum.Threshold,
      message: DetectionRuleTypeEnum.PartialNodes,
      response_code: DetectionRuleTypeEnum.PartialNodes
    };
    const list = this.$store.getters['strategy-config/uptimeCheckMap'];
    return list || local;
  }

  /** 是否为实时 */
  get isRealtime(): boolean {
    return this.dataMode === 'realtime';
  }

  /** 根据条件设置算法是否禁用 */
  get detectionTypeListFilter() {
    const uptimeItem = this.uptimeCheckMap?.[this.uptimeCheckType];
    // 是否已选择离群算法
    const hasAbnormalCluster = this.addType.some(item => item.id === DetectionRuleTypeEnum.AbnormalCluster);
    const list = this.detectionTypeList.map(item => {
      item.disabled = item.id === DetectionRuleTypeEnum.PartialNodes;

      // 聚合方法为实时 只能选择静态阈值
      if (this.aggMethod === 'REAL_TIME') {
        if (item.id !== DetectionRuleTypeEnum.Threshold) {
          item.disabled = true;
          item.disabledTip = this.$tc('不支持实时检测');
        }
      }

      // ICMP协议的拨测服务开放所有的检测算法选项、HTTP、TCP、UDP协议仅有静态阈值检测算法
      if (uptimeItem) {
        if (!this.isICMP) {
          item.disabled = item.id !== uptimeItem;
          item.disabledTip = this.$tc('不支持查询数据的来源和类型');
        }
      }

      /**
       * 离群检测和其他算法互斥
       * 1. 已选择离群检测，则其它选项禁用
       * 2. 没有选择离群检测且已选择其他选项，则离群检测禁用
       * */
      if (
        (hasAbnormalCluster && item.id !== DetectionRuleTypeEnum.AbnormalCluster) ||
        (!hasAbnormalCluster && !!this.addType.length && item.id === DetectionRuleTypeEnum.AbnormalCluster)
      ) {
        item.disabled = true;
        item.disabledTip = this.$tc('离群检测和其他算法互斥');
      }

      // 智能检测算法 | 时序预测算法一致 | 离群检测
      if (
        [
          DetectionRuleTypeEnum.IntelligentDetect,
          DetectionRuleTypeEnum.TimeSeriesForecasting,
          DetectionRuleTypeEnum.AbnormalCluster
        ].includes(item.id)
      ) {
        if (!this.isCanSetAiops) {
          item.disabled = true;
          item.disabledTip = this.$tc('只支持监控平台和计算平台的单指标数据');
        }
        if (!window.enable_aiops) {
          item.disabled = true;
          item.disabledTip = this.$tc('该功能依赖AIOps平台');
        }
      }

      // 智能算法规则
      if (item.type === 'ai') {
        const hasOne = this.addType.find(set => set.type === 'ai');
        if (hasOne) {
          item.disabled = true;
          item.disabledTip = this.$tc('暂不支持设置两个智能算法');
        }
      }

      // 常规算法
      if (item.type === 'convention') {
        const len = this.addType.filter(type => type.id === item.id).length;
        const childLen = item.child ? item.child.length : 1;
        if (len >= 3 * childLen) {
          item.disabled = true;
          item.disabledTip = this.$tc('常规算法不同等级只能各添加一种');
        }
      }

      return item;
    });
    return list;
  }

  get modelList() {
    return this.addType.reduce((pre, cur) => {
      cur.modelData && pre.push(cur.modelData);
      return pre;
    }, []);
  }

  get localValue() {
    return this.addType.map(item => deepClone(item.data));
  }

  /**
   * 监听回填数据
   * @param v 需要回填的数据
   */
  @Watch('backfillData', { immediate: true, deep: true })
  watchValueChange(v) {
    let value = deepClone(v);
    if (value && this.isEdit && this.isFirstChange) {
      // 编辑状态初次值更新将算法排序
      value = value.sort((a, b) => a.level - b.level);
      this.isFirstChange = false;
    }
    this.addType = value.map(item => {
      const type = this.detectionTypeList.find(item2 => item2.id === item.type || item2.child?.includes(item.type));
      return {
        ...type,
        key: createOnlyId(),
        data: item
      };
    });
  }

  /**
   * 监听指标变化，清理不支持的算法
   * @param val 指标数据
   */
  @Watch('metricData')
  watchMetricDataChange() {
    const val = this.addType;
    /**
     * 如果直接拿当前算法的禁用状态进行过滤，会导致一些特殊的算法规则（算法数量选择上限）被过滤掉
     * 所以先把值置空，然后计算出可以选用的算法，在进行恢复
     */
    this.addType = [];
    const disabledMap = this.detectionTypeListFilter.reduce((pre, cur) => {
      pre[cur.id] = cur.disabled;
      return pre;
    }, {});
    this.addType = val.filter(item => !disabledMap[item.id]);
    this.emitLocalValue();
  }

  @Watch('unitType', { immediate: true })
  unitTypeChange(unitType: string) {
    if (unitType) {
      this.getUnitInfo();
    } else {
      this.unitList = [];
    }
  }

  @Emit('change')
  emitLocalValue() {
    const hasIntelligentDetect = this.addType.some(item => item.data?.type === DetectionRuleTypeEnum.IntelligentDetect);
    if (!hasIntelligentDetect) this.handleAiopsChartTypeChange('none');
    return this.localValue;
  }

  @Emit('unitChange')
  handleUnitChange(v) {
    return v;
  }
  @Emit('connectorChange')
  emitConnector(v) {
    return v;
  }

  @Emit('aiopsTypeChange')
  handleAiopsChartTypeChange(type: ChartType) {
    return type;
  }

  get unitDisplay(): string {
    return (this.unitList.find(item => item.id === this.unit)?.name as string) || '';
  }

  /** 获取单位列表 */
  async getUnitInfo() {
    const data = await getUnitInfo({ unit_id: this.unitType }).catch(() => []);
    const list = data.unit_series.map(item => ({
      id: item.suffix,
      name: item.unit
    }));
    this.unitList = list;
    !this.unit && list[0] && this.handleUnitChange(list[0].id);
  }

  /**
   * @description: 添加算法类型
   * @param {string} type
   */
  handleAddRuleType(type: IDetectionTypeItem) {
    this.addType.push({
      ...deepClone(type),
      key: createOnlyId()
    });
  }

  /**
   * @description: 算法规则数据变化
   */
  handleRuleDataChange(val: IDetectionTypeRuleData, item: IDetectionTypeItem) {
    item.data = val;
    this.emitLocalValue();
  }

  /**
   * 删除算法类型
   */
  handleDeleteRule(ind: number) {
    this.addType.splice(ind, 1);
    this.ruleWrapRefList.splice(ind, 1);
    this.emitLocalValue();
  }

  @Emit('modelChange')
  @Watch('modelList')
  watchModelListChange() {
    return this.modelList;
  }
  /**
   * 模型数据变更
   * @param data 模型数据
   * @returns
   */
  handleModelChange(data: IModelData, item: IDetectionTypeItem) {
    item.modelData = data;
  }

  /**
   * ruleWrap组件实例挂载触发
   * 用于调用校验和清除校验方法
   * @param val 组件实例
   * @param index 索引
   */
  ruleWrapVMInit(val: RuleWrapper, index: number) {
    this.ruleWrapRefList.splice(index, 1, val);
  }

  clearErrorMsg() {
    this.ruleWrapRefList.forEach(vm => vm.clearError());
  }

  /**
   * 校验方法，判断是否选择了算法以及选择的算法是否都校验成功
   */
  validate() {
    this.hasValid = true;
    if (this.addType.length === 0) return Promise.reject();
    return Promise.all(this.ruleWrapRefList.map(vm => vm.validate()));
  }

  /**
   * 点击规则触发
   * @param item 被点击的规则
   * @returns 被点击规则在模型列表中的索引
   */
  @Emit('ruleClick')
  handleRuleClick(item: IDetectionTypeItem) {
    return this.modelList.findIndex(model => item.modelData === model);
  }

  render() {
    return (
      <div class='detection-rules-wrap'>
        <div class='detection-header'>
          <div class='left-des'>
            <i18n
              path='同级别的各算法之间是{0}的关系'
              class='i18n-path'
            >
              <bk-select
                class='inline-select'
                value={this.connector}
                behavior='simplicity'
                clearable={false}
                readonly={this.readonly}
                onChange={this.emitConnector}
              >
                {this.algorithmRelationship.map(opt => (
                  <bk-option
                    key={opt.id}
                    id={opt.id}
                    name={opt.name}
                  />
                ))}
              </bk-select>
            </i18n>
          </div>
          {this.unitList.length && this.needShowUnit ? (
            <div class='right-btn'>
              <span class=''>{this.$t('单位')}:&nbsp;</span>
              <MonitorSelect
                disabled={this.readonly}
                class='unit-select'
                list={this.unitList}
                value={this.unit}
                onChange={this.handleUnitChange}
              >
                {this.unitDisplay}
                <span class='icon-monitor icon-mc-triangle-down'></span>
              </MonitorSelect>
            </div>
          ) : undefined}
        </div>
        <div class='detection-list'>
          {this.addType.map((item, index) => (
            <div
              class='detection-list-item'
              onClick={() => this.handleRuleClick(item)}
            >
              <RuleWrapper
                key={item.key}
                rule={item}
                index={index}
                readonly={this.readonly}
                select-rule-data={this.localValue}
                is-realtime={this.isRealtime}
                is-edit={this.isEdit}
                data={item.data}
                metricData={this.metricData}
                unit={this.unitDisplay}
                resultTableId={this.metricData[0]?.intelligent_detect?.result_table_id}
                onDelete={() => this.handleDeleteRule(index)}
                onDataChange={val => this.handleRuleDataChange(val, item)}
                onModelChange={data => this.handleModelChange(data, item)}
                onChartTypeChange={this.handleAiopsChartTypeChange}
                onInitVM={val => this.ruleWrapVMInit(val, index)}
              />
            </div>
          ))}
        </div>
        {/* 添加按钮 */}
        <RulesSelect
          ref='rulesAddSelectRef'
          readonly={this.readonly}
          isFirst={this.localValue.length === 0}
          typeList={this.detectionTypeListFilter}
          onTypeChange={this.handleAddRuleType}
        ></RulesSelect>

        {this.hasValid && !this.addType.length && <p class='err-msg'>{this.$t('最少选择一个算法')}</p>}
      </div>
    );
  }
}
