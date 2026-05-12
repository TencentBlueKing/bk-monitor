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

import { type PropType, defineComponent, shallowRef, toRef } from 'vue';

import { bkMessage } from 'monitor-api/utils';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { useDataSampling } from '../../hooks/use-data-sampling';
import { useDataVolumeTrend } from '../../hooks/use-data-volume-trend';
import { useNoDataStrategy } from '../../hooks/use-no-data-strategy';
import AlertInfoCard from './components/alert-info-card/alert-info-card';
import DataSamplingTable from './components/data-sampling-table/data-sampling-table';
import DataVolumeTrend from './components/data-volume-trend/data-volume-trend';
import LogDetailSideslider from './components/log-detail-sideslider/log-detail-sideslider';

import type { IRumAppConfig } from '../../../typings';

import './data-state.scss';

export default defineComponent({
  name: 'DataState',
  props: {
    /** 应用基本信息数据 */
    detail: {
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 无数据告警策略状态与处理 */
    const {
      strategyInfo,
      handleEnabledChange,
      loading: strategyLoading,
    } = useNoDataStrategy({
      applicationId: toRef(props.detail.application_id),
      bizId: toRef(props.detail.bk_biz_id),
      appName: toRef(props.detail.app_name),
    });
    /** 数据量趋势图表数据与加载状态 */
    const { dashboardPanels, loading: dashboardLoading } = useDataVolumeTrend({
      bizId: toRef(props.detail.bk_biz_id),
      appName: toRef(props.detail.app_name),
    });
    /** 数据采样状态与处理 */
    const { samplingList, loading: samplingLoading } = useDataSampling({
      bizId: toRef(props.detail.bk_biz_id),
      appName: toRef(props.detail.app_name),
    });
    /** 日志详情侧弹是否可见 */
    const sidesliderShow = shallowRef(false);
    /** 当前查看的日志数据 */
    const activeLog = shallowRef<null | Record<string, unknown>>(null);

    /**
     * @description 打开侧滑栏查看上报数据详情
     * @param {Record<string, unknown>} log - 原始日志对象
     * @returns {void}
     */
    const handleViewDetail = (log: Record<string, unknown>): void => {
      activeLog.value = log;
      sidesliderShow.value = true;
    };

    /**
     * @description 关闭侧滑栏
     * @returns {void}
     */
    const handleCloseSideslider = (): void => {
      sidesliderShow.value = false;
      activeLog.value = null;
    };

    /**
     * @description 复制原始日志 JSON 文本
     * @param {Record<string, unknown>} log - 原始日志对象
     * @returns {void}
     */
    const handleCopyLog = (log: Record<string, unknown>): void => {
      const text = JSON.stringify(log);
      let hasError = false;
      copyText(text, (msg: string) => {
        hasError = true;
        bkMessage({
          message: msg,
          theme: 'error',
        });
      });
      if (!hasError) {
        bkMessage({
          message: t('复制成功'),
          theme: 'success',
        });
      }
    };

    return {
      activeLog,
      dashboardPanels,
      handleCloseSideslider,
      handleCopyLog,
      handleEnabledChange,
      handleViewDetail,
      dashboardLoading,
      samplingList,
      samplingLoading,
      sidesliderShow,
      strategyInfo,
      strategyLoading,
    };
  },
  render() {
    return (
      <div class='run-config-data-state'>
        <AlertInfoCard
          class='run-config-data-state-card'
          loading={this.strategyLoading}
          strategyInfo={this.strategyInfo}
          onEnabledChange={this.handleEnabledChange}
        />
        <div class='run-config-data-state-chart-container'>
          <div class='run-config-data-state-chart-header'>
            <span class='run-config-data-state-chart-title'>{this.$t('数据量趋势')}</span>
          </div>
          <div class='run-config-data-state-chart-content'>
            <DataVolumeTrend
              class='run-config-data-state-chart'
              dashboardPanels={this.dashboardPanels}
              loading={this.dashboardLoading}
            />
          </div>
        </div>
        <div class='run-config-data-state-sampling-container'>
          <div class='run-config-data-state-sampling-header'>
            <span class='run-config-data-state-sampling-title'>{this.$t('数据采样')}</span>
          </div>
          <div class='run-config-data-state-sampling-content'>
            <DataSamplingTable
              loading={this.samplingLoading}
              samplingList={this.samplingList}
              onCopy={this.handleCopyLog}
              onViewDetail={this.handleViewDetail}
            />
          </div>
        </div>
        <LogDetailSideslider
          isShow={this.sidesliderShow}
          log={this.activeLog}
          onCopy={this.handleCopyLog}
          onUpdate:isShow={this.handleCloseSideslider}
        />
      </div>
    );
  },
});
