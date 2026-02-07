/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent } from 'vue';

import AlarmCharts from './echarts/alarm-charts';
// import AiopsCharts from './echarts/aiops-charts';
// import IntelligenceScene from './echarts/intelligence-scene';
// import OutlierDetectionChart from './echarts/outlier-detection-chart';
// import TimeSeriesForecastingChart from './echarts/time-series-forecasting-chart';
// import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import type { AlarmDetail } from '@/pages/alarm-center/typings';
import type { DateValue } from '@blueking/date-picker';

import './chart-wrapper.scss';

/** 算法类型常量 */
// const ALGORITHM_TYPES = {
//   INTELLIGENT_DETECT: 'IntelligentDetect',
//   ABNORMAL_CLUSTER: 'AbnormalCluster',
//   TIME_SERIES_FORECASTING: 'TimeSeriesForecasting',
// } as const;

export default defineComponent({
  name: 'ChartWrapper',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
    /** 业务ID */
    bizId: {
      type: Number,
    },
    /** 默认时间范围 */
    defaultTimeRange: {
      type: Array as unknown as PropType<DateValue>,
    },
  },
  setup(props) {
    /** 是否为主机智能场景检测视图 */
    // const isHostAnomalyDetection = computed(() => {
    //   return props.detail?.extra_info?.strategy?.items?.[0]?.algorithms?.[0].type === MetricType.HostAnomalyDetection;
    // });

    // const detectionConfig = computed<IDetectionConfig>(() => {
    //   const strategy = props.detail.extra_info?.strategy;
    //   const algorithms = strategy?.items?.[0]?.algorithms;
    //   if (!algorithms?.length) return null;
    //   const result = {
    //     unit: algorithms[0].unit_prefix,
    //     // @ts-expect-error
    //     unitType: strategy.items?.[0]?.query_configs?.[0]?.unit || '',
    //     unitList: [],
    //     connector: strategy.detects?.[0]?.connector as 'and' | 'or',
    //     data: algorithms.map(({ unit_prefix, ...item }) => displayDetectionRulesConfig(item)),
    //     query_configs: strategy?.items?.[0]?.query_configs,
    //   };
    //   return result;
    // });

    /** 是否含有智能检测算法 */
    // const hasAIOpsDetection = computed(
    //   () =>
    //     hasAlgorithmType(ALGORITHM_TYPES.INTELLIGENT_DETECT) &&
    //     detectionConfig.value?.query_configs?.[0]?.intelligent_detect?.result_table_id
    // );

    /** 是否含有离群检测算法 */
    // const hasOutlierDetection = computed(() => hasAlgorithmType(ALGORITHM_TYPES.ABNORMAL_CLUSTER));

    /** 是否含有时序预测算法 */
    // const hasTimeSeriesForecasting = computed(() => hasAlgorithmType(ALGORITHM_TYPES.TIME_SERIES_FORECASTING));

    /**
     * @description 检查是否包含指定类型的算法
     * @param {string} type 算法类型
     * @returns 是否包含该类型算法
     */
    // const hasAlgorithmType = (type: string) => detectionConfig.value?.data?.some?.(item => item.type === type);

    /**
     * @description 处理检测规则配置，对配置项进行标准化处理
     * @param item 检测算法配置项
     * @returns 处理后的配置项
     */
    // const displayDetectionRulesConfig = item => {
    //   const { config } = item;
    //   if (item.type === ALGORITHM_TYPES.INTELLIGENT_DETECT && !config.anomaly_detect_direct) {
    //     config.anomaly_detect_direct = 'all';
    //   }
    //   if (typeTools.isArray(config)) return item;

    //   for (const key of Object.keys(config)) {
    //     if (config[key] === null) config[key] = '';
    //   }
    //   return item;
    // };

    /**
     * @description 根据告警类型获取对应的图表组件
     * @returns 对应的图表组件 JSX
     */
    const getSeriesViewComponent = () => {
      // // 主机智能场景检测
      // if (isHostAnomalyDetection.value) {
      //   return <IntelligenceScene detail={props.detail} />;
      // }
      // // 智能检测算法图表
      // if (hasAIOpsDetection.value) {
      //   return (
      //     <AiopsCharts
      //       detail={props.detail}
      //       detectionConfig={detectionConfig.value}
      //     />
      //   );
      // }
      // // 时序预测图表
      // if (hasTimeSeriesForecasting.value) {
      //   return (
      //     <TimeSeriesForecastingChart
      //       detail={props.detail}
      //       detectionConfig={detectionConfig.value}
      //     />
      //   );
      // }
      // if (hasOutlierDetection.value) {
      //   return <OutlierDetectionChart detail={props.detail} />;
      // }
      return (
        <div class='series-view-container'>
          <AlarmCharts
            bizId={props.bizId}
            defaultTimeRange={props.defaultTimeRange}
            detail={props.detail}
          />
        </div>
      );
    };

    return {
      getSeriesViewComponent,
    };
  },

  render() {
    return <div class={['alarm-view-chart-wrapper']}>{this.getSeriesViewComponent()}</div>;
  },
});
