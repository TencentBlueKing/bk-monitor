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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listBcsCluster, listK8sResources, namespaceWorkloadOverview } from 'monitor-api/modules/k8s';
import { Debounce, random } from 'monitor-common/utils';

import OverflowPrefixEllipsis from './overflow-prefix-ellipsis';

import './relation-select-panel.scss';

enum QueryFromType {
  NameSpace = 'namespace',
  Workload = 'workload',
}
interface RelationSelectPanelProps {
  value: string[];
}
interface TreeNode extends TreeNodeData {
  data: TreeNodeData & {
    count: number;
    leaf: boolean;
    queryFrom: QueryFromType;
    type: string;
  };
  state: {
    checked: boolean;
  };
}
interface TreeNodeData {
  // 子集
  children?: TreeNodeData[];
  // 总数
  count?: number;
  // 链式id
  id: string;
  // 当前id
  key: string;
  // 叶子结点
  leaf?: boolean;
  loading?: boolean;
  name: string;
  // 父级数据
  parentData?: TreeNodeData;
  // 根节点
  root?: boolean;
  // 类型 cluster namespace workload  more等
  type?: string;
}

@Component
export default class RelationSelectPanel extends tsc<
  RelationSelectPanelProps,
  {
    onChange: (value: string[]) => void;
  }
> {
  @Prop({ default: () => [] }) value: string[];
  @Ref('tree') treeRef: any;

  searchVal = '';

  data: TreeNodeData[] = [];
  clusterList = [];
  loading = false;
  localValue: string[] = [];
  allCheckedValue: string[] = [];

  mounted() {
    this.localValue = this.value || [];
    this.getClusterTreeData();
  }
  @Debounce(300)
  handleSearch(val: string) {
    this.searchVal = val;
    this.getClusterTreeData();
  }

  handleClear() {
    this.refreshTreeData([], this.localValue);
    this.localValue = [];
    this.$emit('change', this.localValue);
  }
  handleDelete(id: string) {
    this.updateNodesState([id], false, false);
    this.localValue = this.localValue.filter(item => item !== id);
    this.$emit('change', this.localValue);
  }
  /** 是否显示checkbox */
  isShowCheckbox(data: TreeNodeData) {
    if (data.type === 'more' || data.root) return false;
    return true;
  }

  /** 加载更多 */
  async handleShowMore(data: TreeNodeData) {
    const { type, id: parentId } = data.parentData;
    data.loading = true;
    const parentNode: TreeNode = this.treeRef.getNodeById(parentId);
    const children = parentNode.children;
    let items = [];
    /** 集群加载更多 */
    if (type === 'cluster') {
      const result = await this.getNamespaceWorkloadOverview({
        bcs_cluster_id: parentId,
        page: Math.floor(children.length / 5) + 1,
        parentData: data.parentData,
      });
      items = result.items;
    } else if (type === 'workload') {
      /** workload加载更多 */
      const [bcs_cluster_id, namespace, workloadType] = parentId.split('/');
      const result = await this.getListResources({
        bcs_cluster_id,
        namespace,
        workloadType,
        page: Math.floor(children.length / 5) + 1,
        parentData: data.parentData,
        query_string: parentNode.data.queryFrom === QueryFromType.NameSpace ? '' : this.searchVal,
      });
      items = result.items;
    }
    data.loading = false;
    this.treeRef.removeNode(data.id);
    this.treeRef.addNode(items.slice(children.length), parentId);
    this.refreshTreeData(this.localValue);
  }

  async handleCheckChange(ids: string[], node: TreeNode) {
    this.updateNodesState([node.id], node.state.checked, node.state.checked);
    const value = this.treeRef.nodes.filter(node => node.state.checked && !node.state.disabled).map(node => node.id);
    const list = [...this.localValue];
    if (this.searchVal) {
      if (node.state.checked) {
        list.push(...value);
      } else {
        const index = list.indexOf(node.id);
        if (index > -1) {
          list.splice(index, 1);
        }
      }
    }
    this.localValue = Array.from(new Set(!this.searchVal ? value : list));
    this.$emit('change', this.localValue);
  }

  /** 判断节点是否有展开功能 */
  lazyDisabled(node: TreeNode) {
    if (node.data.type === 'more' || node.data.leaf || node.data.count === 0) return true;
    return false;
  }

  /** 展开懒加载功能 */
  async lazyMethod(node: TreeNode) {
    if (node.data.type === 'workload') {
      const [bcs_cluster_id, namespace] = node.data.id.split('/');
      this.loading = true;
      const { items } = await this.getListResources({
        bcs_cluster_id,
        namespace,
        workloadType: node.name,
        parentData: node.data,
        page: 1,
        query_string: node.data.queryFrom === QueryFromType.NameSpace ? '' : this.searchVal,
      });
      node.data.children.push(...items);
      this.loading = false;
    }
    setTimeout(() => {
      this.refreshTreeData(this.localValue);
    }, 100);
    return {
      data: node.data?.children || [],
    };
  }
  getDefaultExpandedIds() {
    const expanded = [];
    for (const item of this.data) {
      expanded.push(item.id);
      if (item.children?.length) {
        for (const child of item.children) {
          expanded.push(child.id);
        }
      }
    }
    return expanded;
  }

  async updateNodesState(nodeIds: string[], checked: boolean, childDisable: boolean) {
    const updateNodeAndChildren = (node: TreeNode, checked: boolean, disabled: boolean) => {
      // 如果有子节点，递归设置子节点
      if (node.children?.length) {
        this.treeRef?.setDisabled(
          node.children.map(n => n.id),
          { emitEvent: false, disabled }
        );
        this.treeRef?.setChecked(
          node.children.map(n => n.id),
          { emitEvent: false, checked }
        );
        for (const child of node.children) {
          updateNodeAndChildren(this.treeRef.getNodeById(child.id), checked, disabled);
        }
      }
    };

    for (const id of nodeIds) {
      const node: TreeNode = this.treeRef.getNodeById(id);
      if (!node) continue;
      this.treeRef?.setChecked(node.id, { emitEvent: false, checked });
      updateNodeAndChildren(node, checked, childDisable);
    }
  }
  /**
   *
   * @param ids 重新设置的值
   * @param oldIds 上一次操作的值
   */
  async refreshTreeData(ids: string[], oldIds: string[] = []) {
    await this.$nextTick();
    // 处理旧节点
    this.updateNodesState(oldIds, false, false);

    // 处理新节点
    this.updateNodesState(ids, true, true);
  }

  async setExpandedData() {
    // 重新设置展开
    setTimeout(() => {
      this.treeRef?.setExpanded(this.getDefaultExpandedIds(), { emitEvent: false, expanded: true });
    }, 100);
  }
  /** 获取集群列表 */
  async getClusterList() {
    let clusterList = structuredClone(this.clusterList || []);
    if (!clusterList.length) {
      clusterList = await listBcsCluster().catch(() => []);
    }
    this.clusterList = clusterList || [];
    return structuredClone(clusterList);
  }
  async getClusterTreeData() {
    this.loading = true;
    const clusterList = await this.getClusterList();
    const promiseList = clusterList.map(async cluster => {
      const { items, workload_count } = await this.getNamespaceWorkloadOverview({
        bcs_cluster_id: cluster.id,
        page: 1,
      });
      const result = {
        ...cluster,
        type: 'cluster',
        key: cluster.id,
        root: true,
        count: workload_count,
      };
      return {
        ...result,
        children: items.map(item => ({ ...item, parentData: result })),
      };
    });
    const data = await Promise.all(promiseList).catch(() => []);
    this.data = data;
    this.setExpandedData();
    this.refreshTreeData(this.localValue);
    this.loading = false;
  }
  /** 获取集群下namespace的数量和workload数量 */
  async getNamespaceWorkloadOverview(params) {
    const { count, items, workload_count } = await namespaceWorkloadOverview({
      query_string: this.searchVal,
      bcs_cluster_id: params.bcs_cluster_id,
      page: params.page,
    }).catch(() => {
      return { count: 0, items: [], workload_count: 0 };
    });
    const data: TreeNodeData[] = items.map(item => {
      const namespaceData = {
        type: 'namespace',
        id: `${params.bcs_cluster_id}/${item.namespace}`,
        name: item.namespace,
        key: item.namespace,
        count: item.workload_count,
        parentData: params.parentData,
      };
      return {
        ...namespaceData,
        children: item.workload_overview.map(workload => ({
          parentData: namespaceData,
          type: 'workload',
          id: `${params.bcs_cluster_id}/${item.namespace}/${workload[0]}`,
          key: workload[0],
          name: workload[0],
          count: workload[1],
          children: [],
          queryFrom: this.searchVal ? item.query_from : QueryFromType.Workload,
        })),
      };
    });
    if (count !== data.length) {
      data.push({
        id: `${params.bcs_cluster_id}/more_${random(5)}`,
        type: 'more',
        key: 'more',
        name: this.$tc('点击加载更多'),
        loading: false,
        parentData: params.parentData,
      });
    }
    return {
      count,
      items: data,
      workload_count,
    };
  }

  /** 获取workload各分类下的列表数据 */
  async getListResources(params) {
    const { count, items } = await listK8sResources({
      bcs_cluster_id: params.bcs_cluster_id,
      resource_type: 'workload',
      scenario: 'performance',
      query_string: params.query_string ?? this.searchVal,
      start_time: 0,
      end_time: 0,
      page: params.page,
      filter_dict: {
        namespace: params.namespace,
        workload: `${params.workloadType}:`,
      },
    }).catch(() => ({ count: 0, items: [] }));

    const data: TreeNodeData[] = items.map(workload => {
      const name = workload.workload.split(':')?.[1] || workload.workload;
      return {
        id: `${params.parentData.id}/${name}`,
        key: workload.workload,
        type: params.workloadType,
        name,
        leaf: true,
        parentData: params.parentData,
      };
    });
    if (count !== data.length) {
      data.push({
        id: `${params.parentData.id}/more_${random(5)}`,
        key: 'more',
        type: 'more',
        name: this.$tc('点击加载更多'),
        parentData: params.parentData,
        loading: false,
      });
    }

    return {
      count,
      items: data,
    };
  }
  /**
   * @description: 查询字符传匹配
   * @param {string} str
   * @return {*}
   */
  getSearchNode = (str: string, search: string) => {
    if (!str || !search) return str;
    let keyword = search.trim();
    const len = keyword.length;
    if (!keyword?.trim().length || !str.toLocaleLowerCase().includes(keyword.toLocaleLowerCase())) return str;
    const list = [];
    let lastIndex = -1;
    keyword = keyword.replace(/([.*/]{1})/gim, '\\$1');
    str.replace(new RegExp(`${keyword}`, 'igm'), (key, index) => {
      if (list.length === 0 && index !== 0) {
        list.push(str.slice(0, index));
      } else if (lastIndex >= 0) {
        list.push(str.slice(lastIndex + key.length, index));
      }
      list.push(<span class='is-keyword'>{key}</span>);
      lastIndex = index;
      return key;
    });
    if (lastIndex >= 0) {
      list.push(str.slice(lastIndex + len));
    }
    return list.length ? list : str;
  };
  renderLoadMore(item: TreeNodeData) {
    return (
      <div class='show-more'>
        <bk-spin
          style={{ display: item.loading ? 'inline-block' : 'none' }}
          size='mini'
        />
        <div
          style={{ display: !item.loading ? 'flex' : 'none' }}
          class='content'
          onClick={() => this.handleShowMore(item)}
        >
          <span class='dot' />
          <span class='dot' />
          <span class='dot' />
          <span class='text'>{this.$t('点击加载更多')}</span>
        </div>
      </div>
    );
  }

  render() {
    return (
      <div class='relation-select-panel-comp'>
        <div class='tree-panel'>
          <bk-input
            clearable={true}
            left-icon='bk-icon icon-search'
            placeholder={this.$t('请输入关键字')}
            value={this.searchVal}
            onChange={this.handleSearch}
          />
          <div class='relation-workload-tree'>
            <bk-big-tree
              ref='tree'
              scopedSlots={{
                default: ({ data }) => {
                  if (data.type === 'more') return this.renderLoadMore(data);
                  return (
                    <div class={['bk-tree-node', { root: data.root }]}>
                      <span
                        style='padding-right: 5px;'
                        class='node-content'
                      >
                        <span
                          class='item-name'
                          v-bk-overflow-tips
                        >
                          {this.getSearchNode(data.name, this.searchVal)}
                        </span>
                        {data.count !== undefined && <span class='item-count'>{data.count}</span>}
                      </span>
                    </div>
                  );
                },
              }}
              check-strictly={false}
              data={this.data}
              default-checked-nodes={this.localValue}
              default-expanded-nodes={this.getDefaultExpandedIds()}
              lazy-disabled={this.lazyDisabled}
              lazy-method={this.lazyMethod}
              selectable={true}
              show-checkbox={this.isShowCheckbox}
              on-check-change={this.handleCheckChange}
            />
          </div>
        </div>
        <div class='selected-panel'>
          <div class='header'>
            <span class='select-panel-title'>
              {this.$t('已关联')}（{this.localValue.length}）
            </span>
            <span
              class='clear-btn'
              onClick={this.handleClear}
            >
              {this.$t('清空')}
            </span>
          </div>

          <div class='selected-list'>
            {this.localValue.map(item => (
              <div
                key={item}
                class='selected-item'
              >
                <OverflowPrefixEllipsis
                  class='selected-item-name'
                  text={item}
                />
                <i
                  class='icon-monitor icon-mc-close'
                  onClick={() => this.handleDelete(item)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
