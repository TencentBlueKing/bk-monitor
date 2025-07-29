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

import GroupItem from './group-item';

import type { GroupListItem } from '../../typings/k8s-new';

import './k8s-metric-list.scss';

interface K8sMetricListEvent {
  onHandleItemClick: (id: string) => void;
  onMetricHiddenChange: (val: string[]) => void;
}

interface K8sMetricListProps {
  activeMetric?: string;
  disabledMetricList?: { id: string; tooltips: string }[];
  hideMetrics?: string[];
  loading?: boolean;
  metricList: GroupListItem[];
}

@Component
export default class K8sMetricList extends tsc<K8sMetricListProps, K8sMetricListEvent> {
  @Prop({ type: Array, default: () => [] }) hideMetrics: string[];
  @Prop({ type: Array, default: () => [] }) metricList: GroupListItem[];
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: String, default: '' }) activeMetric: string;
  @Prop({ type: Array, default: () => [] }) disabledMetricList: { id: string; tooltips: string }[];

  @Emit('metricHiddenChange')
  handleMetricHiddenChange(ids: string[]) {
    return ids;
  }

  @Emit('handleItemClick')
  handleItemClick(id: string) {
    return id;
  }

  renderGroupSkeleton() {
    return (
      <div class='skeleton-element-group'>
        <div class='skeleton-element group-title' />
        <div class='skeleton-element group-content' />
        <div class='skeleton-element group-content' />
        <div class='skeleton-element group-content' />
      </div>
    );
  }

  render() {
    return (
      <div class='k8s-metric-list'>
        <div class='panel-title'>{this.$t('指标')}</div>
        {this.loading
          ? [this.renderGroupSkeleton(), this.renderGroupSkeleton()]
          : this.metricList.map(group => (
              <GroupItem
                key={group.id}
                activeMetric={this.activeMetric}
                defaultExpand={true}
                disabledList={this.disabledMetricList}
                hiddenList={this.hideMetrics}
                list={group}
                tools={['view']}
                onHandleHiddenChange={this.handleMetricHiddenChange}
                onHandleItemClick={this.handleItemClick}
              />
            ))}
      </div>
    );
  }
}
