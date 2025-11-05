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
import { defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { Button, Tree } from 'bkui-vue';
import { getHostOrTopoNodeDetail } from 'monitor-api/modules/scene_view';
import { useI18n } from 'vue-i18n';

import type { ITopoNodeDataItem } from '../../../typings';

import './shield-tree-component.scss';

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

export default defineComponent({
  name: 'ShieldTreeComponent',
  props: {
    bizId: {
      type: [String, Number],
    },
    bkHostId: {
      type: [String, Number],
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['confirm', 'cancel'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = shallowRef(true);
    // 选中的节点树id，集群和模块之间字段名相同，id值可能重复，与后端确认使用_拼接方式：`${item.bk_inst_id}_${item.bk_obj_id}`
    const checkedIds = shallowRef([]);
    // big-tree渲染数据
    const treeNodeList = shallowRef<TreeNodeData[]>([]);
    const treeRef = useTemplateRef<InstanceType<typeof Tree>>('tree');

    /**
     * 后端节点数据转换为big-tree渲染格式
     * @param data 后端获取的节点树数据
     */
    const mapTreeData = (data: ITopoNodeDataItem[]) => {
      return data.map(item => ({
        id: `${item.bk_inst_id}_${item.bk_obj_id}`, // 集群与模块之前的id不唯一所以拼接方式
        instId: item.bk_inst_id,
        objId: item.bk_obj_id,
        name: `${item.bk_obj_name}(${item.bk_inst_name})`,
        state: {
          checked: false,
        },
        children: item.child && item.child.length > 0 ? mapTreeData(item.child) : [],
      }));
    };

    const getTopoNodeDetailData = () => {
      if (!props.bkHostId || !props.bizId) return;
      loading.value = true;
      getHostOrTopoNodeDetail({
        bk_biz_id: props.bizId,
        topo_tree: true, // 只有该接口需要查找topoNode才需要此参数
        bk_host_id: props.bkHostId, // 只有该接口需要查找topoNode才需要此参数
      })
        .then(res => {
          treeNodeList.value = mapTreeData(res);
        })
        .catch(() => {
          treeNodeList.value = [];
        })
        .finally(() => {
          loading.value = false;
        });
    };

    watch(
      () => props.show,
      show => {
        // 告警中心首页存在批量操作，每次打开需要重置数据
        checkedIds.value = [];
        treeNodeList.value = [];
        if (show) {
          getTopoNodeDetailData();
        }
      },
      {
        immediate: true,
      }
    );

    const handleConfirm = () => {
      // 将选中的id转换为后端需要的格式传递给父组件
      const findCheckedNodes = nodes => {
        let result = [];
        for (const item of nodes) {
          const fullId = `${item.instId}_${item.objId}`; // 集群与模块之前的id不唯一所以拼接方式查找
          if (checkedIds.value.includes(fullId)) {
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
      const bkTopoNode = findCheckedNodes(treeNodeList.value);
      emit('confirm', bkTopoNode);
    };

    const handleCancel = () => {
      emit('cancel');
    };

    /**
     * 更新big-tree组件节点状态
     * @param nodeIds 需要变更状态的节点
     * @param checked 目标变更的状态
     * @param childDisable 禁用子节点
     */
    const updateNodesState = async (nodeIds: string[], checked: boolean, childDisable: boolean) => {
      console.log(treeRef.value);
      const updateNodeAndChildren = (node: TreeNodeData, checked: boolean, disabled: boolean) => {
        // 如果有子节点，递归设置子节点
        if (node.children?.length) {
          treeRef.value?.setDisabled(
            node.children.map(n => n.id),
            { emitEvent: false, disabled }
          );
          treeRef.value?.setChecked(
            node.children.map(n => n.id),
            { emitEvent: false, checked }
          );
          for (const child of node.children) {
            updateNodeAndChildren(treeRef.value.getNodeById(child.id), checked, disabled);
          }
        }
      };

      for (const id of nodeIds) {
        const node: TreeNodeData = treeRef.value.getNodeById(id);
        if (!node) continue;
        treeRef.value?.setChecked(node.id, { emitEvent: false, checked });
        updateNodeAndChildren(node, checked, childDisable);
      }
    };

    // 节点checkbox事件
    const handleCheckChange = node => {
      console.log(node, treeRef.value);
      updateNodesState([node.id], node.state.checked, node.state.checked);
      const value = treeRef.value.nodes.filter(node => node.state.checked && !node.state.disabled).map(node => node.id);
      checkedIds.value = Array.from(new Set(value));
    };

    // 骨架屏
    const skeletonComponent = () => {
      return (
        <div class='skeleton-wrap'>
          <div class='skeleton-element' />
          <div class='skeleton-element' />
          <div class='skeleton-element' />
        </div>
      );
    };

    // 节点树渲染
    const treeNodeComponent = () => {
      console.log(treeNodeList.value);
      return (
        <div class='tree-node__container'>
          {treeNodeList.value.length ? (
            <Tree
              ref='tree'
              checked={checkedIds.value}
              checkStrictly={false}
              data={treeNodeList.value}
              label='name'
              selectable={true}
              show-node-type-icon={false}
              showCheckbox={true}
              expandAll
              onNodeChecked={handleCheckChange}
            />
          ) : (
            <div class='empty'>{t('暂无数据')}</div>
          )}
        </div>
      );
    };

    return {
      loading,
      skeletonComponent,
      treeNodeComponent,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <div class='tree-node-shield__container'>
        {this.loading ? this.skeletonComponent() : this.treeNodeComponent()}
        <div class='component-bottom'>
          <div class='button-wrap'>
            <Button
              class='mr-8'
              disabled={this.loading}
              theme='primary'
              onClick={this.handleConfirm}
            >
              {this.$t('确定')}
            </Button>
            <Button onClick={this.handleCancel}>{this.$t('取消')}</Button>
          </div>
        </div>
      </div>
    );
  },
});
