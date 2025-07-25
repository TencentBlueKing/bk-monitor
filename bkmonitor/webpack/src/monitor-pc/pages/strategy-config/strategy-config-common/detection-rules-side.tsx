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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';
import { getMetricListV2, updatePartialStrategyV2 } from 'monitor-api/modules/strategies';
import { deepClone, typeTools } from 'monitor-common/utils';

import { transformLogMetricId } from '../strategy-config-detail/utils';
import DetectionRules from '../strategy-config-set-new/detection-rules/detection-rules';
import { MetricDetail } from '../strategy-config-set-new/typings';

import './detection-rules-side.scss';

interface IProps {
  show?: boolean;
  strategyData?: any;
  onShowChange?: (show: boolean) => void;
  onSuccess?: () => void;
}

@Component
export default class DetectionRulesSide extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: null }) strategyData: any;

  @Ref('detection-rules') readonly detectionRulesEl: InstanceType<typeof DetectionRules>;

  detectionConfig = {
    unit: '',
    unitType: '', // 单位类型
    unitList: [],
    connector: 'and',
    data: [],
  };
  metricData = [];
  dataMode = 'converge';
  backfillData = [];
  metricFunctions = [];
  loading = true;

  @Watch('show')
  async onShowChange() {
    if (this.show) {
      await this.getMetricData();
    }
  }

  async getMetricData() {
    const { queryConfigs, objectType, targetNodeType: nodeType, metricType, algorithms, detects } = this.strategyData;
    const { metric_list: metricList = [] } = await getMetricListV2({
      bk_biz_id: this.strategyData.bizId,
      conditions: [{ key: 'metric_id', value: queryConfigs.map(item => transformLogMetricId(item)) }],
    }).catch(() => ({}));
    this.metricData = queryConfigs.map(
      ({
        data_source_label,
        data_type_label,
        result_table_id,
        data_label,
        unit,
        index_set_id,
        functions,
        intelligent_detect,
        metric_field,
        metric_id,
        agg_method,
        agg_condition = [],
        agg_dimension = [],
        agg_interval,
        alias,
        query_string,
        custom_event_name,
        bkmonitor_strategy_id,
      }) => {
        const curMetric = metricList?.find(set => set.metric_id === metric_id) || {
          data_source_label,
          data_type_label,
          metric_field,
          metric_field_name: metric_field,
          metric_id,
          result_table_id,
          data_label,
          unit,
          index_set_id,
          query_string,
          custom_event_name,
          bkmonitor_strategy_id,
          dimensions: [],
        };

        this.dataMode =
          agg_method === 'REAL_TIME' || (data_type_label === 'event' && data_source_label === 'bk_monitor')
            ? 'realtime'
            : 'converge';

        return new MetricDetail({
          ...curMetric,
          agg_method,
          agg_condition: this.getAggConditionOfHasDimensionName(agg_condition, curMetric),
          agg_dimension,
          agg_interval,
          alias: (alias || '').toLocaleLowerCase(),

          targetType: nodeType,
          objectType: objectType,
          query_string,
          functions: functions || [],
          intelligent_detect,
          metric_type: metricType,
          logMetricList: metricList,
        });
      }
    );
    await this.handleGetMetricFunctions();
    // 检测算法数据回显
    this.handleDetectionRulesUnit();
    this.detectionConfig.data = algorithms.map(({ unit_prefix, ...item }) => this.displayDetectionRulesConfig(item));
    this.detectionConfig.unit = algorithms?.[0]?.unit_prefix || '';
    this.detectionConfig.connector = detects?.[0]?.connector || 'and';
    this.backfillData = deepClone(this.detectionConfig.data);
  }

  getAggConditionOfHasDimensionName(aggCondition = [], curMetric = null) {
    return (aggCondition || [])
      .filter(setCondition => setCondition.key)
      .map(setCondition => ({
        ...setCondition,
        dimensionName: (() => {
          const dimensions = JSON.parse(JSON.stringify(curMetric?.dimensions || []));
          const dimensionName = dimensions.find(d => d.id === setCondition.key)?.name;
          const temp = dimensionName || setCondition?.dimensionName || setCondition?.dimension_name;
          return temp || setCondition.key;
        })(),
        value: typeof setCondition.value === 'string' ? setCondition.value.split(',') : setCondition.value,
      }));
  }

  // 检测算法回显空数据转换
  displayDetectionRulesConfig(item) {
    const { config } = item;
    if (item.type === 'IntelligentDetect' && !config.anomaly_detect_direct) config.anomaly_detect_direct = 'all';
    // 如果服务端没有返回 fetch_type 数据，这里将提供一个默认的数值。（向前兼容）

    if (['AdvancedRingRatio', 'AdvancedYearRound'].includes(item.type) && !config.fetch_type) config.fetch_type = 'avg';
    const isArray = typeTools.isArray(config);
    if (isArray) return item;
    for (const key in config) {
      const value = config[key];
      if (value === null) config[key] = '';
    }
    return item;
  }

  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }
  // 处理检测算法单位
  handleDetectionRulesUnit() {
    let notNeededDetectionUnit = false; //  handleResetMetricAlias不需要算法单位 汇聚方法为COUNT || 函数有ignore_unit: true的不需要算法单位
    const len = this.metricData.length;
    if (len === 1) {
      const firstMetric = this.metricData[0];
      const allFuncList = this.metricFunctions.reduce((total, cur) => total.concat(cur.children), []);
      const ignoreUnit = firstMetric.functions.some(
        item => !!allFuncList.find(set => item.id === set.id && set.ignore_unit)
      );
      notNeededDetectionUnit = firstMetric.agg_method === 'COUNT' || ignoreUnit;
    }
    if (!len || len > 1 || notNeededDetectionUnit) {
      this.detectionConfig.unit = '';
      this.detectionConfig.unitType = '';
    } else {
      this.detectionConfig.unitType = this.metricData[0].unit;
      if (!this.detectionConfig.unitType) {
        this.detectionConfig.unit = '';
      }
    }
  }

  // 检测算法值更新
  handleDetectionRulesChange(v) {
    this.detectionConfig.data = v;
  }

  handleClose() {
    this.$emit('showChange', false);
  }

  async handleConfirm() {
    const validate = await this.detectionRulesEl
      .validate()
      .then(() => true)
      .catch(() => false);
    if (validate) {
      const params = {
        algorithms: this.detectionConfig.data,
      };
      await updatePartialStrategyV2({
        ids: [this.strategyData.id],
        edit_data: params,
      })
        .then(() => {
          this.$bkMessage({ theme: 'success', message: this.$t('修改检测规则成功'), ellipsisLine: 0 });
          this.$emit('success', params);
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }

  handleCancel() {
    this.handleClose();
  }

  render() {
    return (
      <bk-sideslider
        width={960}
        ext-cls='strategy-detection-rules-side'
        before-close={this.handleClose}
        is-show={this.show}
        quick-close={true}
        transfer={true}
        z-index={1000}
      >
        <div slot='header'>
          <span>{this.$t('检测规则详情')}</span>
        </div>
        <div
          class='strategy-detection-rules-side-content'
          slot='content'
        >
          <DetectionRules
            key={+this.show}
            ref='detection-rules'
            backfillData={this.backfillData}
            connector={this.detectionConfig.connector}
            dataMode={this.dataMode}
            isEdit={true}
            metricData={this.metricData}
            needShowUnit={true}
            unit={this.detectionConfig.unit}
            unitType={this.detectionConfig.unitType}
            onChange={this.handleDetectionRulesChange}
          />
          <div class='mt-32'>
            <bk-button
              class='mr-8 button-88'
              theme='primary'
              onClick={this.handleConfirm}
            >
              {this.$t('提交')}
            </bk-button>
            <bk-button
              class='button-88'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
