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

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listPipeline, pipelineOverview } from 'monitor-api/modules/apm_service';
import { Debounce, random } from 'monitor-common/utils';

import OverflowPrefixEllipsis from './overflow-prefix-ellipsis';

import './pipeline-select-panel.scss';

interface ILocalValue {
  id: string;
  key: string;
  name: string;
  projectId: string;
}

interface IParams {
  appName: string;
  bkBizId: number;
}

interface ISendValue {
  pipeline_id: string;
  pipeline_name: string;
  project_id: string;
}

interface PipelineSelectPanelProps {
  isEditing: boolean;
  params: IParams;
  value: ISendValue[];
}

interface TreeNode {
  // 流水线总数
  count: number;
  // 子节点id
  id: string;
  key: string;
  loading?: boolean;
  name: string;
  // 子集页码
  page: number;
  // 一级项目id
  projectId?: string;
  data?: {
    key: string;
  };
  parent?: {
    id: string;
  };
  state: {
    checked: boolean;
  };
}

interface TreeNodeData {
  // 子集
  children: TreeNode[];
  // 流水线总数
  count?: number;
  // 节点id
  id: string;
  key: string;
  name: string;
  // 一级项目id
  projectId?: string;
  // 根节点
  root?: boolean;
  // 子集页码
  // page: number;
}

@Component
export default class PipelineSelectPanel extends tsc<
  PipelineSelectPanelProps,
  {
    onChange: (value: string[]) => void;
  }
> {
  @Prop({ default: () => [] }) value: ISendValue[];
  @Prop({ default: false }) isEditing: boolean;
  @Prop({ default: () => {} }) params: IParams;
  @Ref('tree') treeRef: any;

  searchVal = '';

  data: TreeNodeData[] = [];
  loading = false;
  localValue: ILocalValue[] = [];
  cacheLocalValue: ILocalValue[] = [];

  @Watch('isEditing')
  handleResetData(isEditing: boolean) {
    if (!isEditing) {
      this.data = [];
      this.localValue = [...this.cacheLocalValue];
      this.handleChange();
    }
  }

  @Emit('change')
  handleChange() {
    return this.localValue.map(item => ({
      project_id: item.projectId,
      pipeline_id: item.id,
      pipeline_name: item.name,
    }));
  }

  mounted() {
    this.localValue = this.mapChildrenData(this.value);
    this.cacheLocalValue = [...this.localValue] || [];
  }

  @Debounce(300)
  handleSearch(val: string) {
    this.data = [];
    this.searchVal = val;
    this.getPipelineData();
  }

  // 隐藏流水线选择框
  handleHidePopover() {
    this.searchVal = '';
    this.data = [];
  }

  // 删除流水线
  handleDelete(id: string) {
    this.localValue = this.localValue.filter(item => item.id !== id);
    this.updateNodesState([id], false);
    this.handleChange();
  }

  // 是否显示checkbox
  isShowCheckbox(data: TreeNodeData) {
    return !data.root && data.key !== 'more';
  }

  // 加载更多
  async handleShowMore(data: TreeNode) {
    const { id, projectId, page } = data;
    data.loading = true;
    const parentNode: TreeNodeData = this.treeRef.getNodeById(projectId);
    const children = parentNode.children;
    let items = [];
    const { bkBizId: bk_biz_id, appName: app_name } = this.params;
    const result = await listPipeline({
      bk_biz_id,
      app_name,
      project_id: projectId,
      keyword: this.searchVal,
      page,
      page_size: 5,
    });
    if (result.items.length) {
      data.page += 1;
      items = this.mapChildrenData(result.items);

      // 是否需要加载更多
      if (result.count > children.length + items.length) {
        items.push({
          id: `${items[items.length - 1].id}/more_${random(5)}`,
          projectId: projectId,
          key: 'more',
          name: '加载更多',
          loading: false,
          page: data.page,
        });
      }
      this.treeRef.removeNode(id);
      this.treeRef.addNode(items, projectId);
      this.updateNodesState(
        this.localValue.filter(selectItem => items.some(item => item.id === selectItem.id)).map(item => item.id),
        true
      );
    }
  }

  // 节点勾选切换
  async handleCheckChange(ids: string[], node: TreeNode) {
    if (!node.parent || node.data.key === 'more') return;
    if (node.state.checked) {
      this.localValue.push({
        id: node.id,
        name: node.name,
        key: node.key,
        projectId: node.parent.id,
      });
    } else {
      this.localValue = this.localValue.filter(item => item.id !== node.id);
    }
    this.handleChange();
  }

  // 默认展开的节点
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

  // 默认选中checkbox的节点
  getDefaultCheckedIds() {
    return this.localValue.map(item => item.id);
  }

  // 更新节点选中状态
  async updateNodesState(nodeIds: string[], checked: boolean) {
    if (nodeIds.length) {
      this.treeRef?.setChecked(nodeIds, { emitEvent: false, checked });
    }
  }

  // 获取流水线数据
  async getPipelineData() {
    if (this.data.length) return;
    this.loading = true;
    const { bkBizId: bk_biz_id, appName: app_name } = this.params;
    const pipeData = await pipelineOverview({
      bk_biz_id,
      app_name,
      keyword: this.searchVal,
    }).catch(() => []);
    this.loading = false;
    if (pipeData.length) {
      this.data = this.mapTreeData(pipeData);
    }
  }

  // 数据转换TreeNode格式
  mapTreeData(data) {
    // filter: 子元素没有节点的父级不展示
    return data
      .filter(root => root.count && root.items?.length)
      .map(root => {
        return {
          id: root.project_id,
          key: `${root.project_name}${root.project_id}`,
          name: `(${root.project_name || ''})${root.project_id || ''}`,
          root: true,
          count: root.count,
          children: root.items.flatMap((pipeline, index) => {
            const treeNode = {
              id: pipeline.pipeline_id,
              key: pipeline.pipeline_id,
              name: pipeline.pipeline_name,
              parentId: pipeline.project_id,
            };
            // 加载更多选项
            if (root.items.length - 1 === index && root.count > root.items.length) {
              return [
                treeNode,
                {
                  id: `${pipeline.pipeline_id}/more_${random(5)}`,
                  projectId: root.project_id,
                  key: 'more',
                  name: '加载更多',
                  loading: false,
                  page: 2, // 查询父级接口已经给了一部分数据，加载更多从2开始
                },
              ];
            }
            return treeNode;
          }),
        };
      });
  }

  // 转换流水线数据格式
  mapChildrenData(data: ISendValue[]) {
    return data.map(item => ({
      id: item.pipeline_id,
      name: item.pipeline_name,
      key: item.pipeline_id,
      projectId: item.project_id,
    }));
  }

  // 高亮列表内的搜索内容
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

  // 加载更多
  renderLoadMore(item: TreeNode) {
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

  // 新增流水线按钮
  renderPipelineAdd() {
    return (
      <bk-popover
        width='360'
        height='236'
        ext-cls='pipeline-add-popover'
        component-event-delay='300'
        placement='bottom-start'
        theme='light'
        tippy-options={{ trigger: 'click', arrow: false, distance: 0 }}
        on-hide={this.handleHidePopover}
        on-show={this.getPipelineData}
      >
        <div class='add-pipeline'>
          <i class='icon-monitor icon-mc-plus-fill' />
          {this.$t('新增流水线')}
        </div>
        <div
          class='pipeline-select-panel-comp'
          slot='content'
        >
          <div class='tree-panel'>
            <bk-input
              clearable={true}
              left-icon='bk-icon icon-search'
              placeholder={this.$t('请输入关键字')}
              value={this.searchVal}
              onChange={this.handleSearch}
            />
            {this.loading ? (
              <div class='skeleton-wrap'>
                <div class='skeleton-element' />
                <div class='skeleton-element' />
                <div class='skeleton-element' />
                <div class='skeleton-element' />
              </div>
            ) : (
              <div class='pipeline-workload-tree'>
                {!this.data.length ? (
                  <div class='pipeline-empty'>{this.$t('暂无选项')}</div>
                ) : (
                  <bk-big-tree
                    ref='tree'
                    scopedSlots={{
                      default: ({ data }) => {
                        if (data.key === 'more') return this.renderLoadMore(data);
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
                              {data.count ? <span class='item-count'>{data.count}</span> : undefined}
                            </span>
                          </div>
                        );
                      },
                    }}
                    check-on-click={true}
                    check-strictly={false}
                    data={this.data}
                    default-checked-nodes={this.getDefaultCheckedIds()}
                    default-expanded-nodes={this.getDefaultExpandedIds()}
                    padding={0}
                    show-checkbox={this.isShowCheckbox}
                    on-check-change={this.handleCheckChange}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      </bk-popover>
    );
  }

  // 已选择的流水线/传入的流水线信息
  renderPipelineItem() {
    return this.localValue.map(item => (
      <div
        key={item.id}
        class='pipeline-item'
      >
        <div class='pipeline-item-hd'>
          <OverflowPrefixEllipsis
            class='pipeline-item-name'
            text={item.name}
          />
          {this.isEditing && (
            <i
              class='icon-monitor icon-mc-close'
              on-click={() => this.handleDelete(item.id)}
            />
          )}
        </div>
      </div>
    ));
  }

  render() {
    return (
      <div class='pipeline-content'>
        {this.isEditing && this.renderPipelineAdd()}
        {this.renderPipelineItem()}
      </div>
    );
  }
}
