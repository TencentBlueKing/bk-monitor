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

import { Prop, Component, Emit, Watch, InjectReactive, Inject, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';

import type { DrillDownEvent, K8sTableColumnResourceKey } from '../k8s-table-new/k8s-table-new';

export default class K8sQuickTools extends tsc<object> {
  /** 激活工具栏时数据所在维度 */
  @Prop({ type: String }) groupByField!: K8sTableColumnResourceKey;
  /** 点击工具栏时的数据值 */
  @Prop({ type: String }) filterValue!: string;
  /** 当前filterBy筛选数据中所在维度的筛选项数据 */
  @Prop({ type: Array, default: () => [] }) filters: string[];
  /** 是否启用下钻功能 */
  @Prop({ type: Boolean }) enableDrillDown!: boolean;

  /** 添加/移除 筛选项工具icon配置 */
  get filterToolConfig() {
    // 当前数据值已在筛选项中
    const hasFilter = this.filters?.includes?.(this.filterValue);
    const elAttr = hasFilter
      ? { className: ['selected'], text: '移除该筛选项' }
      : { className: ['icon-monitor icon-a-sousuo'], text: '添加为筛选项' };
    return {
      hasFilter: hasFilter,
      ...elAttr,
    };
  }

  /**
   * @description 维度下钻事件点击后回调
   *
   **/
  @Emit('drillDown')
  handleDrillDown(drillDownEvent: DrillDownEvent) {
    return drillDownEvent;
  }

  /**
   * @description 添加/移除 筛选值
   *
   */
  handleFilterChange() {
    this.$emit('filterChange', this.filterValue, this.groupByField, !this.filterToolConfig.hasFilter);
  }

  render() {
    return (
      <div class='k8s-quick-tools'>
        {this.enableDrillDown ? (
          <K8sDimensionDrillDown
            class='tool-item drill-down-tool'
            dimension={this.groupByField}
            value={this.groupByField}
            onHandleDrillDown={this.handleDrillDown}
          />
        ) : null}
        <div class='tool-item filter-tool'>
          <i
            class={this.filterToolConfig.className}
            v-bk-tooltips={{ content: this.$t(this.filterToolConfig.text), interactive: false }}
            onClick={this.handleFilterChange}
          />
        </div>
        <div class='tool-item scene-tool'>
          <i
            class='icon-monitor icon-switch'
            v-bk-tooltips={{ content: this.$t('查看该对象的其他场景'), interactive: false }}
            onClick={() => this.onFilterChange(resourceValue, column.id, !hasFilter)}
          />
        </div>
      </div>
    );
  }
}
