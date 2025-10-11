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
import { Component, InjectReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '../../../../../store/modules/custom-escalation-view';
import RenderMetricsGroup from './components/render-metrics-group';

import type { IRouteParams } from '@/pages/custom-escalation/new-metric-view/type';

import './index.scss';

interface IEmit {
  onReset: () => void;
}

@Component
export default class HeaderFilter extends tsc<object, IEmit> {
  @InjectReactive('routeParams') routeParams: IRouteParams;

  @Ref('metricGroupRef') metricGroupRef: RenderMetricsGroup;

  searchKey = '';
  isExpandAll = false;

  get metricGroupList() {
    return customEscalationViewStore.metricGroupList;
  }

  handleClearChecked() {
    this.metricGroupRef.resetMetricChecked();
    this.$emit('reset');
  }

  handleFlodAllGroup() {
    this.isExpandAll = false;
    this.metricGroupRef.expandAll(false);
  }
  handleExpandAllGroup() {
    this.isExpandAll = true;
    this.metricGroupRef.expandAll(true);
  }

  created() {
    // 默认会选中一个指标，如果只有一个分组此时是全部展开状态
    if (this.metricGroupList.length === 1) {
      this.isExpandAll = true;
    }
  }

  handleGoToSettings() {
    if (window.__POWERED_BY_BK_WEWEB__) {
      window.open(
        location.href.replace(
          location.hash,
          `#/custom-escalation-detail/timeseries/${this.routeParams.idParams.time_series_group_id}`
        ),
        '_blank'
      );
      return;
    }
  }
  handleGoToDataRetrieval() {
    if (window.__POWERED_BY_BK_WEWEB__) {
      window.open(location.href.replace(location.hash, '#/data-retrieval'), '_blank');
      return;
    }
    const route = this.$router.resolve({
      name: 'data-retrieval',
    });
    window.open(route.href, '_blank');
  }

  render() {
    return (
      <div class='new-metric-view-metrics-select'>
        <div class='header-wrapper'>
          <bk-input
            v-model={this.searchKey}
            placeholder={this.$t('搜索 指标组、指标')}
            right-icon='bk-icon icon-search'
          />
          <div class='action-box'>
            <span
              style='color: #3a84ff;'
              onClick={this.handleGoToSettings}
            >
              <i class='icon-monitor icon-mc-goto' />
              {this.$t('指标管理')}
            </span>
            <span
              style='color: #3a84ff; margin-left: 16px;'
              onClick={this.handleGoToDataRetrieval}
            >
              <i class='icon-monitor icon-mc-goto' />
              {this.$t('指标计算')}
            </span>
            {this.isExpandAll ? (
              <div
                style='display: inline-block; margin-left: auto; cursor: pointer'
                v-bk-tooltips={this.$t('全部收起')}
                onClick={this.handleFlodAllGroup}
              >
                <i class='icon-monitor icon-zhankai2' />
              </div>
            ) : (
              <div
                style='display: inline-block; margin-left: auto; cursor: pointer'
                v-bk-tooltips={this.$t('全部展开')}
                onClick={this.handleExpandAllGroup}
              >
                <i class='icon-monitor icon-shouqi3' />
              </div>
            )}
          </div>
        </div>
        <RenderMetricsGroup
          ref='metricGroupRef'
          searchKey={this.searchKey}
        />
      </div>
    );
  }
}
