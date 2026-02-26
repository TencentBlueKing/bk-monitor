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

import { defineComponent, ref, onUnmounted, watch, computed, type PropType } from 'vue';

import { random } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import TreeComponent from '../../../common-comp/tree-component';
import type { IClusterItem, IValueItem } from '../../../../type';
import $http from '@/api';

import './label-choose-dialog.scss';

type ITreeItem = {
  id: string;
  name: string;
  type: string;
  children?: ITreeItem[];
  isOpen?: boolean;
};

export default defineComponent({
  name: 'LabelChooseDialog',

  props: {
    isShowDialog: {
      type: Boolean,
      default: false,
    },
    labelParams: {
      type: Object as PropType<IValueItem>,
      default: () => ({}),
    },
    clusterList: {
      type: Array as PropType<IClusterItem[]>,
      required: true,
    },
  },

  emits: ['cancel', 'change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const treeList = ref<ITreeItem[]>([]);
    const filterStr = ref('');
    const matchCheckedList = ref<string[]>([]);
    const matchCheckedItemList = ref<IValueItem[]>([]);
    const matchSelectList = ref<string[]>([]);
    const matchSelectItemList = ref<IValueItem[]>([]);
    const treeLoading = ref(false);
    const labelLoading = ref(false);
    /**
     * 容器宽度状态
     */
    const DEFAULT_LEFT_WIDTH = 400;
    const MIN_LEFT_WIDTH = 200;
    const MAX_LEFT_WIDTH = 800;
    const leftWidth = ref(DEFAULT_LEFT_WIDTH);
    const isDragging = ref(false);
    const startX = ref(0);
    const startLeftWidth = ref(0);
    const currentNodeId = ref('');

    // 预构建集群映射，避免在每次初始化树时重复查找
    const clusterIdToName = computed<Record<string, string>>(() => {
      const map: Record<string, string> = {};
      for (const c of props.clusterList || []) {
        map[c.id] = c.name;
      }
      return map;
    });

    /**
     * 关闭新增索引弹窗
     */
    const handleCancel = () => {
      emit('cancel', false);
    };

    /**
     * 规范化输入数据为数组格式
     * @param rawData 原始数据，可能是数组或单个对象
     * @returns 规范化后的数组
     */
    const normalizeTreeData = (rawData: ITreeItem[]): ITreeItem[] => {
      if (Array.isArray(rawData)) {
        return rawData as ITreeItem[];
      }
      if (rawData && typeof rawData === 'object') {
        return [rawData as ITreeItem];
      }
      return [];
    };

    /**
     * 初始化树列表，处理集群名称显示
     * @param list 树节点列表
     * @returns 处理后的树节点列表
     */
    const initTreeList = (list: ITreeItem[] = []): ITreeItem[] =>
      list.map(item => {
        if (item.type === 'cluster' && Object.hasOwn(clusterIdToName.value, item.id)) {
          const clusterName = clusterIdToName.value[item.id];
          return { ...item, name: `${clusterName} (${item.id})` };
        }
        return item;
      });

    /**
     * 递归设置树节点的 isOpen 状态为 true
     * @param nodes 树节点列表
     * @returns 处理后的树节点列表
     */
    const setTreeNodesOpen = (nodes: ITreeItem[]): ITreeItem[] =>
      nodes.map(node => ({
        ...node,
        isOpen: true,
        children: Array.isArray(node.children) ? setTreeNodesOpen(node.children) : node.children,
      }));

    /**
     * 自动选择第一个可用的 pod/node 节点
     * @param nodes 树节点列表
     */
    const autoSelectFirstAvailableNode = (nodes: ITreeItem[]) => {
      if (!nodes.length) {
        return;
      }

      const firstNode = nodes[0];
      const firstChild = firstNode.children?.[0];
      const firstGrandChild = firstChild?.children?.[0];

      // 检查是否存在三层嵌套结构，且最深层节点存在
      if (firstGrandChild) {
        currentNodeId.value = firstGrandChild.id;
        handleSelectTreeItem(firstGrandChild, firstChild);
      }
    };

    /**
     * 处理树数据：规范化、初始化、设置展开状态、自动选择节点
     * @param rawData 原始树数据
     */
    const processTreeData = (rawData: ITreeItem[]) => {
      // 1. 规范化数据格式
      const normalizedData = normalizeTreeData(rawData);

      // 2. 初始化树列表（处理集群名称等）
      const initializedData = initTreeList(normalizedData);

      // 3. 设置所有节点为展开状态（合并到一次遍历中）
      const treeListData = setTreeNodesOpen(initializedData);

      // 4. 更新树列表
      treeList.value = treeListData;

      // 5. 自动选择第一个可用节点
      autoSelectFirstAvailableNode(treeListData);
    };
    /**
     * 根据请求类型获取树列表
     */
    const getTreeList = () => {
      const { bk_biz_id, bcs_cluster_id, type, namespaceStr } = props.labelParams;
      const baseQuery = { bcs_cluster_id, type, bk_biz_id };
      const query = type === 'node' ? baseQuery : { ...baseQuery, namespace: namespaceStr };

      treeLoading.value = true;
      $http
        .request('container/getPodTree', { query })
        .then(res => {
          processTreeData(res.data);
        })
        .catch(err => {
          console.warn(err);
        })
        .finally(() => {
          treeLoading.value = false;
        });
    };

    /**
     * 开始拖拽
     */
    const handleMouseDown = (e: MouseEvent) => {
      isDragging.value = true;
      startX.value = e.clientX;
      startLeftWidth.value = leftWidth.value;

      /**
       * 添加全局拖拽状态
       */
      document.body.classList.add('dragging-resize');

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      e.preventDefault();
    };

    /**
     * 拖拽过程中
     */
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.value) {
        return;
      }

      const deltaX = e.clientX - startX.value;
      const newLeftWidth = startLeftWidth.value + deltaX;

      // 限制最小和最大宽度
      if (newLeftWidth >= MIN_LEFT_WIDTH && newLeftWidth <= MAX_LEFT_WIDTH) {
        leftWidth.value = newLeftWidth;
      }
    };

    /**
     * 结束拖拽
     */
    const handleMouseUp = () => {
      isDragging.value = false;

      // 移除全局拖拽状态
      document.body.classList.remove('dragging-resize');

      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    // 清理事件监听器
    onUnmounted(() => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('dragging-resize');
    });

    const resetSelect = () => {
      matchSelectList.value = [];
      matchSelectItemList.value = [];
      matchCheckedList.value = [];
      matchCheckedItemList.value = [];
    };

    /**
     * 基于关键字过滤树节点，命中节点或其后代命中即保留
     */
    const filterTreeByKeyword = (nodes: ITreeItem[], keyword: string): ITreeItem[] => {
      if (!(Array.isArray(nodes) && nodes.length)) {
        return [];
      }
      const k = keyword.trim().toLowerCase();
      if (!k) {
        return nodes;
      }

      const loop = (list: ITreeItem[]): ITreeItem[] =>
        list
          .map((node: ITreeItem) => {
            const nameHit = (node.name || '').toLowerCase().includes(k);
            const children = Array.isArray(node.children) ? loop(node.children) : [];
            if (nameHit || children.length) {
              return {
                ...node,
                isOpen: true,
                children,
              };
            }
            return null;
          })
          .filter(Boolean) as ITreeItem[];

      return loop(nodes);
    };

    const filteredTreeList = computed<ITreeItem[]>(() => filterTreeByKeyword(treeList.value, filterStr.value));

    /**
     * 同步树节点展开状态：根据子组件返回的 node 与 level，更新 treeList 对应节点的 isOpen
     */
    const handleToggleTreeNode = (toggledNode: ITreeItem, _level: number) => {
      const syncOpen = (list: ITreeItem[]): ITreeItem[] =>
        list.map(item => {
          const isTarget = item.id === toggledNode.id;
          const children = Array.isArray(item.children) ? syncOpen(item.children) : item.children;
          return {
            ...item,
            isOpen: isTarget ? !!toggledNode.isOpen : item.isOpen,
            children,
          };
        });

      treeList.value = syncOpen(treeList.value);
    };

    watch(
      () => props.isShowDialog,
      (val: boolean) => {
        if (val) {
          treeList.value = [];
          getTreeList();

          /**
           * 初始化已选择列表为空，等待用户选择
           */
          matchCheckedItemList.value = [];
          matchCheckedList.value = [];
        } else {
          resetSelect();
          filterStr.value = '';
        }
      },
    );

    /**
     * 判断两个标签是否等价（用于去重）
     * @param a
     * @param b
     *@returns
     */
    const isSameLabel = (a: IValueItem, b: IValueItem) =>
      a.key === b.key && a.value === b.value && a.operator === b.operator;

    /**
     * 选择树节点时：
     * - 非 pod/node 节点：清空未选择区域
     * - pod/node 节点：请求该节点的可选标签，过滤掉与"已选择"重复的项
     * - 已选择区域始终保持不变
     */
    const handleSelectTreeItem = (treeItem, parent) => {
      currentNodeId.value = treeItem.id;

      /**
       * 非 pod/node 节点时，清空未选择区域
       */
      if (!['pod', 'node'].includes(treeItem.type)) {
        matchSelectItemList.value = [];
        return;
      }

      const { bk_biz_id, bcs_cluster_id, type } = props.labelParams;
      const query: Record<string, unknown> = {
        name: treeItem.name,
        bcs_cluster_id,
        type,
        bk_biz_id,
        ...(type !== 'node' ? { namespace: parent.name } : {}),
      };

      /**
       * 请求该节点的可选标签
       */
      labelLoading.value = true;

      $http
        .request('container/getNodeLabelList', { query })
        .then(res => {
          if (res.code !== 0) {
            return;
          }

          /**
           * 过滤掉与已选择列表重复的项，确保不重复
           */
          const allCheckedItemList: IValueItem[] = [...matchCheckedItemList.value];

          matchSelectItemList.value = res.data
            .filter((item: IValueItem) => {
              if (!allCheckedItemList.length) {
                return true;
              }
              const normalized: IValueItem = { ...item, operator: 'In' };
              return !allCheckedItemList.some(mItem => {
                const normalizedMItem: IValueItem = { ...mItem, operator: 'In' };
                return isSameLabel(normalized, normalizedMItem);
              });
            })
            // 统一为可选择项补齐 operator 与临时 id
            .map((item: IValueItem) => ({ ...item, operator: 'In', id: random(10) }));
        })
        .catch(err => {
          console.warn(err);
        })
        .finally(() => {
          labelLoading.value = false;
        });
    };

    /**
     * 处理checkbox勾选/反选事件
     * @param vals 当前勾选的id列表
     * @param isSelectedArea 是否为已选择区域
     */
    const handleCheckboxChange = (vals: string[], isSelectedArea: boolean) => {
      if (isSelectedArea) {
        /**
         * 已选择区域：反选时从已选择列表中删除
         */
        const allSelectedIds = matchCheckedItemList.value.map(item => item.id);
        const removedIds = allSelectedIds.filter(id => !vals.includes(id));

        /**
         * 先获取被反选的项（在删除前获取）
         */
        const removedItems = matchCheckedItemList.value.filter(item => removedIds.includes(item.id));

        /**
         * 从已选择列表中移除被反选的项
         */
        matchCheckedItemList.value = matchCheckedItemList.value.filter(item => !removedIds.includes(item.id));
        /**
         * 检查未选择区域是否已存在相同项，避免重复
         */
        if (removedItems.length > 0) {
          const newUnselectedItems = removedItems.filter(
            removedItem => !matchSelectItemList.value.some(existingItem => isSameLabel(removedItem, existingItem)),
          );
          matchSelectItemList.value = [...matchSelectItemList.value, ...newUnselectedItems];
        }
      } else {
        /**
         * 未选择区域：勾选时添加到已选择列表
         */
        const newCheckedItems = matchSelectItemList.value.filter(item => vals.includes(item.id));

        /**
         * 检查是否重复，避免添加重复项
         */
        const uniqueNewItems = newCheckedItems.filter(
          newItem => !matchCheckedItemList.value.some(existingItem => isSameLabel(newItem, existingItem)),
        );

        matchCheckedItemList.value = [...matchCheckedItemList.value, ...uniqueNewItems];

        /**
         * 从未选择区域移除已勾选的项
         */
        matchSelectItemList.value = matchSelectItemList.value.filter(item => !vals.includes(item.id));
      }
    };

    const renderMatchSelectItem = (data: IValueItem[], isSelectedArea = false) => {
      /**
       * 已选择区域显示所有已选择的项，未选择区域显示当前节点的可选项
       */
      const currentCheckedIds = isSelectedArea ? data.map(item => item.id) : [];

      return (
        <bk-checkbox-group
          value={currentCheckedIds}
          on-change={vals => handleCheckboxChange(vals, isSelectedArea)}
        >
          {data.map(item => {
            const value = item?.id ?? `${item.key}|${item.operator}|${item.value ?? '-'}`;
            return (
              <bk-checkbox
                key={value}
                class='selected-item'
                label={value}
              >
                <div class='item-slot'>
                  <span class='key'>{item.key}</span>
                  <span class='operator'>{item.operator}</span>
                  <span class='value'>{item.value || '-'}</span>
                </div>
              </bk-checkbox>
            );
          })}
        </bk-checkbox-group>
      );
    };
    /**
     * 确认选择
     */
    const handleConfirm = () => {
      emit('change', matchCheckedItemList.value);
      handleCancel();
    };
    /**
     * 渲染无数据提示
     * @returns
     */
    const renderEmpty = () => (
      <bk-exception
        class='no-selected-item'
        scene='part'
        type='empty'
      >
        {t('暂无标签')}
      </bk-exception>
    );
    return () => (
      <bk-dialog
        width={1060}
        ext-cls='label-choose-dialog-main'
        headerPosition={'left'}
        mask-close={false}
        theme='primary'
        title={t('选择标签')}
        value={props.isShowDialog}
        on-cancel={handleCancel}
        on-confirm={handleConfirm}
      >
        <div class='resizable-container'>
          <div
            style={{ width: `${leftWidth.value}px` }}
            class='main-left'
          >
            <bk-input
              class='tree-search'
              right-icon='bk-icon icon-search'
              value={filterStr.value}
              clearable
              on-input={(val: string) => {
                filterStr.value = (val || '').toString();
              }}
            />
            <div
              class='tree-list'
              v-bkloading={{ isLoading: treeLoading.value }}
            >
              {filteredTreeList.value.length > 0 ? (
                <TreeComponent
                  activeNodeId={currentNodeId.value}
                  data={filteredTreeList.value}
                  on-click-node={handleSelectTreeItem}
                  on-toggle={handleToggleTreeNode}
                />
              ) : (
                <bk-exception
                  class='tree-list-empty'
                  type={filterStr.value ? 'search-empty' : 'empty'}
                >
                  {filterStr.value && <span>{t('搜索结果为空')}</span>}
                  <span
                    class='list-main-empty-text'
                    on-click={() => {
                      filterStr.value = '';
                    }}
                  >
                    {t('清空筛选条件')}
                  </span>
                </bk-exception>
              )}
            </div>
          </div>

          <div
            class='resize-handle'
            onMousedown={handleMouseDown}
          >
            <div class='resize-dots'>
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  class='dot'
                />
              ))}
            </div>
          </div>

          <div class='main-right'>
            <div class='main-right-top'>
              {t('已选择')}
              {matchCheckedItemList.value.length > 0
                ? renderMatchSelectItem(matchCheckedItemList.value, true)
                : renderEmpty()}
            </div>
            <div
              class='main-right-bot'
              v-bkloading={{ isLoading: labelLoading.value }}
            >
              {t('未选择')}
              {matchSelectItemList.value.length > 0
                ? renderMatchSelectItem(matchSelectItemList.value, false)
                : renderEmpty()}
            </div>
          </div>
        </div>
      </bk-dialog>
    );
  },
});
