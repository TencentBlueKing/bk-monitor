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

import { getHostOrTopoNodeDetail } from 'monitor-api/modules/scene_view';

import './shield-tree-compnent.scss';

interface IProps {
  bizId: string | number; // 查询节点树id
  bkHostId: string | number; // 查询节点树id
  show?: boolean; 
}

interface TreeNodeData {
  // 子集
  children?: TreeNodeData[];
  // id
  id: string;
  instId: string;
  // 当前id
  key: string;
  name: string;  
  state: {
    checked: boolean;
  };
}

@Component
export default class ShieldTreeCompnent extends tsc<
  IProps,
  {
    onCancel: () => void;
    onConfirm: [];
  }
> {
  @Prop({ type: [String, Number], default: '' }) bizId: string | number;
  @Prop({ type: [String, Number], default: '' }) bkHostId: string | number;
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Ref('tree') treeRef: any;

  loading = true;
  checkedIds = [];
  treeNodeList: TreeNodeData[] = [];

  @Watch('show', { immediate: true })
  handleWatchShow() {
    this.checkedIds = [];
    this.treeNodeList = [];
    if (this.show) {
      this.getTopoNodeDetailData();
    }
  }

  @Emit('confirm')
  handleConfirm() {
    const findCheckedNodes = (nodes) => {
      let result = [];
      for (const item of nodes) {
        const fullId = `${item.instId}_${item.objId}`;
        if (this.checkedIds.includes(fullId)) {
          result.push({
            bk_obj_id: item.objId,
            bk_inst_id: item.instId,
            node_name: item.name,
          });
          continue;
        }
        // 子节点中查找是否存在已选中的节点
        if (item.children && item.children.length > 0) {
          result = result.concat(findCheckedNodes(item.children));
        }
      }
      return result;
    };
    const bkTopoNode = findCheckedNodes(this.treeNodeList);
    return bkTopoNode;
  }
  

  @Emit('cancel')
  handleCancel() {
    return undefined;
  }

  getTopoNodeDetailData() {
    if (!this.bkHostId || !this.bizId) return;
    this.loading = true;
    getHostOrTopoNodeDetail({
      bk_biz_id: this.bizId,
      topo_tree: true,
      bk_host_id: this.bkHostId,
    })
    .then(res => {
      this.treeNodeList = this.mapTreeData(res);
      
    })
    .catch(()=>{
      this.treeNodeList = [];
    })
    .finally(() => {
      this.loading = false;
    })
    
  }

  mapTreeData(data) {
    return data.map(item => ({
      id: `${item.bk_inst_id}_${item.bk_obj_id}`,
      instId: item.bk_inst_id,
      objId: item.bk_obj_id,
      name: `${item.bk_obj_name}(${item.bk_inst_name})`,
      state: {
        checked: false,
      },
      children: item.child && item.child.length > 0 ? this.mapTreeData(item.child) : [],
    }));
  }

  async updateNodesState(nodeIds: string[], checked: boolean, childDisable: boolean) {
    const updateNodeAndChildren = (node: TreeNodeData, checked: boolean, disabled: boolean) => {
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
      const node: TreeNodeData = this.treeRef.getNodeById(id);
      if (!node) continue;
      this.treeRef?.setChecked(node.id, { emitEvent: false, checked });
      updateNodeAndChildren(node, checked, childDisable);
    }
  }


  handleCheckChange(id, node) {
    this.updateNodesState([node.id], node.state.checked, node.state.checked);
    const value = this.treeRef.nodes.filter(node => node.state.checked && !node.state.disabled).map(node => node.id);
    this.checkedIds = Array.from(new Set(value));
  }

  skeletonComponent() {
    return (
      <div class='skeleton-wrap'>
        <div class='skeleton-element' />
        <div class='skeleton-element' />
        <div class='skeleton-element' />
      </div>
    );
  }

  treeNodeComponent() {
    return  (
      <div class='tree-node__container'>
        { this.treeNodeList.length ?
          (<bk-big-tree
            ref='tree'
            check-strictly={false}
            data={this.treeNodeList}
            default-checked-nodes={this.checkedIds}
            default-expand-all={true}
            selectable={true}
            show-checkbox={true}
            on-check-change={this.handleCheckChange}
          />) : <div class='empty'>{this.$t('暂无数据')}</div>
        }
      </div>
    )
  }

  render() {
    return (
      <div class='tree-node-shield__container'>
        {this.loading ? this.skeletonComponent() : this.treeNodeComponent()}
        <div class='component-bottom'>
          <div class='button-wrap'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={() => this.handleConfirm()}
              disabled={this.loading}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button onClick={() => this.handleCancel()}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </div>
    );
  }
}
