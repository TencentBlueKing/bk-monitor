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
/** biome-ignore-all lint/correctness/noUnusedVariables: <explanation> */

import { Component, Inject, Prop, ProvideReactive, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';

import { EMode } from '../../../../components/retrieval-filter/utils';
import { DimensionSceneMap, K8sGroupDimension, SceneAliasMap } from '../../k8s-dimension';
import { K8sTableColumnKeysEnum, K8SToEventWhereKeyMap, SceneEnum } from '../../typings/k8s-new';

import type { DrillDownEvent, K8sTableColumnResourceKey, K8sTableGroupByEvent } from '../k8s-table-new/k8s-table-new';

import './k8s-quick-tools.scss';

interface K8sQuickToolsProps {
  /** 公共参数 */
  filterCommonParams: { [key: string]: any; filter_dict: Record<string, string[]>; scenario: SceneEnum };
  /** 激活工具栏时数据所在维度 */
  groupByField: K8sTableColumnResourceKey;
  /** 需要 添加/移除 到筛选项中的源数据值（非最终添加/移除的值，因为图表使用时可能会存在一些拼接逻辑还需做拆分获取最终值） */
  value: string;
}

@Component
export default class K8sQuickTools extends tsc<K8sQuickToolsProps> {
  /** 激活工具栏时数据所在维度 */
  @Prop({ type: String }) groupByField!: K8sTableColumnResourceKey;
  /** 需要 添加/移除 到筛选项中的源数据值（非最终添加/移除的值，因为图表使用时可能会存在一些拼接逻辑还需做拆分获取最终值） */
  @Prop({ type: String }) value!: string;
  /** 当前筛选过滤中已存在的过滤值 filterBy数据 */
  @Prop({ type: Object }) filterCommonParams: K8sQuickToolsProps['filterCommonParams'];

  /** 场景下拉菜单 dom 实例 */
  @Ref('sceneRef') sceneRef: any;
  // 视图变量--图表中的时间对比值
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  @Inject({ from: 'onFilterChange', default: () => null }) readonly onFilterChange: (
    id: string,
    groupId: K8sTableColumnResourceKey,
    isSelect: boolean
  ) => void;
  @Inject({ from: 'onGroupChange', default: () => null }) readonly onDrillDown: (
    item: K8sTableGroupByEvent,
    showCancelDrill?: boolean
  ) => void;

  /** popover 实例 */
  popoverInstance = null;

  get filters() {
    return this.filterCommonParams?.filter_dict?.[this.groupByField] || [];
  }

  /** 需要 添加/移除 到筛选项中的最终数据值 */
  get filterValue() {
    const splits = this.value.split(':');
    if (splits?.length !== 1) {
      if (this.groupByField === K8sTableColumnKeysEnum.CONTAINER) {
        const [container] = splits;
        return container;
      }
      if ([K8sTableColumnKeysEnum.INGRESS, K8sTableColumnKeysEnum.SERVICE].includes(this.groupByField)) {
        const isIngress = this.groupByField === K8sTableColumnKeysEnum.INGRESS;
        const list = splits;
        const id = isIngress ? list[0] : list[1];
        return id;
      }
    }
    if (this.timeOffset.length) {
      return this.value.split('-')?.slice(1).join('-');
    }
    return this.value;
  }

  /** 添加/移除 筛选项工具icon配置 */
  get filterToolConfig() {
    // 当前数据值已在筛选项中
    const filters = this.filters;
    const hasFilter = filters?.includes?.(this.filterValue);
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
    const sceneList = (DimensionSceneMap[this.groupByField] || []).filter(v => v !== this.filterCommonParams.scenario);
    return sceneList;
  }

  /**
   * @description 维度下钻事件点击后回调
   *
   **/
  handleDrillDown(drillDownEvent: DrillDownEvent) {
    const groupByEvent: K8sTableGroupByEvent = {
      ...drillDownEvent,
      filterById: this.filterValue,
    };
    this.onDrillDown(groupByEvent, true);
  }

  /**
   * @description 添加/移除 筛选值
   *
   */
  handleFilterChange() {
    this.onFilterChange(this.filterValue, this.groupByField, !this.filterToolConfig.hasFilter);
  }

  /**
   * @description 切换场景(新开页实现)
   * @param {SceneEnum} targetScene 想要切换到的目标场景
   *
   */
  handleNewK8sPage(targetScene: SceneEnum) {
    const { scene: currentScene, groupBy, filterBy, ...rest } = this.$route.query;
    const targetPageGroupInstance = K8sGroupDimension.createInstance(targetScene);
    targetPageGroupInstance.addGroupFilter(this.groupByField);
    // 事件场景 跳转
    if (targetScene === SceneEnum.Event) {
      const eventQuery = {
        ...rest,
        scene: targetScene,
        /** 因存在内部跳转功能，所以使用事件检索URL格式 */
        targets: JSON.stringify([
          {
            data: {
              query_configs: [
                {
                  where:
                    this.groupByField === K8sTableColumnKeysEnum.WORKLOAD
                      ? [
                          {
                            key: K8SToEventWhereKeyMap.workload_kind,
                            method: 'eq',
                            value: [this.filterValue.split(':')[0]],
                          },
                          {
                            key: K8SToEventWhereKeyMap.workload,
                            method: 'eq',
                            value: [this.filterValue.split(':')[1]],
                          },
                        ]
                      : [
                          {
                            key: K8SToEventWhereKeyMap[this.groupByField],
                            method: 'eq',
                            value: [this.filterValue],
                            condition: 'and',
                          },
                        ],
                  query_string: '',
                },
              ],
            },
          },
        ]),
        filterMode: EMode.ui,
        prop: '',
        order: '',
      };
      this.gotoK8sPageByQuery(eventQuery);
      return;
    }
    const query = {
      ...rest,
      filterBy: JSON.stringify({ [this.groupByField]: [this.filterValue] }),
      groupBy: JSON.stringify(targetPageGroupInstance.groupFilters),
      scene: targetScene,
    };
    this.gotoK8sPageByQuery(query);
  }

  gotoK8sPageByQuery(query: Record<string, any>) {
    const targetRoute = this.$router.resolve({
      query,
    });
    this.handlePopoverHide();
    window.open(`${location.origin}${location.pathname}${location.search}${targetRoute.href}`, '_blank');
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
              onClick={() => this.handleNewK8sPage(scene)}
            >
              {SceneAliasMap[scene]}
            </li>
          ))}
          <li
            key='event'
            class='menu-item'
            onClick={() => this.handleNewK8sPage(SceneEnum.Event)}
          >
            {SceneAliasMap[SceneEnum.Event]}
          </li>
        </ul>
      </div>
    );
  }

  render() {
    return (
      <div class='k8s-quick-tools'>
        <div
          class='tool-item filter-tool'
          v-bk-tooltips={{ content: this.$t(this.filterToolConfig.text), interactive: false }}
        >
          <i
            class={this.filterToolConfig.className}
            onClick={this.handleFilterChange}
          />
        </div>
        <K8sDimensionDrillDown
          class='tool-item drill-down-tool'
          dimension={this.groupByField}
          value={this.groupByField}
          onHandleDrillDown={this.handleDrillDown}
        />
        {this.sceneMenuList?.length || K8SToEventWhereKeyMap[this.groupByField] ? (
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
