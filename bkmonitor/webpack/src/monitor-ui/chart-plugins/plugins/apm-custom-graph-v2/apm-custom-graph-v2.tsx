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

import { Component, Inject, InjectReactive, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import ApmCustomGraphV2 from 'monitor-pc/pages/custom-escalation/metric-detail/components/view-main';
import {
  createOrUpdateGroupingRule,
  customTimeSeriesDetail,
  customTimeSeriesList,
  customTsGroupingRuleList,
  deleteGroupingRule,
  exportCustomTimeSeriesFields,
  getCustomTimeSeriesLatestDataByFields,
  getCustomTsDimensionValues,
  getCustomTsFields,
  getCustomTsGraphConfig,
  getCustomTsMetricGroups,
  getSceneView,
  getUnitList,
  importCustomTimeSeriesFields,
  modifyCustomTimeSeries,
  // modifyCustomTsFields, // 使用apm接口
  previewGroupingRule,
  proxyHostInfo,
  validateCustomTsGroupLabel,
  validateCustomTsGroupName,
} from 'monitor-pc/pages/custom-escalation/service';
import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import { modifyCustomTsFields } from './service';

import type { ApmRequestHandlerMap } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { RequestHandlerMap } from 'monitor-pc/pages/custom-escalation/metric-detail/type';

import './apm-custom-graph-v2.scss';

type CombinedRequestHandlerMap = MergeWithPriority<RequestHandlerMap, ApmRequestHandlerMap>;
type GetSceneViewParams = Parameters<typeof getSceneView>[0];


type MergeWithPriority<T1, T2> = {
  [K in keyof T1 | keyof T2]: K extends keyof T2 ? T2[K] : K extends keyof T1 ? T1[K] : never;
};

@Component({
  name: 'ApmCustomGraphV2',
})
export default class ApmViewContent extends tsc<any, any> {
  // @Prop({ default: -1, type: Number }) timeSeriesGroupId: number;
  @ProvideReactive('timeRange') timeRange: TimeRangeType = [this.startTime, this.endTime];
  // @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('showRestore') showRestore = false;
  @ProvideReactive('containerScrollTop') containerScrollTop = 0;
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  @Provide('requestHandlerMap') requestHandlerMap: CombinedRequestHandlerMap = {
    getCustomTsMetricGroups, // 详情页
    customTimeSeriesList, // 详情页
    customTimeSeriesDetail, // 详情页面暂未使用过
    getCustomTsFields, // 详情页面暂未使用
    modifyCustomTsFields, // 详情页
    createOrUpdateGroupingRule, // 详情页面暂未使用
    customTsGroupingRuleList, // 详情页面暂未使用
    getCustomTimeSeriesLatestDataByFields, // 详情页面暂未使用
    getCustomTsDimensionValues, // 详情页
    getCustomTsGraphConfig, // 详情页
    getSceneView, // 详情页
    previewGroupingRule,
    modifyCustomTimeSeries,
    importCustomTimeSeriesFields,
    exportCustomTimeSeriesFields,
    validateCustomTsGroupName,
    validateCustomTsGroupLabel,
    deleteGroupingRule,
    proxyHostInfo,
    getUnitList,
  };
  // @InjectReactive('viewOptions') readonly viewOptions;
  @InjectReactive('customRouteQuery') customRouteQuery: Record<string, string>;
  @Inject('handleCustomRouteQueryChange') handleCustomRouteQueryChange: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  // @Provide('handleChartDataZoom')
  // handleChartDataZoom(value) {
  //   if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
  //     this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
  //     this.timeRange = value;
  //     this.showRestore = true;
  //   }
  // }
  // @Provide('handleRestoreEvent')
  // handleRestoreEvent() {
  //   this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
  //   this.showRestore = false;
  // }

  cacheTimeRange = [];
  dimenstionParams: GetSceneViewParams | null = null;
  isCustomTsMetricGroupsLoading = true;

  get metricGroupList() {
    return customEscalationViewStore.metricGroupList;
  }

  get startTime() {
    return customEscalationViewStore.startTime;
  }

  get endTime() {
    return customEscalationViewStore.endTime;
  }

  get selectedMetricsData() {
    return customEscalationViewStore.currentSelectedMetricList.map(item => {
      return {
        name: item.metric_name,
        scope_name: item.scope_name,
      };
    });
  }

  get graphConfigParams() {
    return {
      limit: {
        function: 'top' as const, // top/bottom
        limit: 50, // 0不限制
      },
      view_column: 2,
      ...this.dimenstionParams,
      metrics: this.selectedMetricsData,
    };
  }

  // @Watch('serviceName')
  // timeSeriesGroupIdChange() {
  //   this.isCustomTsMetricGroupsLoading = true;
  // }

  @Watch('isCustomTsMetricGroupsLoading')
  isCustomTsMetricGroupsLoadingChange(v) {
    if (!v) {
      this.$nextTick(() => {
        this.initScroll();
      });
    }
  }

  @Watch('selectedMetricsData')
  selectedMetricsDataChange() {
    this.updateUrlParams();
  }

  getGroupDataSuccess() {
    this.parseUrlParams();
    this.isCustomTsMetricGroupsLoading = false;
  }

  initScroll() {
    const container = document.querySelector('.metric-view-dashboard-container') as HTMLElement;
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
      container.addEventListener('scroll', this.handleScroll);
    }
  }

  removeScrollEvent() {
    const container = document.querySelector('.metric-view-dashboard-container') as HTMLElement;
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
    }
  }

  handleScroll(e) {
    if (e.target.scrollTop > 0) {
      this.containerScrollTop = e.target.scrollTop;
    }
  }

  // 回显 转换url参数
  parseUrlParams() {
    const urlData = this.getUrlParams();
    if (urlData) {
      // 过滤条件和维度回显
      this.dimenstionParams = {
        ...urlData,
        metrics: undefined,
      };
      // 分组选中
      const convertData = this.convertMetricsData(urlData.metrics);
      // 视图保存的 metric 可能被隐藏，需要过滤掉不存在的 metric
      const allMetricNameMap = this.metricGroupList.map(group => {
        return {
          groupName: group.name,
          metricsName: group.metrics.map(metric => metric.metric_name),
        };
      });
      // 过滤掉不存在的分组数据
      const realMetricNameList = _.filter(convertData, item => {
        // 是否有对应的分组名称
        const group = allMetricNameMap.find(group => group.groupName === item.groupName);
        if (!group) return false;
        // 检查该 groupName 下的 metricsName 是否包含 item.metricsName 数组中的每个值
        return item.metricsName.every(metric => group.metricsName.includes(metric));
      });
      // 更新 Store 上的 已选中分组和指标信息(currentSelectedGroupAndMetricNameList)
      customEscalationViewStore.updateCurrentSelectedGroupAndMetricNameList(realMetricNameList);
    }
  }

  handleDimensionParamsChange(payload: GetSceneViewParams) {
    this.dimenstionParams = Object.freeze(payload);
    this.updateUrlParams();
  }

  handleMetricsSelectReset() {
    this.dimenstionParams = null;
    this.updateUrlParams();
  }

  // 更新url参数
  updateUrlParams() {
    this.handleCustomRouteQueryChange({
      viewPayload: JSON.stringify(this.graphConfigParams),
    });

    // this.$router.replace({
    //   query: {
    //     ...this.$route.query,
    //     key: `${Date.now()}`, // query 相同时 router.replace 会报错
    //     viewPayload: JSON.stringify(this.graphConfigParams),
    //   },
    // });
  }

  // 获取url参数
  getUrlParams() {
    const { viewPayload } = this.customRouteQuery;
    if (!viewPayload) {
      return undefined;
    }
    const paylaod = JSON.parse((viewPayload as string) || '') as GetSceneViewParams;
    return _.isObject(paylaod) ? paylaod : undefined;
  }

  convertMetricsData(data) {
    return data.reduce((result, item) => {
      const groupName = item.scope_name;
      // 查找是否已有此分组
      const existingGroup = result.find(group => group.groupName === groupName);
      if (existingGroup) {
        existingGroup.metricsName.push(item.name);
      } else {
        result.push({
          groupName,
          viewTab: 'default',
          metricsName: [item.name],
        });
      }
      return result;
    }, []);
  }

  handleSideslider() {
    // 打开指标管理抽屉
  }

  render() {
    return (
      <div
        class='apm-custom-graph-v2 bk-monitor-new-metric-view'
        v-bkloading={{ isLoading: this.isCustomTsMetricGroupsLoading }}
      >
        <ApmCustomGraphV2
          config={this.graphConfigParams}
          dimenstionParams={this.dimenstionParams}
          isApm={true}
          onCustomTsMetricGroups={this.getGroupDataSuccess}
          onDimensionParamsChange={this.handleDimensionParamsChange}
          onOpenSideslider={this.handleSideslider}
          onResetMetricsSelect={this.handleMetricsSelectReset}
        />
      </div>
    );
  }
}
