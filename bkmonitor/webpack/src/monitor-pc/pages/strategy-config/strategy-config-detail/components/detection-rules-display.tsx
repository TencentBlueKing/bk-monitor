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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getUnitInfo } from 'monitor-api/modules/strategies';

import { CONDITION_METHOD_LIST, SIMPLE_METHOD_LIST } from '../../../../constant/constant';
import AbnormalCluster from '../../strategy-config-set-new/detection-rules/components/abnormal-cluster/abnormal-cluster';
import IntelligentDetect, {
  type ChartType,
} from '../../strategy-config-set-new/detection-rules/components/intelligent-detect/intelligent-detect';
import TimeSeriesForecast, {
  type IModelData,
} from '../../strategy-config-set-new/detection-rules/components/time-series-forecast/time-series-forecast';

import type {
  DetectionRuleTypeEnum,
  ICommonItem,
  IDetectionType,
  IDetectionTypeRuleData,
  MetricDetail,
} from '../../strategy-config-set-new/typings';

import './detection-rules-display.scss';

export interface IDetectionRulesItem extends IDetectionTypeRuleData {
  unit_prefix: string;
}
interface IEvents {
  onAiopsTypeChange: ChartType;
  onModelChange: IModelData;
}
interface IProps {
  metricData: MetricDetail[];
  value: IDetectionRulesItem;
}
@Component
export default class DetectionRulesDisplay extends tsc<IProps, IEvents> {
  @Prop({ type: Object }) value: IDetectionRulesItem;
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];

  /** 等级icons */
  levelIconMap: string[] = ['', 'icon-danger', 'icon-mind-fill', 'icon-tips'];
  /** 算法等级 */
  levelList: ICommonItem[] = [
    { id: 1, name: window.i18n.t('致命') },
    { id: 2, name: window.i18n.t('预警') },
    { id: 3, name: window.i18n.t('提醒') },
  ];
  /** 检测算法可选数据 */
  detectionTypeList: IDetectionType[] = [
    {
      id: 'IntelligentDetect',
      name: window.i18n.t('智能异常检测'),
      show: false,
      default: {
        sensitivity_value: 75,
        anomaly_detect_direct: 'all',
      },
    },
    {
      id: 'TimeSeriesForecasting',
      name: window.i18n.t('时序预测'),
      show: false,
      default: {
        args: {},
        duration: 1,
        plan_id: '',
        thresholds: [[{ method: 'gte', threshold: 0 }]],
        visual_type: 'forecasting',
      },
    },
    {
      id: 'AbnormalCluster',
      name: window.i18n.t('离群检测'),
      show: false,
      default: {
        args: {},
        plan_id: '',
      },
    },
    {
      id: 'Threshold',
      name: window.i18n.t('静态阈值'),
      show: false,
      default: [
        [
          {
            method: 'gte',
            threshold: 0,
          },
        ],
      ],
    },
    {
      id: 'AdvancedYearRound',
      name: window.i18n.t('同比（高级）'),
      show: false,
      default: {
        floor: '',
        floor_interval: '',
        ceil: '',
        ceil_interval: '',
      },
    },
    {
      id: 'AdvancedRingRatio',
      name: window.i18n.t('环比（高级）'),
      show: false,
      default: {
        floor: '',
        floor_interval: '',
        fetch_type: 'avg',
        ceil: '',
        ceil_interval: '',
      },
    },
    {
      id: 'SimpleYearRound',
      name: window.i18n.t('同比（简易）'),
      show: false,
      default: {
        floor: '',
        ceil: '',
      },
    },
    {
      id: 'SimpleRingRatio',
      name: window.i18n.t('环比（简易）'),
      show: false,
      default: {
        floor: '',
        ceil: '',
      },
    },
    {
      id: 'PartialNodes',
      name: window.i18n.t('部分节点数'),
      show: false,
      default: {
        count: 1,
      },
    },
    {
      id: 'YearRoundAmplitude',
      name: window.i18n.t('同比振幅'),
      show: false,
      default: {
        ratio: '',
        shock: '',
        days: '',
        method: 'gte',
      },
    },

    {
      id: 'RingRatioAmplitude',
      name: window.i18n.t('环比振幅'),
      show: false,
      default: {
        ratio: '',
        shock: '',
        threshold: '',
      },
    },
    {
      id: 'YearRoundRange',
      name: window.i18n.t('同比区间'),
      show: false,
      default: {
        ratio: '',
        shock: '',
        days: '',
        method: 'gte',
      },
    },
  ];

  rateOfChangeList: ICommonItem[] = [
    {
      id: 'ceil',
      name: window.i18n.tc('向上'),
    },
    {
      id: 'floor',
      name: window.i18n.tc('向下'),
    },
    {
      id: 'all',
      name: window.i18n.tc('向上或向下'),
    },
  ];

  advancedYearRoundTplData = [
    { value1: 'ceil_interval', value2: 'ceil', value3: 'fetch_type', text: window.i18n.t('升') },
    { value1: 'floor_interval', value2: 'floor', value3: 'fetch_type', text: window.i18n.t('降') },
  ];

  simpleRoundTplData = [
    { value: 'ceil', text: window.i18n.t('升') },
    { value: 'floor', text: window.i18n.t('降') },
  ];

  /** 单位列表 */
  unitList = [];

  fetchTypeMapping = {
    avg: this.$t('均值'),
    last: this.$t('瞬间值'),
  };

  get levelName() {
    return this.levelList.find(item => item.id === this.value.level)?.name;
  }
  get levelIcon() {
    return this.levelIconMap[this.value.level] || '';
  }
  get rulesName() {
    const item = this.detectionTypeList.find(item => item.id === this.value.type);
    return item?.name || '';
  }
  get config() {
    return this.value.config;
  }

  /** 单位类型 */
  get unitType() {
    return this.metricData[0]?.unit;
  }

  /** 单位的显示值 */
  get unitDisplay(): string {
    return (this.unitList.find(item => item.id === this.value.unit_prefix)?.name as string) || '';
  }

  mounted() {
    !!this.value.unit_prefix && this.value.type === 'Threshold' && this.getUnitInfo();
  }

  // 获取单位列表
  async getUnitInfo() {
    const data = await getUnitInfo({ unit_id: this.unitType }).catch(() => []);
    const list = data.unit_series.map(item => ({
      id: item.suffix,
      name: item.unit,
    }));
    this.unitList = list;
  }

  getCurrentMethod(method) {
    return SIMPLE_METHOD_LIST.find(item => item.id === method)?.name || method;
  }

  getCurrentAiDirect(type) {
    return this.rateOfChangeList.find(item => item.id === type)?.name || type;
  }

  /** 处理算法内容部分 */
  handleContentTpl() {
    const contentMap: Partial<Record<DetectionRuleTypeEnum, () => void>> = {
      // 环比策略（高级）
      AdvancedRingRatio: () => this.advancedYearRoundTpl(this.value.type),
      // 同比策略（高级）
      AdvancedYearRound: () => this.advancedYearRoundTpl(this.value.type),
      // 智能异常检测
      IntelligentDetect: this.intelligentDetectTpl,
      // 部分节点数
      PartialNodes: this.partialNodesTpl,
      // 环比振幅
      RingRatioAmplitude: this.ringRatioAmplitudeTpl,
      // 环比策略（简易）
      SimpleRingRatio: () => this.simpleRingTpl(this.value.type),
      // 同比策略（简易）
      SimpleYearRound: () => this.simpleRingTpl(this.value.type),
      /** 静态阈值 */
      Threshold: this.thresholdTpl,
      // 同比振幅
      YearRoundAmplitude: this.yearRoundAmplitudeTpl,
      // 同比区间
      YearRoundRange: this.yearRoundRangeTpl,
      // 时序预测
      TimeSeriesForecasting: this.timeSeriesForecastingTpl,
      // 离群检测
      AbnormalCluster: this.handleOutlierDetecTpl,
    };
    return contentMap[this.value.type]();
  }

  /**
   * 模型数据变更
   * @param data IModelData(时序预测)
   * @returns
   */
  @Emit('modelChange')
  handleModelChange(data: IModelData) {
    return data;
  }

  @Emit('aiopsTypeChange')
  handleAiopsChartTypeChange(type: ChartType) {
    return type;
  }

  intelligentDetectTpl() {
    return (
      <IntelligentDetect
        data={this.value}
        interval={this.metricData[0].agg_interval}
        resultTableId={this.metricData[0]?.intelligent_detect?.result_table_id}
        readonly
        onChartTypeChange={this.handleAiopsChartTypeChange}
        onModelChange={this.handleModelChange}
      />
    );
  }

  timeSeriesForecastingTpl() {
    return (
      <TimeSeriesForecast
        data={this.value}
        interval={this.metricData?.[0]?.agg_interval}
        methodList={CONDITION_METHOD_LIST}
        unit={this.unitDisplay}
        readonly
        onModelChange={this.handleModelChange}
      />
    );
  }

  handleOutlierDetecTpl() {
    return (
      <AbnormalCluster
        data={this.value}
        interval={this.metricData[0].agg_interval}
        metricData={this.metricData}
        readonly
      />
    );
  }
  advancedYearRoundTpl(type) {
    return this.advancedYearRoundTplData.map((item, index) => {
      const template = {
        AdvancedYearRound: (
          <div class='rules-item advanced-item'>
            <i18n
              class='i18n-path'
              path='较前{0}天同一时刻绝对值的{1}{2}时触发告警'
            >
              <span class='i18n-span'>{this.config[item.value1] || '--'}</span>
              <span class='i18n-span'>{this.fetchTypeMapping[this.config[item.value3]] || this.$t('均值')}</span>
              <span class='i18n-span advance-status'>
                <span class={`status-${index === 0 ? 'green' : 'red'}`}>{item.text}</span>&nbsp;
                {this.config[item.value2] || '--'}%
              </span>
            </i18n>
          </div>
        ),
        AdvancedRingRatio: (
          <div class='rules-item advanced-item'>
            <i18n
              class='i18n-path'
              path='较前{0}个时间点的{1}{2}时触发告警'
            >
              <span class='i18n-span'>{this.config[item.value1] || '--'}</span>
              <span class='i18n-span'>{this.fetchTypeMapping[this.config[item.value3]] || this.$t('均值')}</span>
              <span class='i18n-span advance-status'>
                <span class={`status-${index === 0 ? 'green' : 'red'}`}>{item.text}</span>&nbsp;
                {this.config[item.value2] || '--'}%
              </span>
            </i18n>
          </div>
        ),
      };
      return template[type];
    });
  }

  simpleRingTpl(type) {
    return this.simpleRoundTplData.map((item, index) => (
      <div
        key={index}
        class='rules-item simple-ring-item'
      >
        <i18n
          class='i18n-path'
          path={type === 'SimpleYearRound' ? '当前值较上周同一时刻{0}时触发告警' : '当前值较前一时刻{0}时触发告警'}
        >
          <span>
            <span class='i18n-span advance-status'>
              <span class={`status-${index === 0 ? 'green' : 'red'}`}>{item.text}</span>&nbsp;
              {this.config[item.value] || '--'}%
            </span>
          </span>
        </i18n>
      </div>
    ));
  }

  yearRoundAmplitudeTpl() {
    return (
      <div class='rules-item'>
        <i18n
          class='i18n-path'
          path='(当前值 - 前一时刻值){0}过去{1}天内任意一天同时刻的 (差值 ×{2}+{3}) 时触发告警'
        >
          <span class='i18n-span'>{this.getCurrentMethod(this.config.method)}</span>
          <span class='i18n-span'>{this.config.days}</span>
          <span class='i18n-span'>{this.config.ratio}</span>
          <span class='i18n-span'>{this.config.shock}</span>
        </i18n>
      </div>
    );
  }

  ringRatioAmplitudeTpl() {
    return (
      <div class='rules-item'>
        <i18n
          class='i18n-path'
          path='当前值与前一时刻值 >={0}且，之间差值 >= 前一时刻 ×{1}+{2}'
        >
          <span class='i18n-span'>{this.config.threshold}</span>
          <span class='i18n-span'>{this.config.ratio}</span>
          <span class='i18n-span'>{this.config.shock}</span>
        </i18n>
      </div>
    );
  }

  yearRoundRangeTpl() {
    return (
      <div class='rules-item'>
        <i18n
          class='i18n-path'
          path='当前值 {0} 过去{1}天内同时刻绝对值 ×{2}+{3}'
        >
          <span class='i18n-span'>{this.getCurrentMethod(this.config.method)}</span>
          <span class='i18n-span'>{this.config.days}</span>
          <span class='i18n-span'>{this.config.ratio}</span>
          <span class='i18n-span'>{this.config.shock}</span>
        </i18n>
      </div>
    );
  }

  partialNodesTpl() {
    return (
      <div class='rules-item'>
        <i18n path='满足以上条件的拨测节点数>={0}时触发告警'>
          <span class='i18n-span'>{this.config.count}</span>
        </i18n>
      </div>
    );
  }

  thresholdTpl() {
    const localValue = [];
    this.config.forEach((item, index) => {
      item.forEach((child, i) => {
        const isAnd = index === 0 || i !== 0;
        const method = CONDITION_METHOD_LIST.find(item => item.id === child.method)?.name;
        localValue.push({
          method,
          value: child.threshold,
          condition: isAnd ? 'AND' : 'OR',
        });
      });
    });
    return localValue.map((item, index) => (
      <span
        key={index}
        class='threshold-item'
      >
        {index !== 0 && <span class='item-condition'>&nbsp;{item.condition}&nbsp;</span>}
        <span class='item-method'>{item.method}&nbsp;</span>
        <span class='item-value'>{item.value}</span>
        {this.value.unit_prefix ? <span class='item-unit'>{this.unitDisplay || ''}</span> : undefined}
      </span>
    ));
  }

  render() {
    return (
      <div class='detection-rules-display'>
        <div class='detec-rules-header'>
          <i class={['icon-monitor', this.levelIcon]} />
          <span class='level-name'>{this.levelName}</span>
          <span class='rules-name'>{this.rulesName}</span>
        </div>
        <div class='detec-rules-content'>{this.handleContentTpl()}</div>
      </div>
    );
  }
}
