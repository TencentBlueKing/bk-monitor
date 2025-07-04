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

import { Prop, Component, Emit, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';

import { DimensionSceneMap, SceneAliasMap } from '../../k8s-dimension';

import type { SceneEnum } from '../../typings/k8s-new';
import type { DrillDownEvent, K8sTableColumnResourceKey, K8sTableGroupByEvent } from '../k8s-table-new/k8s-table-new';

import './k8s-quick-tools.scss';

interface K8sQuickToolsProps {
  scene: SceneEnum;
  /** 激活工具栏时数据所在维度 */
  groupByField: K8sTableColumnResourceKey;
  /** 点击工具栏时的数据值 */
  filterValue: string;
  /** 当前filterBy筛选数据中所在维度的筛选项数据 */
  filters: string[];
  /** 是否启用下钻功能 */
  enableDrillDown: boolean;
  /** 是否开启 添加/移除 筛选项 功能 */
  enableFilter: boolean;
}

interface K8sQuickToolsEmits {
  /** 下钻事件 */
  onDrillDown: (groupByEvent: K8sTableGroupByEvent) => void;
  /** 筛选事件 */
  onFilterChange: (filterValue: string, groupByField: K8sTableColumnResourceKey, isSelect: boolean) => void;
  /** 场景切换事件 */
  onSceneChange: (scene: SceneEnum, groupByEvent: K8sTableGroupByEvent) => void;
}
@Component
export default class K8sQuickTools extends tsc<K8sQuickToolsProps, K8sQuickToolsEmits> {
  /** 当前所在场景 */
  @Prop({ type: String }) scene: SceneEnum;
  /** 激活工具栏时数据所在维度 */
  @Prop({ type: String }) groupByField!: K8sTableColumnResourceKey;
  /** 点击工具栏时的数据值 */
  @Prop({ type: String }) filterValue!: string;
  /** 当前filterBy筛选数据中所在维度的筛选项数据 */
  @Prop({ type: Array, default: () => [] }) filters: string[];
  /** 是否启用下钻功能 */
  @Prop({ type: Boolean, default: true }) enableDrillDown!: boolean;
  /** 是否开启 添加/移除 筛选项 功能 */
  @Prop({ type: Boolean, default: true }) enableFilter: boolean;

  /** 场景下拉菜单 dom 实例 */
  @Ref('sceneRef') sceneRef: any;

  /** popover 实例 */
  popoverInstance = null;

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

  /** 场景下拉菜单列表数据 */
  get sceneMenuList() {
    const sceneList = (DimensionSceneMap[this.groupByField] || []).filter(v => v !== this.scene);
    return sceneList;
  }

  /**
   * @description 维度下钻事件点击后回调
   *
   **/
  @Emit('drillDown')
  handleDrillDown(drillDownEvent: DrillDownEvent) {
    const groupByEvent: K8sTableGroupByEvent = {
      ...drillDownEvent,
      filterById: this.filterValue,
    };
    return groupByEvent;
  }

  /**
   * @description 添加/移除 筛选值
   *
   */
  handleFilterChange() {
    this.$emit('filterChange', this.filterValue, this.groupByField, !this.filterToolConfig.hasFilter);
  }

  /**
   * @description 切换场景
   *
   */
  handleSceneChange(scene: SceneEnum) {
    this.handlePopoverHide();
    this.$emit('sceneChange', scene, {
      id: this.groupByField,
      dimension: this.groupByField,
      filterById: this.filterValue,
    });
  }

  /**
   * @description 场景选择下拉菜单 popover 显示
   *
   */
  async handlePopoverShow(e: MouseEvent) {
    if (this.popoverInstance) {
      return;
    }
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.sceneRef,
      maxWidth: 'none',
      animateFill: false,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor k8s-scene-popover',
      arrow: false,
      distance: 4,
      interactive: true,
      followCursor: false,
      onHidden: () => {
        this.handlePopoverHide();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
  }

  handlePopoverHide() {
    this.popoverInstance?.hide();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /**
   * @description 场景 下拉菜单渲染
   *
   */
  sceneMenuListRender() {
    return (
      <div style='display: none'>
        <ul
          ref='sceneRef'
          class='scene-list-menu'
        >
          {this.sceneMenuList.map(scene => (
            <li
              key={scene}
              class='menu-item'
              onClick={() => this.handleSceneChange(scene)}
            >
              {SceneAliasMap[scene]}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  render() {
    return (
      <div class='k8s-quick-tools'>
        {this.enableFilter ? (
          <div
            class='tool-item filter-tool'
            v-bk-tooltips={{ content: this.$t(this.filterToolConfig.text), interactive: false }}
          >
            <i
              class={this.filterToolConfig.className}
              onClick={this.handleFilterChange}
            />
          </div>
        ) : null}
        {this.enableDrillDown ? (
          <K8sDimensionDrillDown
            class='tool-item drill-down-tool'
            dimension={this.groupByField}
            value={this.groupByField}
            onHandleDrillDown={this.handleDrillDown}
          />
        ) : null}
        {this.sceneMenuList?.length ? (
          <div
            class={`tool-item scene-tool ${this.popoverInstance ? 'active' : ''}`}
            v-bk-tooltips={{ content: this.$t('查看该对象的其他场景'), interactive: false }}
          >
            <i
              class='icon-monitor icon-switch'
              onClick={this.handlePopoverShow}
            />
          </div>
        ) : null}
        {this.sceneMenuListRender()}
      </div>
    );
  }
}
