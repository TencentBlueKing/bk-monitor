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

import { defineComponent, ref, onMounted, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import http from '@/api';

import './module-select.scss';

export default defineComponent({
  name: 'ModuleSelect',
  props: {
    // 是否显示选择对话框
    showSelectDialog: {
      type: Boolean,
      default: false,
    },
    // 选择类型
    selectedType: {
      type: String,
      default: 'topo',
    },
    // 已选中的模块
    selectedModules: {
      type: Array,
      default: () => [],
    },
    onHandleConfirm: { type: Function },
    onHandleValueChange: { type: Function },
  },
  emits: ['handleConfirm', 'handleValueChange'],

  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();

    const isLoading = ref(true); // 加载状态
    const topoList = ref<any[]>([]); // 拓扑列表
    const topoCheckedNodes = ref<string[]>([]); // 拓扑已选中节点
    const topoExpandNodes = ref<string[]>([]); // 拓扑展开节点
    const moduleList = ref<any[]>([]); // 模块列表
    const moduleCheckedNodes = ref<string[]>([]); // 模块已选中节点
    const selectedTypeData = ref(props.selectedType); // 选中的类型
    const selectedTopoList = ref<any[]>(props.selectedModules); // 选中的拓扑列表
    const selectedModuleList = ref<any[]>([]); // 选中的模块列表
    const isSelectAllModule = ref(false); // 是否全选模块
    const indeterminate = ref(false); // 是否半选

    // 树组件引用
    const topoTreeRef = ref<any>(null);
    const moduleTreeRef = ref<any>(null);

    // 初始化拓扑列表
    const initTopoList = async () => {
      try {
        isLoading.value = true;
        const res = await http.request('collect/getExtractBizTopo', {
          query: {
            bk_biz_id: store.state.bkBizId,
          },
        });
        topoList.value = res.data;
        moduleList.value = filterList(res.data);

        // 数据回填
        const {
          topoExpandNodes: expandNodes,
          topoCheckedNodes: checkedNodes,
          moduleCheckedItems,
        } = recursiveFindDefault(res.data, null, props.selectedModules);

        // 回填已选择的模块
        selectedModuleList.value = moduleCheckedItems.map((item: any) => ({
          bk_inst_id: item.bk_inst_id,
          bk_inst_name: item.bk_inst_name,
          bk_obj_id: item.bk_obj_id,
          bk_biz_id: item.bk_biz_id,
        }));
        moduleCheckedNodes.value = moduleCheckedItems.map((item: any) => item.id);

        if (moduleCheckedNodes.value.length === moduleList.value.length) {
          isSelectAllModule.value = true;
        } else if (moduleCheckedNodes.value.length !== 0) {
          indeterminate.value = true;
        }

        // 保证根节点默认展开
        const rootId = res.data[0]?.id;
        if (rootId && !expandNodes.includes(rootId)) {
          expandNodes.push(rootId);
        }

        // 回填已选择的大区
        topoExpandNodes.value = expandNodes;
        topoCheckedNodes.value = checkedNodes;

        if (checkedNodes.length) {
          // 父亲勾选后子孙禁用勾选
          await nextTick();
          const rootNode = topoTreeRef.value?.nodes[0];
          if (rootNode?.children?.length) {
            recursiveDealCheckedNode(rootNode.children, rootNode.checked);
          }
        }
      } catch (e) {
        console.warn(e);
      } finally {
        isLoading.value = false;
      }
    };

    // 初始化处理默认勾选节点，父亲勾选后子孙禁用勾选
    const recursiveDealCheckedNode = (nodes: any[], bool: boolean) => {
      if (bool) {
        inheritCheckNode(nodes, bool);
      } else {
        nodes.forEach((node: any) => {
          if (node?.children?.length) {
            recursiveDealCheckedNode(node.children, node.checked);
          }
        });
      }
    };

    // 找到模板节点并打平去重
    const filterList = (list: any[], dict: any = {}) => {
      list.forEach((item: any) => {
        if (item.bk_obj_id === 'module' && !dict[item.bk_inst_name]) {
          dict[item.bk_inst_name] = item;
        }
        if (item.children?.length) {
          filterList(item.children, dict);
        }
      });
      return Object.values(dict);
    };

    // 递归查找默认选中节点
    const recursiveFindDefault = (
      treeNodes: any[],
      parentNode: any,
      selectedNodes: any[],
      topoCheckedNodes: string[] = [],
      topoExpandNodes: string[] = [],
      moduleCheckedMap: any = {},
    ) => {
      treeNodes.forEach((treeNode: any) => {
        treeNode.parentNode = parentNode || null;

        for (const selectedNode of selectedNodes) {
          if (selectedNode.bk_obj_id === treeNode.bk_obj_id && selectedNode.bk_inst_id === treeNode.bk_inst_id) {
            topoCheckedNodes.push(treeNode.id);
            if (treeNode.bk_obj_id === 'module' && !moduleCheckedMap[treeNode.bk_inst_name]) {
              moduleCheckedMap[treeNode.bk_inst_name] = treeNode;
            }
            if (parentNode) {
              topoExpandNodes.push(parentNode.id);
            }
            break;
          }
        }

        if (treeNode.children?.length) {
          recursiveFindDefault(
            treeNode.children,
            treeNode,
            selectedNodes,
            topoCheckedNodes,
            topoExpandNodes,
            moduleCheckedMap,
          );
        }
      });

      return {
        topoCheckedNodes,
        topoExpandNodes: [...new Set(topoExpandNodes)],
        moduleCheckedItems: Object.values(moduleCheckedMap),
      };
    };

    // 按大区选择
    const handleTopoNodeCheck = (checkedId: string, checkedNode: any) => {
      checkedNode?.children?.length && inheritCheckNode(checkedNode.children, checkedNode.state.checked);
      selectedTopoList.value = recursiveFindTopoNodes(topoTreeRef.value.nodes[0]);
    };

    // 父亲勾选或取消勾选后，子孙跟随状态变化，且父亲勾选后子孙禁用勾选
    const inheritCheckNode = (nodes: any[], bool: boolean) => {
      nodes.forEach((node: any) => {
        node.checked = bool;
        node.disabled = bool;
        node.children?.length && inheritCheckNode(node.children, bool);
      });
    };

    // 遍历树找到勾选的节点，如果父节点已勾选，子孙节点不算在列表内
    const recursiveFindTopoNodes = (node: any, selectedTopoList: any[] = []) => {
      if (node.checked) {
        const { data } = node;
        selectedTopoList.push({
          bk_inst_id: data.bk_inst_id,
          bk_inst_name: data.bk_inst_name,
          bk_obj_id: data.bk_obj_id,
          bk_biz_id: data.bk_biz_id,
        });
      } else if (node.children?.length) {
        node.children.forEach((child: any) => {
          recursiveFindTopoNodes(child, selectedTopoList);
        });
      }
      return selectedTopoList;
    };

    // 按模板选择
    const handleModuleNodeCheck = (checkedId: string[], checkedNode: any) => {
      const { nodes, checkedNodes } = checkedNode.tree;
      if (checkedId.length) {
        if (checkedId.length === nodes.length) {
          isSelectAllModule.value = true;
          indeterminate.value = false;
        } else {
          isSelectAllModule.value = false;
          indeterminate.value = true;
        }
      } else {
        isSelectAllModule.value = false;
        indeterminate.value = false;
      }
      selectedModuleList.value = checkedNodes.map((node: any) => {
        const { data } = node;
        return {
          bk_inst_id: data.bk_inst_id,
          bk_inst_name: data.bk_inst_name,
          bk_obj_id: data.bk_obj_id,
          bk_biz_id: data.bk_biz_id,
        };
      });
    };

    // 全选模板节点或者取消全选
    const handleSelectAllChange = (val: boolean) => {
      const { nodes } = moduleTreeRef.value;
      if (val) {
        indeterminate.value = false;
        isSelectAllModule.value = true;
        nodes.forEach((node: any) => {
          node.checked = true;
        });
        selectedModuleList.value = nodes.map((node: any) => {
          const { data } = node;
          return {
            bk_inst_id: data.bk_inst_id,
            bk_inst_name: data.bk_inst_name,
            bk_obj_id: data.bk_obj_id,
            bk_biz_id: data.bk_biz_id,
          };
        });
      } else {
        indeterminate.value = false;
        isSelectAllModule.value = false;
        nodes.forEach((node: any) => {
          node.checked = false;
        });
        selectedModuleList.value = [];
      }
    };

    // 处理对话框值变化
    const handleValueChange = (val: boolean) => {
      emit('handleValueChange', val);
    };

    // 处理确认
    const handleConfirm = () => {
      const selectedList = selectedTypeData.value === 'topo' ? selectedTopoList.value : selectedModuleList.value;
      emit('handleConfirm', selectedTypeData.value, selectedList);
    };

    // 组件挂载时初始化
    onMounted(() => {
      initTopoList();
    });

    // 主渲染函数
    return () => (
      <bk-dialog
        width={680}
        closeIcon={false}
        confirmFn={handleConfirm}
        maskClose={false}
        value={props.showSelectDialog}
        on-value-change={handleValueChange}
      >
        <div
          class='module-select-container'
          v-bkloading={{ isLoading: isLoading.value }}
        >
          <bk-radio-group
            style='margin-bottom: 20px'
            value={selectedTypeData.value}
            onChange={(val: string) => (selectedTypeData.value = val)}
          >
            <bk-radio
              style='margin-right: 16px'
              value='topo'
            >
              {t('按大区选择')}
            </bk-radio>
            <bk-radio value='module'>{t('按模块选择')}</bk-radio>
          </bk-radio-group>

          {/* 按大区选择 */}
          <div
            class='tree-container'
            v-show={selectedTypeData.value === 'topo'}
          >
            <bk-big-tree
              ref={topoTreeRef}
              checkStrictly={false}
              data={topoList.value}
              defaultCheckedNodes={topoCheckedNodes.value}
              defaultExpandedNodes={topoExpandNodes.value}
              showCheckbox
              on-check-change={handleTopoNodeCheck}
            />
          </div>

          {/* 按模块选择 */}
          <div
            class='tree-container'
            v-show={selectedTypeData.value === 'module'}
          >
            <div class='checkbox-container'>
              <bk-checkbox
                indeterminate={indeterminate.value}
                value={isSelectAllModule.value}
                onChange={val => {
                  isSelectAllModule.value = val;
                  handleSelectAllChange(val);
                }}
              >
                {t('全选')}
              </bk-checkbox>
            </div>
            <bk-big-tree
              ref={moduleTreeRef}
              data={moduleList.value}
              defaultCheckedNodes={moduleCheckedNodes.value}
              showCheckbox
              on-check-change={handleModuleNodeCheck}
            />
          </div>
        </div>
      </bk-dialog>
    );
  },
});
