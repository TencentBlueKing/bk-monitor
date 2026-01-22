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

import { Component, Inject, InjectReactive, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import { modifyCustomTsFields } from 'monitor-api/modules/apm_custom_metric';
import ApmCustomGraphV2 from 'monitor-pc/pages/custom-escalation/metric-detail/components/view-main';
import {
  getCustomTsDimensionValues,
  getCustomTsGraphConfig,
  getCustomTsMetricGroups,
  getSceneView,
} from 'monitor-pc/pages/custom-escalation/service';
import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import MetricManage from './components/metric-manage';

import './apm-custom-graph-v2.scss';

type GetSceneViewParams = Parameters<typeof getSceneView>[0];

@Component({
  name: 'ApmCustomGraphV2',
})
export default class ApmViewContent extends tsc<any, any> {
  @ProvideReactive('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('containerScrollTop') containerScrollTop = 0;
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  @InjectReactive('customRouteQuery') customRouteQuery: Record<string, string>;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @Inject('handleCustomRouteQueryChange') handleCustomRouteQueryChange: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  @Ref('apmCustomGraphV2Ref') apmCustomGraphV2Ref: ApmCustomGraphV2;

  metricTimeRange: TimeRangeType = [this.startTime, this.endTime];
  dimenstionParams: GetSceneViewParams | null = null;
  loading = true;
  isShowMetricManage = false;
  metricManageTab: 'metric' | 'dimension' = 'metric';

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

  @Watch('selectedMetricsData')
  selectedMetricsDataChange() {
    this.updateUrlParams();
  }

  @Watch('timeRange', { immediate: true })
  setTimeRange(v) {
    this.metricTimeRange = v;
  }

  getGroupDataSuccess() {
    this.parseUrlParams();
    this.loading = false;
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

  // 打开指标管理抽屉
  handleMetricManage(tab: 'dimension' | 'metric') {
    this.metricManageTab = tab;
    this.isShowMetricManage = true;
  }

  // 刷新指标和分组的数据
  handleRefreshGroupData() {
    this.apmCustomGraphV2Ref.getCustomTsMetricGroupsData();
  }

  render() {
    return (
      <div
        class='apm-custom-graph-v2 bk-monitor-new-metric-view'
        v-bkloading={{ isLoading: this.loading }}
      >
        <ApmCustomGraphV2
          ref='apmCustomGraphV2Ref'
          requestMap={{
            modifyCustomTsFields, // apm可视化页面只有此接口用新的，下面接口用原有的
            getCustomTsMetricGroups,
            getCustomTsDimensionValues,
            getCustomTsGraphConfig,
            getSceneView,
          }}
          config={this.graphConfigParams}
          dimenstionParams={this.dimenstionParams}
          isApm={true}
          metricTimeRange={this.metricTimeRange}
          onCustomTsMetricGroups={this.getGroupDataSuccess}
          onDimensionParamsChange={this.handleDimensionParamsChange}
          onMetricManage={this.handleMetricManage}
          onResetMetricsSelect={this.handleMetricsSelectReset}
        />
        <MetricManage
          isShow={this.isShowMetricManage}
          tab={this.metricManageTab}
          onCancel={() => {
            this.isShowMetricManage = false;
          }}
          onAliasChange={this.handleRefreshGroupData}
          onGroupListChange={this.handleRefreshGroupData}
        />
      </div>
    );
  }
}
