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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import RenderMetricsGroup from './components/render-metrics-group';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

import './index.scss';

interface IEmit {
  onReset: () => void;
}

@Component
export default class HeaderFilter extends tsc<object, IEmit> {
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
            <router-link
              style='color: #3a84ff;'
              to={{
                name: 'custom-detail-timeseries',
                id: this.$route.params.id,
              }}
              target='_blank'
            >
              <i class='icon-monitor icon-mc-goto' />
              {this.$t('指标管理')}
            </router-link>
            <router-link
              style='color: #3a84ff; margin-left: 16px;'
              to={{
                name: 'data-retrieval',
              }}
              target='_blank'
            >
              <i class='icon-monitor icon-mc-goto' />
              {this.$t('指标计算')}
            </router-link>
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
