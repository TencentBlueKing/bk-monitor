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

import { type getCustomTsMetricGroups } from 'monitor-api/modules/scene_view_new';

import RenderMetricsGroup from './components/render-metrics-group';

import './index.scss';

type TCustomTsMetricGroups = ServiceReturnType<typeof getCustomTsMetricGroups>;

interface IEmit {
  onChange: (value: {
    metricsList: TCustomTsMetricGroups['metric_groups'][number]['metrics'];
    commonDimensionList: TCustomTsMetricGroups['common_dimensions'];
  }) => void;
}

@Component
export default class HeaderFilter extends tsc<object, IEmit> {
  @Ref('metricGroup') metricGroup: RenderMetricsGroup;

  searchKey = '';

  handleChange(payload: {
    metricsList: TCustomTsMetricGroups['metric_groups'][number]['metrics'];
    commonDimensionList: TCustomTsMetricGroups['common_dimensions'];
  }) {
    this.$emit('change', payload);
  }

  handleClearChecked() {
    this.metricGroup.resetMetricChecked();
  }

  render() {
    return (
      <div class='new-metric-view-metrics-select'>
        <div class='header-wrapper'>
          <bk-input
            v-model={this.searchKey}
            placeholder={this.$t('搜索 指标组、指标')}
          />
          <div class='action-box'>
            <bk-button
              style='padding: 0'
              size='small'
              theme='primary'
              text
            >
              <i class='icon-monitor icon-mc-goto' />
              {this.$t('指标计算')}
            </bk-button>
            <bk-button
              style='margin-left: 16px; padding: 0'
              size='small'
              theme='primary'
              text
              onClick={this.handleClearChecked}
            >
              <i class='icon-monitor icon-a-3yuan-bohui' />
              {this.$t('取消选中')}
            </bk-button>
            <div style='display: inline-block; margin-left: auto; cursor: pointer'>
              <i class='icon-monitor icon-zhankai' />
            </div>
          </div>
        </div>
        <RenderMetricsGroup
          ref='metricGroup'
          searchKey={this.searchKey}
          onChange={this.handleChange}
        />
      </div>
    );
  }
}
