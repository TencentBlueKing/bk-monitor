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

import { useApplicationStore } from '@/app/state/domains/application-store';
import {
  Checkbox as TCheckbox,
  Dialog as TDialog,
  Radio as TRadio,
  RadioGroup as TRadioGroup,
  Tree as TTree,
} from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { computed, defineComponent, onMounted, ref, watch } from 'vue';

import useLocale from '@/shared/composables/use-locale';
import { overlayRegistry } from '@/shared/global/overlay/overlay-registry';

import { renderFieldListSkeleton } from '@/shared/ui/loading/list-skeleton';

import './module-select.scss';

// 使用 type 别名而非 interface，便于直接作为 TDesign Tree 的节点数据
type TopoNode = {
  id: string;
  name: string;
  children?: TopoNode[];
  bk_obj_id?: string;
  bk_inst_id?: number;
  bk_inst_name?: string;
  bk_biz_id?: number;
  disabled?: boolean;
};

type TargetNode = {
  bk_inst_id?: number;
  bk_inst_name?: string;
  bk_obj_id?: string;
  bk_biz_id?: number;
};

// TDesign Tree 字段映射：节点值取 id，展示文案取 name
const TREE_KEYS = { value: 'id', label: 'name', children: 'children' };

const nodeKey = (node: TopoNode) => String(node.id);

const toTarget = (node: TopoNode): TargetNode => ({
  bk_inst_id: node.bk_inst_id,
  bk_inst_name: node.bk_inst_name,
  bk_obj_id: node.bk_obj_id,
  bk_biz_id: node.bk_biz_id,
});

// 找到模块节点并按 bk_inst_name 去重打平
const filterModuleNodes = (nodes: TopoNode[], dict: Record<string, TopoNode> = {}) => {
  nodes.forEach(node => {
    // bk_inst_name 可能为空，统一转成字符串作为去重键，与旧版 dict[undefined] 的运行时语义保持一致
    const instName = String(node.bk_inst_name);
    if (node.bk_obj_id === 'module' && !dict[instName]) {
      dict[instName] = node;
    }
    if (node.children?.length) {
      filterModuleNodes(node.children, dict);
    }
  });
  return Object.values(dict);
};

// 父优先：父节点已选中时，子孙节点不再计入授权目标
const normalizeParentFirst = (nodes: TopoNode[], keys: Iterable<string>) => {
  const keySet = new Set(keys);
  const selectedKeys: string[] = [];
  const walk = (list: TopoNode[]) => {
    list.forEach(node => {
      if (keySet.has(nodeKey(node))) {
        selectedKeys.push(nodeKey(node));
      } else if (node.children?.length) {
        walk(node.children);
      }
    });
  };
  walk(nodes);
  return selectedKeys;
};

// 收集被父节点带出的子孙节点，这些节点只用于展示与禁用，不参与授权目标
const collectDescendantKeys = (nodes: TopoNode[], selectedKeys: Iterable<string>) => {
  const keySet = new Set(selectedKeys);
  const descendantKeys = new Set<string>();
  const walk = (list: TopoNode[], disabledByAncestor: boolean) => {
    list.forEach(node => {
      const id = nodeKey(node);
      if (disabledByAncestor) {
        descendantKeys.add(id);
      }
      if (node.children?.length) {
        walk(node.children, disabledByAncestor || keySet.has(id));
      }
    });
  };
  walk(nodes, false);
  return descendantKeys;
};

// 父节点勾选时，子孙节点同样显示为选中，保证受控 value 与禁用状态一致
const expandCheckedKeys = (nodes: TopoNode[], selectedKeys: Iterable<string>) => {
  const selected = new Set(selectedKeys);
  const checkedKeys: string[] = [];
  const walk = (list: TopoNode[], inherited: boolean) => {
    list.forEach(node => {
      const matched = inherited || selected.has(nodeKey(node));
      if (matched) {
        checkedKeys.push(nodeKey(node));
      }
      if (node.children?.length) {
        walk(node.children, matched);
      }
    });
  };
  walk(nodes, false);
  return checkedKeys;
};

// 父节点勾选后子孙节点禁用勾选，保持与旧版一致的交互
const buildDisabledTree = (nodes: TopoNode[], selected: Set<string>, disabledByAncestor = false): TopoNode[] => {
  return nodes.map(node => {
    const children = node.children?.length
      ? buildDisabledTree(node.children, selected, disabledByAncestor || selected.has(nodeKey(node)))
      : undefined;
    return {
      ...node,
      disabled: disabledByAncestor,
      children,
    };
  });
};

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
    const store = useApplicationStore();
    const { t } = useLocale();

    const isLoading = ref(true); // 加载状态
    const topoList = ref<TopoNode[]>([]); // 拓扑列表
    const moduleList = ref<TopoNode[]>([]); // 模块列表
    const topoSelectedKeys = ref<string[]>([]); // 拓扑选中的授权目标（父优先，不会包含被父节点带出的子孙）
    const topoExpandedKeys = ref<string[]>([]); // 拓扑展开节点
    const moduleSelectedKeys = ref<string[]>([]); // 模块已选节点
    const selectedTypeData = ref(props.selectedType || 'topo'); // 选中的类型
    const dialogZIndex = ref<number>(); // 弹窗层级，保证浮在侧栏之上

    // 上一次渲染中被父节点带出的子孙节点
    const disabledNodeKeys = computed(() => collectDescendantKeys(topoList.value, topoSelectedKeys.value));

    // 受控勾选值：选中的授权目标 + 其子孙
    const topoCheckedKeys = computed(() => expandCheckedKeys(topoList.value, topoSelectedKeys.value));

    // 父节点勾选后子孙禁用勾选
    const topoTreeData = computed(() => buildDisabledTree(topoList.value, new Set(topoSelectedKeys.value)));

    // 按大区选择保存的是父优先节点
    const selectedTopoList = computed(() => {
      const selected = new Set(topoSelectedKeys.value);
      const targets: TargetNode[] = [];
      const walk = (list: TopoNode[]) => {
        list.forEach(node => {
          if (selected.has(nodeKey(node))) {
            targets.push(toTarget(node));
          } else if (node.children?.length) {
            walk(node.children);
          }
        });
      };
      walk(topoList.value);
      return targets;
    });

    const moduleSelectedSet = computed(() => new Set(moduleSelectedKeys.value));

    const selectedModuleList = computed(() =>
      moduleList.value.filter(node => moduleSelectedSet.value.has(nodeKey(node))).map(toTarget));

    const isSelectAllModule = computed(
      () => moduleList.value.length > 0 && moduleSelectedKeys.value.length === moduleList.value.length,
    );

    const indeterminate = computed(
      () => moduleSelectedKeys.value.length > 0 && moduleSelectedKeys.value.length < moduleList.value.length,
    );

    // 初始化拓扑列表与已选数据
    const initTopoList = async () => {
      try {
        isLoading.value = true;
        const res = await ServicesInstance.collect.getExtractBizTopo({
          query: {
            bk_biz_id: store.bkBizId,
          },
        });
        const list: TopoNode[] = Array.isArray(res.data) ? res.data : [];
        topoList.value = list;
        moduleList.value = filterModuleNodes(list).map(node => ({ ...node, children: undefined }));

        const selectedModules = (props.selectedModules || []) as TargetNode[];
        const matchedTopoKeys: string[] = [];
        const expandKeys = new Set<string>();

        // 回填已选节点，并展开命中节点的父级链路
        const walk = (nodes: TopoNode[], ancestors: string[]) => {
          nodes.forEach(node => {
            const id = nodeKey(node);
            const matched = selectedModules.some(
              item => item.bk_obj_id === node.bk_obj_id && item.bk_inst_id === node.bk_inst_id,
            );
            if (matched) {
              matchedTopoKeys.push(id);
              ancestors.forEach(key => expandKeys.add(key));
            }
            if (node.children?.length) {
              walk(node.children, [...ancestors, id]);
            }
          });
        };
        walk(list, []);

        // 保证根节点默认展开
        if (list[0]) {
          expandKeys.add(nodeKey(list[0]));
        }

        topoSelectedKeys.value = normalizeParentFirst(list, matchedTopoKeys);
        topoExpandedKeys.value = [...expandKeys];
        moduleSelectedKeys.value = moduleList.value
          .filter(node =>
            selectedModules.some(item => item.bk_obj_id === node.bk_obj_id && item.bk_inst_id === node.bk_inst_id),
          )
          .map(nodeKey);
      } catch (e) {
        console.warn(e);
      } finally {
        isLoading.value = false;
      }
    };

    // 按大区选择：
    // Tree 以父优先模式返回勾选值，父节点勾选时会把禁用的子孙一并带出，这里过滤后归一化成授权目标
    const handleTopoChange = (value: Array<string | number>) => {
      const checkedKeys = (value || []).map(String).filter(key => !disabledNodeKeys.value.has(key));
      topoSelectedKeys.value = normalizeParentFirst(topoList.value, checkedKeys);
    };

    const handleTopoExpand = (value: Array<string | number>) => {
      topoExpandedKeys.value = (value || []).map(String);
    };

    // 按模块选择
    const handleModuleChange = (value: Array<string | number>) => {
      moduleSelectedKeys.value = (value || []).map(String);
    };

    // 全选模板节点或者取消全选
    const handleSelectAllChange = (checked: boolean) => {
      moduleSelectedKeys.value = checked ? moduleList.value.map(nodeKey) : [];
    };

    // 处理确认
    const handleConfirm = () => {
      const selectedList = selectedTypeData.value === 'topo' ? selectedTopoList.value : selectedModuleList.value;
      emit('handleConfirm', selectedTypeData.value, selectedList);
      emit('handleValueChange', false);
    };

    // 处理关闭
    const handleClose = () => {
      emit('handleValueChange', false);
    };

    watch(
      () => props.showSelectDialog,
      visible => {
        if (visible) {
          dialogZIndex.value = overlayRegistry.nextZIndex();
        }
      },
      { immediate: true },
    );

    // 组件挂载时初始化
    onMounted(() => {
      initTopoList();
    });

    // 主渲染函数
    return () => (
      <TDialog
        attach='body'
        width={680}
        visible={props.showSelectDialog}
        header={false}
        closeBtn={false}
        closeOnOverlayClick={false}
        zIndex={dialogZIndex.value}
        confirmBtn={{ content: t('确定'), disabled: isLoading.value }}
        cancelBtn={t('取消')}
        onConfirm={handleConfirm}
        onCancel={handleClose}
        onClose={handleClose}
        v-slots={{
          default: () => (
            <div class='module-select-container'>
              <TRadioGroup
                style='margin-bottom: 20px'
                value={selectedTypeData.value}
                onChange={(value: any) => {
                  selectedTypeData.value = String(value);
                }}
              >
                <TRadio
                  style='margin-right: 16px'
                  value='topo'
                >
                  {t('按大区选择')}
                </TRadio>
                <TRadio value='module'>{t('按模块选择')}</TRadio>
              </TRadioGroup>

              {/* 按大区选择 */}
              <div
                class='tree-container'
                v-loading={{ loading: isLoading.value, indicator: renderFieldListSkeleton }}
                v-show={selectedTypeData.value === 'topo'}
              >
                <TTree
                  data={topoTreeData.value}
                  keys={TREE_KEYS}
                  hover
                  checkable
                  valueMode='parentFirst'
                  checkStrictly={false}
                  transition={false}
                  value={topoCheckedKeys.value}
                  expanded={topoExpandedKeys.value}
                  onChange={handleTopoChange}
                  onExpand={handleTopoExpand}
                />
              </div>

              {/* 按模块选择 */}
              <div
                class='tree-container'
                v-loading={{ loading: isLoading.value, indicator: renderFieldListSkeleton }}
                v-show={selectedTypeData.value === 'module'}
              >
                <div class='checkbox-container'>
                  <TCheckbox
                    checked={isSelectAllModule.value}
                    indeterminate={indeterminate.value}
                    onChange={handleSelectAllChange}
                  >
                    {t('全选')}
                  </TCheckbox>
                </div>
                <TTree
                  data={moduleList.value}
                  keys={TREE_KEYS}
                  hover
                  checkable
                  transition={false}
                  value={moduleSelectedKeys.value}
                  onChange={handleModuleChange}
                />
              </div>
            </div>
          ),
        }}
      />
    );
  },
});
