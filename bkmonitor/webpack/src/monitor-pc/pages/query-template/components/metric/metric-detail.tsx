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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { xssFilter } from 'monitor-common/utils';

import { type MetricDetailV2 } from '../../typings';
import { getMetricTip } from '../utils/metric-tip';

import './metric-detail.scss';

interface IProps {
  /* 指标详情类实例 */
  metricDetail?: MetricDetailV2;
}

@Component
export default class MetricDetail extends tsc<IProps> {
  /* 指标详情类实例 */
  @Prop({ type: Object }) metricDetail: MetricDetailV2;

  /* 指标别名 */
  get metricAlias() {
    return this.metricDetail?.metric_field_name || this.metricDetail?.metric_id || '--';
  }

  /* hover展示的指标详细信息内容dom */
  get metricTips() {
    return getMetricTip(this.metricDetail);
  }

  render() {
    return (
      <div class='template-metric-detail-component'>
        <span class='metric-label'>{this.$slots?.label || this.$t('监控数据')}</span>
        <span class='metric-colon'>:</span>
        <span
          class='metric-name'
          v-bk-tooltips={{
            content: xssFilter(this.metricTips),
            placement: 'right',
            disabled: !this.metricTips,
            delay: [300, 0],
          }}
        >
          {this.metricAlias}
        </span>
      </div>
    );
  }
}
