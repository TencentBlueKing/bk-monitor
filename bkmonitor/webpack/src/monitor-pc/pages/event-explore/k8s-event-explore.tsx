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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { EMode, type IWhereItem } from '../../components/retrieval-filter/utils';
import { APIType } from './api-utils';
import EventExplore from './event-explore';

import './k8s-event-explore.scss';

interface K8sEventExploreProps {
  dataId: string;
  where?: IWhereItem[];
  queryString?: string;
  filterMode?: EMode;
}

interface K8sEventExploreEvents {
  onFilterModeChange(mode: EMode): void;
  onQueryStringChange(queryString: string): void;
  onSetRouteParams(params: Record<string, any>): void;
  onWhereChange(where: IWhereItem[]): void;
}

@Component
export default class K8sEventExplore extends tsc<
  K8sEventExploreProps,
  K8sEventExploreEvents,
  {
    filterPrepend?: string;
  }
> {
  @Prop({ type: String, required: true }) dataId!: string;
  @Prop({ type: Array, default: () => [] }) where: IWhereItem[];
  @Prop({ type: String, default: '' }) queryString: string;
  @Prop({ type: String, default: EMode.ui }) filterMode: EMode;

  dataTypeLabel = 'event';
  dataSourceLabel = 'custom';
  /** 数据ID列表 */
  dataIdList = [];

  @Emit('filterModeChange')
  handleFilterModelChange(mode: EMode) {
    return mode;
  }

  @Emit('queryStringChange')
  handleQueryStringChange(queryString: string) {
    return queryString;
  }

  @Emit('setRouteParams')
  setRouteParams(params: Record<string, any>) {
    return params;
  }

  @Emit('whereChange')
  handleWhereChange(where: IWhereItem[]) {
    return where;
  }

  render() {
    return (
      <EventExplore
        class={'k8s-event-explore'}
        defaultLayoutConfig={{
          defaultWidth: 280,
          lineTheme: 'line',
          closeTheme: 'button',
        }}
        dataId={this.dataId}
        dataSourceLabel={this.dataSourceLabel}
        dataTypeLabel={this.dataTypeLabel}
        filterMode={this.filterMode}
        isK8sEvent={true}
        queryString={this.queryString}
        scopedSlots={this.$scopedSlots}
        source={APIType.MONITOR}
        where={this.where}
        onFilterModeChange={this.handleFilterModelChange}
        onQueryStringChange={this.handleQueryStringChange}
        onSetRouteParams={this.setRouteParams}
        onWhereChange={this.handleWhereChange}
      />
    );
  }
}
