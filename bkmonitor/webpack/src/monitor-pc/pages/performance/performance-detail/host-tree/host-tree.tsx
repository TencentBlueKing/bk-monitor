/* eslint-disable no-param-reassign */
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
import { Component, Emit, Inject, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc, modifiers as m } from 'vue-tsx-support';

import { isFullIpv6, padIPv6 } from '../../../../../monitor-common/utils/ip-utils';
import { Debounce, deepClone, typeTools } from '../../../../../monitor-common/utils/utils';
import StatusTab from '../../../../../monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import { IOption, IViewOptions, PanelModel } from '../../../../../monitor-ui/chart-plugins/typings';
import { VariablesService } from '../../../../../monitor-ui/chart-plugins/utils/variable';
import EmptyStatus from '../../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../../components/empty-status/types';
import { IQueryData, IQueryDataSearch } from '../../../monitor-k8s/typings';
import {
  filterSelectorPanelSearchList,
  transformConditionValueParams,
  transformQueryDataSearch,
  updateBkSearchSelectName
} from '../../../monitor-k8s/utils';
import { DEFAULT_TAB_LIST } from '../host-list/host-list';

import './host-tree.scss';

/** 搜索栏的高度 */
const DEFAULT_SEARCH_INPUT_HEIGHT = 32;
/** big-tree 默认的高度 */
const DEFAULT_TREE_HEIGHT = 500;

/** 成功 | 无数据 | 失败 | 警告 | 不展示状态 */
export type StatusClassNameType = 'success' | 'nodata' | 'failed' | 'warning' | 'none';
export interface TreeNodeItem {
  id: number | string;
  name: string;
  alias_name?: string;
  ip?: string;
  bk_host_name?: string;
  bk_cloud_id?: string;
  bk_inst_id?: string;
  bk_obj_id?: string;
  bk_host_id?: string;
  status?: number | string;
  bk_inst_name?: string;
  display_name?: string;
  children: TreeNodeItem[];
  bk_obj_name?: string;
  service_instance_id?: number; // 服务实例ID
  os_type?: string;
}
export interface ICurNode {
  id: string | number; // ip + cloudId 或者 bkInstId + bkObjId
  ip?: string;
  cloudId?: string | number;
  bkInstId?: number | string;
  bkObjId?: string;
  type: NodeType;
  processId?: string | number;
  osType?: number;
}

type NodeType = 'host' | 'node' | 'overview' | 'service'; // host类型时：IP、bkCloudId不为空；node类型时：bkInstId、bkObjId不为空 overview：数据总览 service: 服务实例

export interface IProps {
  panel: PanelModel;
  isTargetCompare?: boolean;
  compareTargets?: string[];
  checkedNode?: FilterDictType;
  viewOptions: IViewOptions;
  height?: number;
  width: number;
  tabActive: string;
  statusMapping?: IStatusMapping[];
}

export interface IEvents {
  onCompareChange: string[];
  onCheckedChange: IViewOptions;
  onListChange: IHostNode[];
  onTitleChange: (a: string, b: TreeNodeItem) => void;
  onChange: IViewOptions;
  onOverviewChange?: void;
  onSearchChange: any[];
}

export type FilterDictType = {
  [key in string]: any;
};

export interface IHostNode {
  bk_biz_id: number;
  bk_cloud_id: number;
  id: string;
  ip: string;
  name: string;
  os_type: string;
  plat_id: number;
}

interface IStatusMapping {
  color?: string;
  id?: string;
  name?: string;
}

/**
 * 属性主机数据列表
 */
@Component
export default class HostTree extends tsc<IProps, IEvents> {
  /** 当前输入的viewOptions数据 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 是否存在目标对比 */
  @Prop({ default: false, type: Boolean }) isTargetCompare: boolean;
  /** 默认选中的节点 */
  @Prop({ default: () => ({}), type: Object }) checkedNode: FilterDictType;
  /** 组件的高度 */
  @Prop({ type: Number }) height: number;
  /** 容器宽度变化，组件自身宽度自适应 */
  @Prop({ type: Number }) width: number;
  /** 选中的页签 */
  @Prop({ default: '', type: String }) tabActive: string;
  /* 颜色及状态映射 */
  @Prop({ default: () => [], type: Array }) statusMapping: IStatusMapping[];
  /* 是否显示数据总览 */
  // @Prop({ default: false, type: Boolean }) showOverview: boolean;
  @Ref() bigTreeRef: any;
  /** 侧栏搜索条件 */
  @InjectReactive('queryData') readonly queryData!: IQueryData;
  /** 侧栏搜索条件更新url方法 */
  @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;

  /** 采集状态status字段映射 */
  hostStatusMap = {
    SUCCESS: 'success',
    FAILED: 'failed',
    NODATA: 'nodata'
  };
  /** 主机状态 */
  statusMap = {
    // '-1': {
    //   name: window.i18n.t('未知'),
    //   status: '3'
    // },
    // 0: {
    //   name: window.i18n.t('正常'),
    //   status: '1'
    // },
    // 1: {
    //   name: window.i18n.t('离线'),
    //   status: '1'
    // },
    // 2: {
    //   name: window.i18n.t('无Agent'),
    //   status: '2'
    // },
    // 3: {
    //   name: window.i18n.t('无数据上报'),
    //   status: '3'
    // }
  };

  /** 数据加载状态 */
  loading = false;

  /** 当前选中的节点 */
  curNode: ICurNode = {
    id: null,
    type: 'overview'
  };

  /** 主机属性数据 */
  hostTreeData: TreeNodeItem[] = [];

  /** 搜索关键字 */
  searchKeyword = '';

  /* 统计栏数据 */
  statusData: any = {};
  statusType = 'all';

  /* 是否选中了数据总览 */
  isOverviewActive = false;

  searchCondition = [];
  conditionList = [];

  localCompareTargets: Array<Record<string, any>> = [];
  isNoData = false;
  emptyStatusType: EmptyStatusType = 'empty';

  /** 状态筛选数据 */
  get statusList() {
    return DEFAULT_TAB_LIST.map(item => ({
      id: item.type,
      name: item.name || (this.statusData[item.type]?.count ?? 0),
      tips: item.tips,
      status: item.status
    }));
  }

  /** 过滤已选得搜索条件 */
  get currentConditionList() {
    return filterSelectorPanelSearchList(this.conditionList, this.searchCondition);
  }

  /** 是否显示数据总览 */
  get showOverview() {
    return !!this.panel.options?.topo_tree?.show_overview;
  }

  /** 是否展示状态统计 */
  get isStatusFilter() {
    return !!this.panel.options?.topo_tree?.show_status_bar;
  }

  get apiData() {
    return this.panel?.targets?.[0];
  }

  get enableCmdbLevel() {
    return this.$store.getters.enable_cmdb_level;
  }

  /** host tree 是否可以选中节点 */
  get canCheckedNode() {
    return this.panel.options?.topo_tree?.can_check_node ?? false;
  }

  /** 目标对比选中的主机id */
  get compareTargets() {
    // eslint-disable-next-line max-len
    return (
      this.viewOptions?.compares?.targets?.map(item => this.panel.targets?.[0]?.handleCreateItemId(item, true)) || []
    );
    // return this.viewOptions?.compares?.targets?.map(item => item.bk_host_id) || [];
  }

  localViewOptions: IViewOptions = {};

  /** 树形组件的高度 */
  get hostTreeHeight() {
    const MARGIN_BOTTOM = 8;
    const overviewHeight = this.showOverview ? 32 + MARGIN_BOTTOM : 0;
    const statusFilterHeight = this.isStatusFilter ? 32 + MARGIN_BOTTOM : 0;
    const targetCompareTips = this.isTargetCompare ? 34 + MARGIN_BOTTOM : 0;
    if (this.height)
      return (
        this.height -
        DEFAULT_SEARCH_INPUT_HEIGHT -
        MARGIN_BOTTOM -
        overviewHeight -
        statusFilterHeight -
        targetCompareTips
      );
    return DEFAULT_TREE_HEIGHT;
  }

  @Watch('tabActive')
  tabActiveChange() {
    const { bk_inst_id, bk_target_ip, bk_target_service_instance_id, bk_host_id } = this.viewOptions.filters;
    if (typeof bk_host_id !== 'undefined' || typeof bk_target_ip !== 'undefined') {
      if (!bk_target_ip && this.bigTreeRef) {
        const node = this.bigTreeRef.getNodeById(this.viewOptions.filters.bk_host_id);
        node?.data && this.$emit('titleChange', node.data.display_name || node.data.ip);
        return;
      }
      this.handleTitleChange(undefined, bk_target_ip || bk_host_id || this.$t('概览'));
    } else {
      this.handleTitleChange(
        undefined,
        `${bk_inst_id ?? ''}` || `${bk_target_service_instance_id ?? ''}` || this.$t('概览').toString()
      );
    }
    if (!!this.hostTreeData.length && (bk_inst_id !== undefined || bk_target_service_instance_id !== undefined)) {
      this.getNodeName();
    }
  }

  @Watch('queryData.selectorSearch', { immediate: true })
  conditionChange(search: IQueryDataSearch) {
    this.searchCondition = updateBkSearchSelectName(this.conditionList, transformQueryDataSearch(search || []));
  }

  @Watch('width')
  @Watch('isTargetCompare')
  @Debounce(300)
  widthChange() {
    this.bigTreeRef?.resize();
  }

  @Watch('checkedNode', { immediate: true })
  checkedNodeChange(val: FilterDictType) {
    if (
      !val?.bk_target_service_instance_id &&
      !('ip' in val || 'bk_target_ip' in val) &&
      !val?.bk_inst_id &&
      this.showOverview
    ) {
      this.curNode.type = 'overview';
      this.curNode.id = null;
      this.isOverviewActive = true;
      this.handleTitleChange(null, this.$tc('概览'));
      return;
    }
    // eslint-disable-next-line no-nested-ternary
    this.curNode.type =
      'bk_target_service_instance_id' in val ? 'service' : 'ip' in val || 'bk_target_ip' in val ? 'host' : 'node';
    // eslint-disable-next-line no-nested-ternary
    this.curNode.id =
      this.curNode?.type === 'service'
        ? val.bk_target_service_instance_id
        : this.curNode?.type === 'host'
          ? this.panel.targets?.[0]?.handleCreateItemId(val, true)
          : `${val.bk_inst_id}-${val.bk_obj_id}`;
  }

  @Watch('viewOptions', { immediate: true })
  handleViewOptionsUpdate() {
    this.localViewOptions = deepClone(this.viewOptions);
    this.checkedNodeChange(this.localViewOptions.filters);
  }

  @Watch('compareTargets', { immediate: true })
  compareTargetsChange() {
    this.localCompareTargets = deepClone(this.viewOptions?.compares?.targets);
  }

  created() {
    this.getHostTreeData();
    this.tabActiveChange();
  }

  /** 获取topo tree数据 */
  getHostTreeData() {
    if (!this.apiData) return;
    this.loading = true;
    const variablesService = new VariablesService(this.viewOptions);
    this.$api[this.apiData.apiModule]
      [this.apiData.apiFunc]({
        ...variablesService.transformVariables(this.apiData.data),
        condition_list: transformConditionValueParams(this.searchCondition)
      })
      .then(data => {
        this.emptyStatusType = 'empty';
        const treeData = (typeTools.isObject(data) ? data.data : data) as TreeNodeItem[];
        this.conditionList = data.condition_list || [];
        this.searchCondition = updateBkSearchSelectName(this.conditionList, this.searchCondition);
        this.hostTreeData = treeData;
        this.traverseTree(treeData);
        this.initExpanedSelectedNode(treeData);
        this.handleListChange();
        const { bk_inst_id, bk_target_service_instance_id } = this.viewOptions.filters;
        if (bk_inst_id !== undefined || bk_target_service_instance_id !== undefined) {
          this.getNodeName();
        } else if (this.viewOptions.filters?.bk_host_id) {
          setTimeout(() => {
            const node = this.bigTreeRef.getNodeById(this.viewOptions.filters.bk_host_id);
            node?.data && this.$emit('titleChange', node.data.display_name || node.data.ip);
          }, 10);
        }
        this.curNode.type === 'overview' && this.handleClickItem(null, true);
      })
      .catch(() => {
        this.emptyStatusType = '500';
      })
      .finally(() => (this.loading = false));
  }
  /** 查找节点或者服务实例的名称 */
  getNodeName() {
    const { bk_inst_id, bk_obj_id, bk_target_service_instance_id } = this.viewOptions.filters;
    const targetNode = this.handleFindNode(this.hostTreeData, node => {
      // eslint-disable-next-line max-len
      const isMatch =
        (node.bk_inst_id === bk_inst_id && node.bk_obj_id === bk_obj_id) ||
        (bk_target_service_instance_id !== undefined && bk_target_service_instance_id === node.service_instance_id);
      return isMatch;
    });
    const title = targetNode.bk_inst_name || targetNode.name;
    if (targetNode && title) this.handleTitleChange(undefined, title);
  }

  /** 查找树节点的目标数据,返回符合条件的数据节点,否则null  广度优先 */
  handleFindNode(treeData: Record<string, any>[], cb: (node: any) => boolean): Record<string, any> {
    if (!treeData.length) return null;
    const queues = [];
    treeData.forEach(node => {
      queues.push(node);
    });
    while (!!queues.length) {
      const currentNode = queues.shift();
      if (cb(currentNode)) return currentNode;
      if (!!currentNode.children?.length) {
        for (const item of currentNode.children) {
          queues.push(item);
        }
      }
    }
    return null;
  }

  /** 初始化展开选中节点 */
  initExpanedSelectedNode(treeData: TreeNodeItem[]) {
    const idMap: Record<string, any> = {
      service: (node: TreeNodeItem) => node.service_instance_id,
      host: (node: TreeNodeItem) => `${this.panel.targets?.[0]?.handleCreateItemId(node)}`,
      node: (node: TreeNodeItem) => `${node.bk_inst_id}-${node.bk_obj_id}`
    };
    const fn = (data: TreeNodeItem[]) => {
      // eslint-disable-next-line no-restricted-syntax
      for (const node of data) {
        const id = idMap[this.curNode.type]?.(node);
        if (id === this.curNode.id) return id;
        if (node.children?.length) return fn(node.children);
      }
    };
    const id = fn(treeData);
    id && this.$nextTick(() => this.bigTreeRef?.setExpanded([id]));
  }

  /** 搜索操作 */
  handleSearch() {
    if (this.emptyStatusType !== '500') this.emptyStatusType = this.searchCondition.length ? 'search-empty' : 'empty';
    this.getHostTreeData();
    const selectorSearch = transformConditionValueParams(this.searchCondition);
    this.handleUpdateQueryData({
      ...this.queryData,
      selectorSearch
    });
  }

  /** 本地搜索 */
  @Debounce(300)
  handleLocalSearch() {
    if (this.emptyStatusType !== '500') this.emptyStatusType = this.searchKeyword ? 'search-empty' : 'empty';
    this.isNoData =
      this.bigTreeRef?.filter({
        status: this.statusType,
        keyword: this.searchKeyword
      })?.length < 1;
  }

  /** 初始化展开的节点 */
  get defaultExpandedId() {
    const fn = (list: string | any[], targetName: string | number): any => {
      if (list?.length) {
        // eslint-disable-next-line no-restricted-syntax
        for (const item of list) {
          const sourceId =
            this.curNode?.type === 'host'
              ? `${this.panel.targets?.[0]?.handleCreateItemId(item)}`
              : `${item.bk_inst_id}-${item.bk_obj_id}`;
          if (this.showOverview && !targetName && !item.children) {
            return item;
          }
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
    const res = fn(this.hostTreeData, this.curNode?.id);
    const data = res ? [res.id] : [];
    if (this.bigTreeRef) {
      this.bigTreeRef.setSelected(data[0]);
      this.bigTreeRef.setExpanded(data);
    }
    return data;
  }

  /** big-tree搜索回调方法 */
  filterMethod(filterObj: { status: string; keyword: string }, node: { data: TreeNodeItem }): boolean {
    const { data } = node;
    if (data.name) {
      const searchTarget = [data.name, data.bk_host_name];
      let { keyword } = filterObj;
      if (isFullIpv6(padIPv6(filterObj.keyword))) {
        keyword = padIPv6(filterObj.keyword);
      }
      return this.isStatusFilter
        ? searchTarget.some(target => `${target ?? ''}`.indexOf(keyword) > -1) &&
            (filterObj.status === 'all' ? true : this.hostStatusMap[data.status] === filterObj.status)
        : searchTarget.some(target => `${target ?? ''}`.indexOf(keyword) > -1);
    }
    return false;
  }

  /** 刷新数据 */
  handleRefresh() {
    this.searchKeyword = '';
    if (!this.conditionList.length) this.handleLocalSearch();
    this.getHostTreeData();
  }

  /** 选中属性节点或子节点 */
  @Emit('checkedChange')
  handleClickItem(data: TreeNodeItem, isOverview = false): IViewOptions {
    this.localCompareTargets = [];
    if (!isOverview) {
      // 选中主机或节点时
      // eslint-disable-next-line no-nested-ternary
      this.curNode.type =
        'service_instance_id' in data ? 'service' : 'ip' in data || 'bk_target_ip' in data ? 'host' : 'node';
      // eslint-disable-next-line no-nested-ternary
      this.curNode.id =
        this.curNode?.type === 'service'
          ? data.service_instance_id
          : this.curNode?.type === 'host'
            ? `${this.panel.targets?.[0]?.handleCreateItemId(data)}`
            : `${data.bk_inst_id}-${data.bk_obj_id}`;
      this.handleTitleChange(data);
    } else {
      this.curNode.type = 'overview'; // 选中数据总览时
      this.curNode.id = null;
    }
    const viewOptions = this.handleGetSelectedViewOptions(data, isOverview);
    this.handleViewOptionsChnage(viewOptions);
    return viewOptions;
  }

  handleClickItemProxy(data: TreeNodeItem) {
    this.isOverviewActive = false;
    if (!data.bk_host_id && !this.canCheckedNode) return;
    this.handleClickItem(data);
  }

  /** 对外派发title */
  handleTitleChange(data: TreeNodeItem, title?: string) {
    this.$emit('titleChange', title || data?.bk_inst_name || data?.name, data);
  }

  /**
   * @description: 添加目标对比
   * @param {TreeNodeItem} node 节点数据
   * @return {*}
   */
  @Emit('compareChange')
  handleAddCompare(node: TreeNodeItem) {
    const value = this.panel.targets?.[0]?.handleCreateCompares(node);
    this.localCompareTargets.push(value);
    const viewOptions: IViewOptions = {
      ...this.localViewOptions,
      compares: {
        targets: this.localCompareTargets
      }
    };
    this.handleViewOptionsChnage(viewOptions);
  }

  /**
   * @description:对外提供一个主机信息的一维数组
   * @return {IHostNode[]}
   */
  @Emit('listChange')
  handleListChange(): IOption[] {
    const hostMap = new Map();
    const fn = (data: TreeNodeItem[]) => {
      data.forEach(item => {
        if (item.children) {
          fn(item.children);
        }
        if ('ip' in item || 'bk_host_id' in item) {
          const id = this.panel.targets?.[0]?.handleCreateItemId(item);
          !hostMap.has(id) &&
            hostMap.set(id, {
              ...item,
              id
            });
        }
      });
    };
    fn(this.hostTreeData);
    const hostList = Array.from(hostMap).map(item => item[1]) as IHostNode[];
    return hostList;
  }
  /** 对外输出一个viewOptions格式数据 */
  @Emit('change')
  handleViewOptionsChnage(viewOptions: IViewOptions): IViewOptions {
    return viewOptions;
  }

  /** 生成选中的viewOptions */
  handleGetSelectedViewOptions(node?: TreeNodeItem, isOverview = false): IViewOptions {
    /** filter需要保留路输入的额外参数， 更新特殊字段excludesKeyMap的值 */
    const excludesKeyMap = [
      'bk_target_ip',
      'bk_target_cloud_id',
      'bk_inst_id',
      'bk_obj_id',
      'bk_target_service_instance_id',
      'bk_host_id'
    ];
    const filterList = Object.entries(this.localViewOptions.filters || {});
    const filter = filterList.reduce((newObj, cur: [string, any]) => {
      const [key, value] = cur;
      !excludesKeyMap.includes(key) && (newObj[key] = value);
      return newObj;
    }, {});
    const viewOptions: IViewOptions = {
      ...this.localViewOptions,
      filters: {
        ...filter
      }
    };
    if (isOverview) {
      // 数据总览情况下
      viewOptions.filters = {};
    } else if (node) {
      if ('service_instance_id' in node) {
        viewOptions.filters = {
          bk_target_service_instance_id: node.service_instance_id
        };
      } else if ('ip' in node || 'bk_target_ip' in node) {
        const matchFields: any = {};
        if (typeof node.os_type !== 'undefined') {
          matchFields.os_type = node.os_type;
        }
        viewOptions.filters = {
          bk_target_ip: node.ip,
          bk_target_cloud_id: node.bk_cloud_id,
          bk_host_id: node.bk_host_id
        };
        viewOptions.matchFields = { ...matchFields };
      } else {
        viewOptions.filters = {
          bk_inst_id: node.bk_inst_id,
          bk_obj_id: node.bk_obj_id
        };
      }
    }
    return viewOptions;
  }

  /* 统计信息 */
  traverseTree(treeData: any) {
    const statusData = {};
    const hosts = new Set();
    const key = 'name';
    const recursiveTraverse = node => {
      if (node.children) {
        node.children.forEach(item => {
          recursiveTraverse(item);
        });
      } else if ((node.ip || node.instance_name || node.service_instance_id) && !hosts.has(node[key])) {
        hosts.add(node[key]);
        /** 生成主机/服务实例的id */
        node.id = this.panel.targets?.[0]?.handleCreateItemId(node);
        const { status } = node;
        const localStatus = this.hostStatusMap[status];
        if (!statusData[localStatus]?.count) {
          statusData[localStatus] = {
            count: 0
          };
        }
        statusData[localStatus].count += 1;
      }
    };
    treeData.forEach(node => {
      recursiveTraverse(node);
    });
    this.statusData = statusData;
  }

  handleStatusChange(v: string) {
    this.statusType = v;
    this.isNoData =
      this.bigTreeRef?.filter({
        status: this.statusType,
        keyword: this.searchKeyword
      })?.length < 1;
  }

  /** 生成主机主机的状态类名 */
  getItemStatusClassName(status: string | number): StatusClassNameType {
    const target = this.statusMapping.find(item => item.id === status);
    return (target.color as StatusClassNameType) || 'none';
  }

  handleShowOverview() {
    this.isOverviewActive = !this.isOverviewActive;
    if (this.isOverviewActive) {
      this.curNode = { id: null, type: 'overview' };
      this.handleClickItem(null, true);
      this.handleTitleChange(null, this.$tc('概览'));
      this.handleOverviewChange();
    }
  }

  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      if (this.conditionList.length) {
        this.searchCondition = [];
        this.handleSearch();
      } else {
        this.searchKeyword = '';
        this.handleLocalSearch();
      }
      return;
    }
    if (type === 'refresh') {
      this.getHostTreeData();
      return;
    }
  }

  @Emit('overviewChange')
  handleOverviewChange() {}

  render() {
    const scopedSlots = {
      default: ({ data }: { data: TreeNodeItem }) => (
        <div
          class={[
            'bk-tree-node',
            {
              active:
                `${this.panel.targets?.[0]?.handleCreateItemId(data)}` === this.curNode?.id ||
                (this.enableCmdbLevel && `${data.bk_inst_id}-${data.bk_obj_id}` === this.curNode?.id) ||
                data.service_instance_id === this.curNode.id,
              'checked-target': this.isTargetCompare && this.compareTargets.includes(data.id)
            }
          ]}
          onClick={m.stop(() => this.handleClickItemProxy(data))}
        >
          <span
            class='node-content'
            style='padding-right: 5px;'
          >
            <div
              class='node-content-wrap'
              v-bk-overflow-tips={{
                content: `${
                  'service_instance_id' in data ? data.name : data.name || data.display_name || data.bk_inst_name
                }`
              }}
            >
              {!!data.status ? (
                <span class={['host-status', `status-${this.getItemStatusClassName(data.status)}`]}></span>
              ) : undefined}
              <span class='host-name'>
                {'service_instance_id' in data ? data.name : data.name || data.display_name || data.bk_inst_name}
              </span>
              {!data.service_instance_id && data.alias_name ? (
                <span class='host-alias-name'>({data.alias_name})</span>
              ) : undefined}
            </div>
            {data.bk_host_id && this.isTargetCompare ? (
              <span class='add-compared'>
                {this.compareTargets.includes(data.id) ? (
                  <i class='icon-monitor icon-mc-check-small'></i>
                ) : (
                  <span
                    class='add-compared-btn'
                    onClick={m.stop(() => this.handleAddCompare(data))}
                  >
                    {this.$t('对比')}
                  </span>
                )}
              </span>
            ) : undefined}
          </span>
        </div>
      )
    };
    return (
      <div
        class='host-tree-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='host-tree-main'>
          <div class='host-tree-tool'>
            <div class='host-tree-search-row'>
              {this.conditionList.length ? (
                <bk-search-select
                  placeholder={this.$t('搜索')}
                  vModel={this.searchCondition}
                  show-condition={false}
                  show-popover-tag-change={false}
                  data={this.currentConditionList}
                  onChange={this.handleSearch}
                />
              ) : (
                <bk-input
                  v-model={this.searchKeyword}
                  right-icon='bk-icon icon-search'
                  placeholder={this.$t('搜索IP / 主机名')}
                  onInput={this.handleLocalSearch}
                ></bk-input>
              )}
              {/* <bk-input
              v-model={this.searchKeyword}
              right-icon="bk-icon icon-search"
              placeholder={this.$t('搜索IP / 主机名')}
              onInput={this.handleSearch}></bk-input> */}
              {/* <bk-search-select
              placeholder={this.$t('搜索')}
              vModel={this.searchCondition}
              show-condition={false}
              data={this.conditionList}
              onChange={this.handleSearch} /> */}
              <bk-button
                class='refresh-btn'
                onClick={this.handleRefresh}
              >
                <i class='icon-monitor icon-shuaxin'></i>
              </bk-button>
            </div>
            {this.isStatusFilter && (
              <StatusTab
                needAll={false}
                disabledClickZero
                v-model={this.statusType}
                statusList={this.statusList}
                onChange={this.handleStatusChange}
              ></StatusTab>
            )}
            {this.showOverview && (
              <div
                class={['overview-item', { active: this.isOverviewActive }]}
                onClick={this.handleShowOverview}
              >
                <i class='icon-monitor icon-mc-overview'></i>
                {this.$t('概览')}
              </div>
            )}
            {this.isTargetCompare ? (
              <bk-alert
                class='target-compare-tips'
                type='info'
                title={this.$t('选择目标进行对比')}
              ></bk-alert>
            ) : undefined}
          </div>
          {this.hostTreeData.length ? (
            <div style={{ height: `${this.hostTreeHeight}px` }}>
              <bk-big-tree
                class={['big-tree', { 'clear-selected': !this.curNode?.id }]}
                ref='bigTreeRef'
                expand-on-click={false}
                selectable={true}
                filter-method={this.filterMethod}
                default-expanded-nodes={this.defaultExpandedId}
                data={this.hostTreeData}
                scopedSlots={scopedSlots}
              >
                <template slot='empty'>
                  {this.isNoData && (
                    <EmptyStatus
                      type={this.emptyStatusType}
                      onOperation={this.handleEmptyOperation}
                    />
                  )}
                </template>
              </bk-big-tree>
            </div>
          ) : (
            <EmptyStatus
              type={this.emptyStatusType}
              onOperation={this.handleEmptyOperation}
            />
          )}
        </div>
      </div>
    );
  }
}
