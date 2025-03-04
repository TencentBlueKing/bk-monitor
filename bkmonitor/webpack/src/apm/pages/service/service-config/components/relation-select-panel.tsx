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
import { random } from 'monitor-common/utils';

import OverflowPrefixEllipsis from './overflow-prefix-ellipsis';

import './relation-select-panel.scss';

interface TreeNodeData {
  // 链式id
  id: string;
  name: string;
  // 当前id
  key: string;
  // 根节点
  root?: boolean;
  // 类型 cluster namespace workload  more等
  type?: string;
  // 父级数据
  parentData?: TreeNodeData;
  // 总数
  count?: number;
  loading?: boolean;
  // 叶子结点
  leaf?: boolean;
  // 子集
  children?: TreeNodeData[];
}

interface RelationSelectPanelProps {
  value: string[];
}

@Component
export default class RelationSelectPanel extends tsc<RelationSelectPanelProps> {
  @Prop({ default: () => [] }) value: string[];
  @Ref('tree') treeRef: any;

  searchVal = '';

  data: TreeNodeData[] = [];

  /** 是否显示checkbox */
  isShowCheckbox(data: TreeNodeData) {
    if (data.type === 'more' || data.root) return false;
    return true;
  }

  /** 加载更多 */
  async handleShowMore(data: TreeNodeData) {
    const { type, id: parentId } = data.parentData;
    data.loading = true;
    const node = this.treeRef.getNodeById(parentId);
    const children = node.children;
    let items = [];
    /** 集群加载更多 */
    if (type === 'cluster') {
      const result = await this.getNamespaceWorkloadOverview({
        bcs_cluster_id: parentId,
        page: Math.floor(children.length / 5) + 1,
        parentData: data.parentData,
      });
      items = result.items;
    }

    /** workload加载更多 */
    if (type === 'workload') {
      const [bcs_cluster_id, namespace, workloadType] = parentId.split('/');
      const result = await this.getListResources({
        bcs_cluster_id,
        namespace,
        workloadType,
        page: Math.floor(children.length / 5) + 1,
        parentData: data.parentData,
      });
      items = result.items;
    }
    data.loading = false;
    this.treeRef.removeNode(data.id);
    this.treeRef.addNode(items.slice(children.length), parentId);
    if (node.checked) this.treeRef.setChecked(parentId);
  }

  handleCheckChange(ids) {
    console.log(ids);
  }

  /** 判断节点是否有展开功能 */
  lazyDisabled(node) {
    if (node.data.type === 'more' || node.data.leaf || node.data.count === 0) return true;
    return false;
  }

  /** 展开懒加载功能 */
  async lazyMethod(node) {
    if (node.data.type === 'workload') {
      const [bcs_cluster_id, namespace] = node.data.id.split('/');
      const { items } = await this.getListResources({
        bcs_cluster_id,
        namespace,
        workloadType: node.name,
        parentData: node.data,
        page: 1,
      });
      return { data: items || [] };
    }
  }

  /** 获取集群列表 */
  async getClusterList() {
    const clusterList = await listBcsCluster();
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
    Promise.all(promiseList).then(res => {
      this.data = res;
    });
  }

  /** 获取集群下namespace的数量和workload数量 */
  async getNamespaceWorkloadOverview(params) {
    const { count, items, workload_count } = await namespaceWorkloadOverview({
      query_string: this.searchVal,
      bcs_cluster_id: params.bcs_cluster_id,
      page: params.page,
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
      query_string: this.searchVal,
      start_time: 0,
      end_time: 0,
      page: params.page,
      filter_dict: {
        namespace: params.namespace,
        workload: `${params.workloadType}:`,
      },
    }).catch(() => ({ count: 0, items: [] }));

    const data: TreeNodeData[] = items.map(workload => {
      return {
        id: `${params.parentData.id}/${workload.workload}`,
        key: workload.workload,
        type: params.workloadType,
        name: workload.workload,
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

  mounted() {
    this.getClusterList();
  }

  render() {
    return (
      <div class='relation-select-panel-comp'>
        <div class='tree-panel'>
          <bk-input
            v-model={this.searchVal}
            left-icon='bk-icon icon-search'
            placeholder={this.$t('请输入关键字')}
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
                          {data.name}
                        </span>
                        {data.count !== undefined && <span class='item-count'>{data.count}</span>}
                      </span>
                    </div>
                  );
                },
              }}
              data={this.data}
              default-checked-nodes={this.value}
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
              {this.$t('已关联 workload')}({this.value.length})
            </span>
            <span class='clear-btn'>{this.$t('清空')}</span>
          </div>

          <div class='selected-list'>
            {this.value.map(item => (
              <div
                key={item}
                class='selected-item'
              >
                <OverflowPrefixEllipsis
                  class='selected-item-name'
                  text={item}
                />
                <i class='icon-monitor icon-mc-close' />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
