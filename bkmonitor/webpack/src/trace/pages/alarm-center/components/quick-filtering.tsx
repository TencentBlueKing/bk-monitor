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

import { type PropType, computed, ref as deepRef, defineComponent, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Loading } from 'bkui-vue';
import { type TreeNodeValue, Tree } from 'tdesign-vue-next';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '@/components/empty-status/empty-status';

import type { CommonCondition, QuickFilterItem } from '../typings';

import './quick-filtering.scss';

export default defineComponent({
  name: 'QuickFiltering',
  props: {
    filterList: {
      type: Array as PropType<QuickFilterItem[]>,
      default: () => [],
    },
    filterValue: {
      type: Array as PropType<CommonCondition[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    isFirstInit: {
      type: Boolean,
      default: true,
    },
    /** 是否过滤空项 */
    isFilterEmptyItem: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['close', 'update:filterValue'],
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 最后一次操作的分类 */
    const lastOperationCategory = shallowRef('');

    /** 缓存数据 */
    const localValue = deepRef<Record<string, TreeNodeValue[]>>({});

    watch(
      () => props.filterValue,
      value => {
        if (value?.length) {
          localValue.value = value.reduce((acc, cur) => {
            acc[cur.key] = cur.value;
            return acc;
          }, {});
        } else {
          localValue.value = {};
        }
      },
      { immediate: true }
    );

    const showFilterList = computed(() => {
      return props.isFilterEmptyItem ? filterEmptyItem(JSON.parse(JSON.stringify(props.filterList))) : props.filterList;
    });

    const selectIds = computed(() => {
      return Object.values(localValue.value).flat(Infinity);
    });

    /** 过滤空选项 */
    const filterEmptyItem = (items: QuickFilterItem[]) => {
      if (!Array.isArray(items)) return [];
      return items.filter(item => {
        // 递归处理子项
        if (item.children?.length) {
          item.children = filterEmptyItem(item.children);
        }

        // 判断是否保留当前项：
        // 1. 如果当前项count为0 -> 移除
        // 2. 如果当前项有子项但全部被清空 -> 移除
        // 3. 其他情况保留（有有效count或非空子项）
        const hasChildren = item.children?.length > 0;
        const hasContent = item.count > 0 || hasChildren || selectIds.value.includes(item.id);
        return hasContent;
      });
    };

    const handleClearFilter = (item: QuickFilterItem) => {
      lastOperationCategory.value = '';
      localValue.value[item.id] = [];
      emitFilterValue();
    };

    const handleNodeChecked = (filterGroupId: string, ids: TreeNodeValue[]) => {
      lastOperationCategory.value = ids.length ? filterGroupId : '';
      localValue.value[filterGroupId] = ids;
      emitFilterValue();
    };

    /** 选择条件增加防抖，优化交互体验 */
    const emitFilterValue = useDebounceFn(() => {
      const list = Object.entries(localValue.value).reduce((pre, cur, index) => {
        const [key, value] = cur;
        if (value?.length) {
          if (index > 0) {
            pre.push({
              key,
              value,
              condition: 'and',
            });
          } else {
            pre.push({
              key,
              value,
            });
          }
        }
        return pre;
      }, []);

      emit('update:filterValue', list, lastOperationCategory.value);
    }, 300);

    const renderIcon = (data: QuickFilterItem) => {
      if (!data.icon) return undefined;

      if (data.icon === 'rect') {
        return (
          <div
            style={{ backgroundColor: data.iconColor || '#8E9BB3' }}
            class='item-rect'
          />
        );
      }
      return (
        <i
          style={{ color: data.iconColor || '#8E9BB3' }}
          class={['icon-monitor', 'item-icon', data.icon]}
        />
      );
    };

    const renderFilterTree = (filterGroup: QuickFilterItem) => {
      return (
        <Tree
          class={{ 'no-multi-level': !filterGroup.children.some(child => child.children?.length) }}
          checkable={true}
          data={filterGroup.children}
          expandAll={true}
          expandOnClickNode={true}
          hover={false}
          keys={{ value: 'id', label: 'name', children: 'children' }}
          transition={false}
          value={localValue.value[filterGroup.id] || []}
          onChange={id => handleNodeChecked(filterGroup.id, id)}
        >
          {{
            icon: ({ node }) => {
              return node.isLeaf() ? undefined : <i class='icon-monitor icon-mc-arrow-right' />;
            },
            label: ({ node }) => (
              <div class={['condition-tree-item', node.data?.extCls]}>
                <div class='item-icon-wrapper'>{renderIcon(node.data)}</div>
                <span
                  style={{
                    color: node.data.textColor || '#313238',
                  }}
                  class='item-name'
                  v-overflow-tips
                >
                  {node.data.name}
                </span>
                <span class='item-count'>{node.data.count}</span>
              </div>
            ),
          }}
        </Tree>
      );
    };

    const handleClose = () => {
      emit('close', true);
    };

    return {
      t,
      handleClose,
      renderFilterTree,
      showFilterList,
      localValue,
      selectIds,
      handleClearFilter,
    };
  },
  render() {
    return (
      <div class='quick-filtering-comp'>
        <div class='quick-filtering-header'>
          <i
            class='icon-monitor icon-gongneng-shouqi'
            v-bk-tooltips={{ content: this.t('收起') }}
            onClick={this.handleClose}
          />
          <div class='title'>{this.t('快捷筛选')}</div>
          <Loading
            class='loading-wrap'
            loading={this.loading && !this.isFirstInit}
            size='small'
          >
            <div />
          </Loading>
        </div>
        {this.loading && this.isFirstInit ? (
          <div class='skeleton-wrap'>
            {new Array(5).fill(0).map((_, index) => (
              <div
                key={index}
                class='skeleton-group'
              >
                <div class='skeleton-element title' />
                <div class='skeleton-element item' />
                <div class='skeleton-element item' />
                <div class='skeleton-element item' />
              </div>
            ))}
          </div>
        ) : (
          <div class='filter-list'>
            {!this.showFilterList.length &&
              (this.$slots.empty?.() || (
                <EmptyStatus
                  showOperation={false}
                  textMap={{ 'search-empty': this.t('暂无数据') }}
                  type='search-empty'
                />
              ))}
            {this.showFilterList.map(item => (
              <div
                key={item.id}
                class='filter-item'
              >
                <div class='filter-group-header'>
                  <div class='filter-group-title'>{item.name}</div>
                  <i
                    class='icon-monitor icon-a-Clearqingkong'
                    onClick={() => this.handleClearFilter(item)}
                  />
                </div>
                <div class='filter-group-children'>{this.renderFilterTree(item)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  },
});
