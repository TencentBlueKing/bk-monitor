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
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc, modifiers as m } from 'vue-tsx-support';

import { Debounce, deepClone, typeTools } from '../../../../../monitor-common/utils/utils';
import StatusTab from '../../../../../monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import { IViewOptions, PanelModel } from '../../../../../monitor-ui/chart-plugins/typings';
import { VariablesService } from '../../../../../monitor-ui/chart-plugins/utils/variable';
import { ITableFilterItem } from '../../typings';
import { filterSelectorPanelSearchList, transformConditionValueParams } from '../../utils';
import CommonStatus from '../common-status/common-status';

import './common-tree.scss';

/** 搜索栏的高度 */
const DEFAULT_SEARCH_INPUT_HEIGHT = 32;
/** big-tree 默认的高度 */
const DEFAULT_TREE_HEIGHT = 500;

interface ICommonListProps {
  // panel实例
  panel: PanelModel;
  condition: any[];
  height?: number;
  // 视图数据参数配置
  viewOptions: IViewOptions;
  checkedNode?: FilterDictType;
}

interface ICommonListEvent {
  // 选中列表行数据触发
  onChange: IViewOptions;
  // 标题修改触发
  onTitleChange: string;
  // get list
  onListChange: Record<string, any>[];
  onSearchChange: any[];
}

export type FilterDictType = {
  [key in string]: any;
};

@Component
export default class CommonList extends tsc<ICommonListProps, ICommonListEvent> {
  /** 当前输入的viewOptions数据 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 搜索条件 */
  @Prop({ default: () => [], type: Array }) condition: any[];
  /** 组件的高度 */
  @Prop({ type: Number }) height: number;
  /** 默认选中的节点 */
  @Prop({ default: () => ({}), type: Object }) checkedNode: FilterDictType;

  @Ref() bigTreeRef: any;

  @InjectReactive('width') readonly width!: number;
  keyword = '';
  loading = false;
  activeId = '';
  /** 搜索关键字 */
  searchKeyword = '';
  /** 搜索条件可选项 */
  conditionList = [];
  /** 搜索条件 - 后端搜索 */
  searchCondition = [];
  treeData = [];
  currentStatus: ITableFilterItem['id'] = 'all';
  statusList: ITableFilterItem[] = [
    {
      id: 'success',
      status: 'success',
      name: 0,
      tips: window.i18n.tc('无异常')
    },
    {
      id: 'failed',
      status: 'failed',
      name: 0,
      tips: window.i18n.tc('异常')
    },
    {
      id: 'disabled',
      status: 'disabled',
      name: 0,
      tips: window.i18n.tc('无数据')
    }
  ];

  /** 过滤已选得搜索条件 */
  get currentConditionList() {
    return filterSelectorPanelSearchList(this.conditionList, this.searchCondition);
  }
  get apiData() {
    return this.panel?.targets?.[0];
  }
  // scoped 变量
  get scopedVars() {
    return {
      ...(this.viewOptions || {}),
      ...(this.viewOptions?.filters || {}),
      ...(this.viewOptions?.current_target || [])
    };
  }
  /** 树形组件的高度 */
  get treeHeight() {
    const MARGIN_BOTTOM = 8;
    if (this.height) return this.height - DEFAULT_SEARCH_INPUT_HEIGHT - MARGIN_BOTTOM;
    return DEFAULT_TREE_HEIGHT;
  }
  /** 初始化展开的节点 */
  get defaultExpandedId() {
    const fn = (list: string | any[], targetName: string): any => {
      if (list?.length) {
        for (const item of list) {
          const sourceId = item.id;
          if (sourceId === targetName) {
            return item;
          }
          if (item.children?.length) {
            const res = fn(item.children, targetName);
            if (res) return res;
          }
        }
      }
    };
    const res = fn(this.treeData, this.activeId);
    const data = res ? [res.id] : [];
    if (this.bigTreeRef) {
      this.bigTreeRef.setSelected(data[0]);
      this.bigTreeRef.setExpanded(data);
    }
    return data;
  }

  @Watch('width')
  handleWidthChange() {
    (this.$refs.bigTreeRef as any)?.resize();
  }
  @Watch('condition', { immediate: true })
  conditionChange() {
    this.searchCondition = deepClone(this.condition);
  }
  @Watch('checkedNode', { immediate: true })
  checkedNodeChange(val: FilterDictType) {
    this.activeId = `${val.endpoint_name}|${val.service_name}`;
  }

  mounted() {
    this.getPanelData();
  }

  // 获取列表数据
  async getPanelData() {
    if (!this.apiData) return;
    this.loading = true;
    const variablesService = new VariablesService(this.scopedVars);
    this.$api[this.apiData.apiModule]
      [this.apiData.apiFunc]({
        ...variablesService.transformVariables(this.apiData.data),
        condition_list: transformConditionValueParams(this.searchCondition)
      })
      .then(data => {
        const treeData = typeTools.isObject(data) ? data.data : data;
        this.conditionList = data.condition_list || [];
        this.treeData = treeData;
        this.traverseTree(treeData);
        this.$emit('listChange', this.treeData.slice());
      })
      .finally(() => (this.loading = false));
  }
  @Emit('searchChange')
  handleSearch() {
    this.getPanelData();
    return deepClone(this.searchCondition);
  }
  @Debounce(300)
  handleLocalSearch() {
    this.bigTreeRef?.filter({
      keyword: this.searchKeyword
    });
  }
  handleRefresh() {
    this.searchKeyword = '';
    this.getPanelData();
  }
  @Emit('titleChange')
  handleTitleChange(title: string) {
    return title;
  }
  /* 统计接口状态信息 */
  traverseTree(treeData: any) {
    const recursiveTraverse = node => {
      if (node.children) {
        node.children.forEach(item => {
          recursiveTraverse(item);
        });
      } else {
        if (node.status?.type === 'success') (this.statusList[0].name as number) += 1;
        if (node.status?.type === 'failed') (this.statusList[1].name as number) += 1;
        if (node.status?.type === 'disabled') (this.statusList[2].name as number) += 1;
      }
    };
    treeData.forEach(node => {
      recursiveTraverse(node);
    });
  }
  /** 生成选中的viewOptions */
  handleGetSelectedViewOptions(node) {
    const viewOptions = { ...this.viewOptions };
    viewOptions.filters = {
      endpoint_name: node.endpoint,
      service_name: node.service_name,
      app_name: node.app_name
    };

    return viewOptions;
  }
  /** 对外输出一个viewOptions格式数据 */
  @Emit('change')
  handleViewOptionsChange(viewOptions: IViewOptions) {
    return viewOptions;
  }
  @Emit('checkedChange')
  handleClickItem(data) {
    this.activeId = data.id;
    const viewOptions = this.handleGetSelectedViewOptions(data);
    this.handleViewOptionsChange(viewOptions);
    return viewOptions;
  }
  handleClickItemProxy(data) {
    if (!data.endpoint) return;
    this.handleClickItem(data);
  }
  /** big-tree搜索回调方法 */
  filterMethod(filterObj: { status: string; keyword: string }, node: { data: any }): boolean {
    const { data } = node;
    const searchTarget = [data.name];
    return (
      searchTarget.some(target => `${target ?? ''}`.indexOf(filterObj.keyword) > -1) &&
      (filterObj.status === 'all' ? true : data.status?.type === filterObj.status)
    );
  }
  handleStatusChange(v: string) {
    this.currentStatus = v;
    this.bigTreeRef?.filter({
      status: this.currentStatus,
      keyword: this.searchKeyword
    });
  }

  render() {
    const scopedSlots = {
      default: ({ data }) => (
        <div
          class={['bk-tree-node', { active: `${data.id}` === this.activeId }]}
          onClick={m.stop(() => this.handleClickItemProxy(data))}
        >
          <span
            class='node-content'
            style='padding-right: 5px;'
          >
            {!!data.status?.type && (
              <CommonStatus
                class='status-icon'
                type={data.status.type}
              ></CommonStatus>
            )}
            <span class='item-name'>{data.name}</span>
          </span>
        </div>
      )
    };
    return (
      <div
        class='common-tree-list'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='list-header'>
          {this.conditionList.length ? (
            <bk-search-select
              placeholder={this.$t('搜索')}
              vModel={this.searchCondition}
              show-condition={false}
              data={this.currentConditionList}
              show-popover-tag-change={false}
              onChange={this.handleSearch}
            />
          ) : (
            <bk-input
              v-model={this.searchKeyword}
              right-icon='bk-icon icon-search'
              placeholder={this.$t('搜索')}
              onInput={this.handleLocalSearch}
            ></bk-input>
          )}
          <bk-button
            class='reflesh-btn'
            onClick={this.handleRefresh}
          >
            <i class='icon-monitor icon-shuaxin'></i>
          </bk-button>
        </div>
        <StatusTab
          class='status-tab'
          disabledClickZero={false}
          v-model={this.currentStatus}
          statusList={this.statusList}
          onChange={this.handleStatusChange}
        />
        <div class='list-wrapper'>
          <bk-big-tree
            class={['big-tree', { 'clear-selected': !this.activeId }]}
            ref='bigTreeRef'
            expand-on-click={false}
            height={this.treeHeight}
            selectable={true}
            filter-method={this.filterMethod}
            default-expanded-nodes={this.defaultExpandedId}
            data={this.treeData}
            scopedSlots={scopedSlots}
          >
            <div
              slot='empty'
              class='search-empty-wrap'
            >
              <bk-exception
                type='search-empty'
                scene='part'
              />
            </div>
          </bk-big-tree>
        </div>
      </div>
    );
  }
}
