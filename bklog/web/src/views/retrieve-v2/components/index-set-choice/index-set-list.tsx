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

import { computed, defineComponent, onBeforeUnmount, type PropType, ref, set } from 'vue';

import useLocale from '@/hooks/use-locale';
import { debounce } from 'lodash-es';

import * as authorityMap from '../../../../common/authority-map';
import BklogPopover from '../../../../components/bklog-popover';
import type { IndexSetItem } from './use-choice';
import useIndexSetList from './use-index-set-list';

import './index-set-list.scss';

const SEARCH_KEYS = ['index_set_name', 'index_set_id', 'bk_biz_id', 'collector_config_id'] as const;
const NO_DATA_TAG_ID = 4;

export default defineComponent({
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String,
      default: 'single',
    },
    value: {
      type: Array as PropType<IndexSetItem[]>,
      default: () => [],
    },
    textDir: {
      type: String,
      default: 'ltr',
    },
    spaceUid: {
      type: String,
      default: '',
    },
  },
  emits: ['value-change', 'favorite-change', 'auth-request'],
  setup(props, { emit }) {
    const { indexSetTagList, clearAllValue, handleIndexSetItemCheck } = useIndexSetList(props, { emit });

    const { $t } = useLocale();

    const hiddenEmptyItem = ref(true);
    /** 输入框即时值 */
    const searchText = ref('');
    /** 参与过滤计算的关键字（防抖后更新，减少高频重算） */
    const searchKeyword = ref('');
    const refFavoriteItemName = ref(null);
    const refFavoriteGroup = ref(null);
    const favoriteFormData = ref({
      name: '',
    });

    const isMonitorComponent = window.__IS_MONITOR_COMPONENT__;

    const listNodeOpenManager = ref({});
    const disableList = ref([]);

    const tagItem = ref({
      tag_id: undefined,
      name: undefined,
      color: undefined,
    });

    const selectedUniqueIdSet = computed(() => new Set((props.value ?? []).map(v => v.unique_id)));

    const isIncludesItem = (item: IndexSetItem) => selectedUniqueIdSet.value.has(item.unique_id);

    const hasNoDataTag = (node: { tags?: { tag_id: number }[] }) =>
      node.tags?.some(tag => tag.tag_id === NO_DATA_TAG_ID) ?? false;

    const matchSearchKeyword = (node: IndexSetItem, keyword: string) => {
      if (SEARCH_KEYS.some(key => `${node[key] ?? ''}`.toLowerCase().includes(keyword))) {
        return true;
      }
      const indices = (node as IndexSetItem & { indices?: { result_table_id?: string }[] }).indices ?? [];
      return indices.some(idc => `${idc.result_table_id ?? ''}`.toLowerCase().includes(keyword));
    };

    const formatList = computed(() => {
      const keyword = searchKeyword.value.trim().toLowerCase();
      const isSearching = keyword.length > 0;
      const activeTagId = tagItem.value.tag_id;
      const isTagFiltering = activeTagId !== undefined;
      const hideEmpty = hiddenEmptyItem.value;
      const selectedSet = selectedUniqueIdSet.value;
      const openManager = listNodeOpenManager.value;
      const isSingle = props.type === 'single';

      const isSelected = (node: IndexSetItem) => selectedSet.has(node.unique_id);

      /**
       * 节点是否展示：
       * - 非检索时：已选中节点始终展示；其余按展开状态 / Tag / 隐藏无数据
       * - 检索时：仅按关键字命中，并与 Tag、隐藏无数据条件取交集（精确过滤）
       */
      const checkNodeShouldShow = (node: IndexSetItem, defaultIsShown = true) => {
        if (!isSearching && isSelected(node)) {
          return true;
        }

        // 检索时需遍历全部节点，不能依赖父节点展开态作为默认可见性
        let isShownNode = isSearching ? true : defaultIsShown;

        if (isTagFiltering) {
          isShownNode = isShownNode && node.tags.some(tag => tag.tag_id === activeTagId);
        }

        if (isShownNode && hideEmpty && !isSelected(node)) {
          isShownNode = !hasNoDataTag(node);
        }

        if (isSearching) {
          isShownNode = isShownNode && matchSearchKeyword(node, keyword);
        }

        return isShownNode;
      };

      const sortBySelectedAndData = (a: any, b: any, compareSelectedChild = false) => {
        if (isSingle) {
          const aIsSelected = isSelected(a);
          const bIsSelected = isSelected(b);
          if (aIsSelected !== bIsSelected) {
            return aIsSelected ? -1 : 1;
          }

          if (compareSelectedChild) {
            const aHasSelectedChild = a.has_selected_child;
            const bHasSelectedChild = b.has_selected_child;
            if (aHasSelectedChild !== bHasSelectedChild) {
              return aHasSelectedChild ? -1 : 1;
            }
          }
        }

        const aHasNoData = hasNoDataTag(a);
        const bHasNoData = hasNoDataTag(b);
        if (aHasNoData !== bHasNoData) {
          return aHasNoData ? 1 : -1;
        }

        return 0;
      };

      const processChildren = (children: any[], parentNode: IndexSetItem) => {
        if (!children?.length) {
          return [];
        }

        const parentOpened = openManager[parentNode.unique_id] === 'opened';
        const processedChildren = children.map(child => ({
          ...child,
          is_shown_node: checkNodeShouldShow(child, parentOpened),
        }));

        return processedChildren.sort((a, b) => sortBySelectedAndData(a, b));
      };

      // 非检索且非 Tag 过滤时：若因选中子节点需要展开分组，则展示同组其它子节点（浏览态）
      // 检索 / Tag 过滤时必须精确命中，禁止把同组无关节点一并展开
      const shouldExpandAllSiblings = !isSearching && !isTagFiltering;

      // 只处理根节点；若误传入扁平列表，跳过 is_child_node 避免与分组内子节点重复渲染
      const rootList = (props.list as IndexSetItem[]).filter((item: any) => !item.is_child_node);

      const processedList = rootList.map((item: any) => {
        const isShownNode = checkNodeShouldShow(item);
        const children = item.children?.length ? processChildren(item.children, item) : item.children;
        const hasVisibleChild = children?.some((child: any) => child.is_shown_node) ?? false;
        const hasSelectedChild = children?.some((child: any) => isSelected(child)) ?? false;

        let nextChildren = children;
        if (hasVisibleChild && shouldExpandAllSiblings && children?.length) {
          nextChildren = children.map((child: any) => {
            let childShown = true;
            if (hideEmpty && !isSelected(child)) {
              childShown = !hasNoDataTag(child);
            }
            return childShown === child.is_shown_node ? child : { ...child, is_shown_node: childShown };
          });
        }

        return {
          ...item,
          children: nextChildren,
          is_shown_node: isShownNode || hasVisibleChild,
          // 检索命中子节点时自动展开分组；浏览态下有可见子节点同样展开
          is_children_open: hasVisibleChild,
          has_selected_child: hasSelectedChild,
          has_no_data_child: nextChildren?.every((child: any) => hasNoDataTag(child)) ?? false,
        };
      });

      // 检索时：同一 index_set_id 既在分组下命中、又以独立根节点存在时，优先保留分组内展示，隐藏根级重复项
      if (isSearching) {
        const shownChildIdSet = new Set<string>();
        for (const item of processedList) {
          for (const child of item.children ?? []) {
            if (child.is_shown_node) {
              shownChildIdSet.add(`${child.index_set_id}`);
            }
          }
        }

        if (shownChildIdSet.size > 0) {
          for (const item of processedList) {
            const isGroupRoot = item.children?.length > 0 || item.is_group;
            if (!isGroupRoot && item.is_shown_node && shownChildIdSet.has(`${item.index_set_id}`)) {
              item.is_shown_node = false;
            }
          }
        }
      }

      return processedList.sort((a, b) => sortBySelectedAndData(a, b, true));
    });

    /** 最终用于渲染的根节点列表（已带精确过滤后的 children.is_shown_node） */
    const filterList = computed(() => formatList.value.filter((item: any) => item.is_shown_node));

    /**
     * 索引集选中操作
     * @param e
     * @param item
     */
    const handleIndexSetItemClick = (_e: MouseEvent, item: any, isRootChecked = false) => {
      if (!item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
        return;
      }

      if (props.type === 'single') {
        emit('value-change', [item.unique_id]);
        return;
      }

      if (props.type === 'union') {
        if (isRootChecked) {
          return;
        }

        const isChecked = !(isIncludesItem(item) || disableList.value.includes(item.unique_id));
        const list: string[] = [];

        for (const child of item.children ?? []) {
          if (child.is_shown_node) {
            if (isIncludesItem(child) || disableList.value.includes(child.unique_id)) {
              list.push(child.unique_id);
              // 如果当前为选中操作，检查所有子节点是否有选中态，选中节点会被放置到 disableList
              if (isChecked) {
                disableList.value.push(child.unique_id);
              } else {
                // 如果是非选中，从 disableList 中移除
                const index = disableList.value.indexOf(child.unique_id);
                if (index >= 0) {
                  disableList.value.splice(index, 1);
                }
              }
            }
          }
        }

        handleIndexSetItemCheck(item, isChecked, list);
      }
    };

    const handleFavoriteClick = (e: MouseEvent, item: any) => {
      e.stopPropagation();

      emit(
        'favorite-change',
        Object.assign(item, { id: item.id ?? item.unique_id, index_set_type: 'single' }),
        !item.is_favorite,
      );
    };

    /**
     * 收藏该组合操作
     * @param e
     */
    const handleFavoriteGroupClick = (e: MouseEvent) => {
      e.stopPropagation();

      if (favoriteFormData.value.name === '') {
        refFavoriteItemName.value.validator.state = 'error';
        refFavoriteItemName.value.validator.content = '收藏名称不能为空';
        return;
      }

      emit('favorite-change', favoriteFormData.value.name, true);
      refFavoriteGroup.value?.hide();
    };

    const handleHiddenEmptyItemChange = (val: boolean) => {
      hiddenEmptyItem.value = val;
    };

    const handleTagItemClick = (tag: { tag_id: number; name: string; color: string }) => {
      if (tagItem.value.tag_id === tag.tag_id) {
        Object.assign(tagItem.value, { tag_id: undefined, name: undefined, color: '' });
        return;
      }

      Object.assign(tagItem.value, tag);
    };

    const handleDeleteCheckedItem = (e: MouseEvent, item) => {
      e.stopPropagation();

      // 如果删除的是父节点，需要将子节点从 disableList 中移除，并作为 storeList 传入以保留子节点选中
      const childIds: string[] = [];
      for (const child of item.children ?? []) {
        const index = disableList.value.indexOf(child.unique_id);
        if (index >= 0) {
          disableList.value.splice(index, 1);
          childIds.push(child.unique_id);
        }
      }

      handleIndexSetItemCheck(item, false, childIds);
    };

    const handleClearValues = (e: MouseEvent) => {
      e.stopPropagation();
      disableList.value = [];
      clearAllValue();
    };

    const handleNodeOpenClick = (e: MouseEvent, node) => {
      e.stopPropagation();
      let nextStatus = listNodeOpenManager.value[node.unique_id] === 'opened' ? 'closed' : 'opened';

      if (searchKeyword.value?.length > 0 && listNodeOpenManager.value[node.unique_id] !== 'forceClosed') {
        nextStatus = 'forceClosed';
      }

      if (node.is_children_open) {
        nextStatus = 'forceClosed';
      }

      if (listNodeOpenManager.value[node.unique_id] === 'forceClosed') {
        nextStatus = 'opened';
      }

      set(listNodeOpenManager.value, node.unique_id, nextStatus);
    };

    const handleAuthBtnClick = (e: MouseEvent, item: any) => {
      e.stopPropagation();
      emit('auth-request', item);
    };

    const getCheckBoxRender = (item, isRootChecked = false) => {
      if (props.type === 'single') {
        return null;
      }

      return (
        <bk-checkbox
          style='margin-right: 4px'
          checked={isIncludesItem(item) || disableList.value.includes(item.unique_id)}
          disabled={isRootChecked}
        />
      );
    };

    const isClosedNode = (item: any) => {
      if (listNodeOpenManager.value[item.unique_id] === 'forceClosed') {
        return true;
      }

      // 与过滤计算使用同一关键字，避免防抖窗口内展开态与列表不一致
      if (searchKeyword.value?.length > 0) {
        return false;
      }

      if (item.is_children_open) {
        return false;
      }

      return !['opened'].includes(listNodeOpenManager.value[item.unique_id]);
    };

    /**
     * 渲染节点数据
     * @param item
     * @param is_child
     * @param has_child
     * @param is_root_checked
     * @returns
     */
    const renderNodeItem = (
      item: any,
      isChild = false,
      hasChild = true,
      isRootChecked = false,
      hasNoDataChild = false,
    ) => {
      const hasPermission = item.permission?.[authorityMap.SEARCH_LOG_AUTH];
      const isEmptyNode = item.tags?.some(tag => tag.tag_id === 4);
      const isClosed = () => isClosedNode(item);

      return (
        <div
          class={[
            'index-set-item',
            {
              'no-authority': !hasPermission,
              'is-child': isChild,
              'has-child': hasChild,
              // 'is-empty': isEmptyNode,
              'has-no-data-child': hasNoDataChild,
              active: isIncludesItem(item),
            },
          ]}
          onClick={e => handleIndexSetItemClick(e, item, isRootChecked)}
        >
          <div dir={props.textDir}>
            {props.type === 'single' && (
              <span
                class={['favorite-icon bklog-icon bklog-lc-star-shape', { 'is-favorite': item.is_favorite }]}
                onClick={e => handleFavoriteClick(e, item)}
              />
            )}
            <span
              class={[
                'node-open-arrow',
                {
                  'is-closed': isClosed(),
                },
              ]}
              onClick={e => handleNodeOpenClick(e, item)}
            >
              <i class='bklog-icon bklog-arrow-down-filled' />
            </span>

            <bdi class={['index-set-name', { 'no-data': item.tags?.some(tag => tag.tag_id === 4) ?? false }]}>
              {getCheckBoxRender(item, isRootChecked)}
              <span class={{ 'bklog-empty-icon': true, 'is-empty': isEmptyNode }} />
              <span class='group-icon'>
                <i class='bklog-icon bklog-suoyin-mulu' />
              </span>
              {item.index_set_name}
            </bdi>
          </div>
          <div class='index-set-tags'>
            {hasPermission ? (
              item.tags
                .filter(tag => tag?.tag_id !== 4)
                .map((tag: any) => (
                  <span
                    key={tag.tag_id}
                    class='index-set-tag-item'
                  >
                    {tag.name}
                  </span>
                ))
            ) : (
              <span
                class='index-set-tag-item'
                onClick={e => handleAuthBtnClick(e, item)}
              >
                {$t('申请权限')}
              </span>
            )}
          </div>
        </div>
      );
    };

    const getMainRender = () => {
      if (filterList.value.length === 0) {
        const type = props.list.length ? 'search-empty' : 'empty';
        return (
          <div class='bklog-v3-index-set-list'>
            <bk-exception
              style='margin-top: 50px'
              scene='part'
              type={type}
            />
          </div>
        );
      }

      return (
        <div class='bklog-v3-index-set-list'>
          {filterList.value.map((item: any) => {
            const result: any[] = [];
            const isRootChecked = isIncludesItem(item);

            if (!isClosedNode(item)) {
              for (const child of item.children ?? []) {
                if (child.is_shown_node || disableList.value.includes(child.unique_id)) {
                  result.push(renderNodeItem(child, true, false, isRootChecked, item.has_no_data_child));
                }
              }
            }

            result.unshift(renderNodeItem(item, false, item.children?.length > 0, false));

            return result;
          })}
        </div>
      );
    };

    const getSingleBody = () => {
      return [getMainRender()];
    };

    /**
     * 联合查询渲染
     * @returns
     */
    const getUnionBody = () => {
      return (
        <div class='content-body-multi'>
          <div class='body'>{getSingleBody()}</div>
          <div class='footer'>
            <div class='row-lable'>
              <div>
                <i18n
                  style='font-size: 12px; color: #4d4f56;'
                  path='已选择{0}个索引集'
                >
                  <span style='color: #3A84FF; font-weight: 700;'>{props.value.length}</span>
                </i18n>
                ,{' '}
                <span
                  style='color: #3A84FF;font-size: 12px;cursor: pointer;'
                  onClick={handleClearValues}
                >
                  {$t('清空选择')}
                </span>
              </div>
              {!isMonitorComponent && (
                <BklogPopover
                  ref={refFavoriteGroup}
                  trigger='click'
                  {...{
                    scopedSlots: {
                      content: () => (
                        <bk-form
                          style='padding: 16px; width: 300px;'
                          form-type='vertical'
                          label-width={200}
                        >
                          <bk-form-item
                            ref={refFavoriteItemName}
                            label={$t('收藏名称')}
                            property='name'
                            required={true}
                          >
                            <bk-input
                              value={favoriteFormData.value.name}
                              on-change={val => (favoriteFormData.value.name = val)}
                            />
                          </bk-form-item>
                          <bk-form-item style='text-align: right;'>
                            <bk-button
                              style='margin-right: 3px;'
                              theme='primary'
                              onClick={handleFavoriteGroupClick}
                            >
                              {$t('确定')}
                            </bk-button>
                            <bk-button
                              ext-cls='mr5'
                              theme='default'
                            >
                              {$t('取消')}
                            </bk-button>
                          </bk-form-item>
                        </bk-form>
                      ),
                    },
                  }}
                >
                  <span
                    style='color: #DCDEE5; font-size: 14px; margin-right: 4px;'
                    class='bklog-icon bklog-lc-star-shape'
                  />
                  <span style='font-size: 12px;color: #3A84FF;'>{$t('收藏该组合')}</span>
                </BklogPopover>
              )}
            </div>
            <div class='row-item-list'>
              {props.value.map((item: any, index: number) => (
                <span
                  key={`${item.unique_id}-${index}`}
                  class='row-value-item'
                >
                  {item.index_set_name}
                  <span
                    class='bklog-icon bklog-close'
                    onClick={e => handleDeleteCheckedItem(e, item)}
                  />
                </span>
              ))}
            </div>
          </div>
        </div>
      );
    };

    const tagScrollTo = (e: MouseEvent, position: string) => {
      const target = (e.target as HTMLElement).closest('.bklog-v3-tag-list').lastElementChild as HTMLElement;
      const { offsetWidth, scrollWidth } = target;

      if (offsetWidth < scrollWidth) {
        let leftPx = position === 'left' ? target.scrollLeft - offsetWidth : target.scrollLeft + offsetWidth;
        if (leftPx < 0) {
          leftPx = 0;
        }

        if (leftPx > scrollWidth) {
          leftPx = scrollWidth;
        }

        target.scrollTo({
          left: leftPx,
          behavior: 'smooth',
        });
      }
    };

    const applySearchKeyword = (val: string) => {
      searchKeyword.value = val;
      if (val.length > 0) {
        for (const key of Object.keys(listNodeOpenManager.value)) {
          if (listNodeOpenManager.value[key] === 'forceClosed') {
            delete listNodeOpenManager.value[key];
          }
        }
      }
    };

    const debouncedApplySearchKeyword = debounce(applySearchKeyword, 200);

    const handleSearchTextChange = (val: string) => {
      searchText.value = val;
      // 清空时立即生效，避免防抖导致空结果残留
      if (!val) {
        debouncedApplySearchKeyword.cancel();
        applySearchKeyword('');
        return;
      }
      debouncedApplySearchKeyword(val);
    };

    onBeforeUnmount(() => {
      debouncedApplySearchKeyword.cancel();
    });

    const getFilterRow = () => {
      return (
        <div class='bklog-v3-content-filter'>
          <div class='bklog-v3-search-input'>
            <bk-input
              style='width: 100%; margin-right: 12px;'
              placeholder={$t('请输入 索引集、采集项 搜索')}
              right-icon="'bk-icon icon-search'"
              value={searchText.value}
              clearable
              on-input={handleSearchTextChange}
            />
            <bk-checkbox
              checked={hiddenEmptyItem.value}
              false-value={false}
              true-value={true}
              on-change={handleHiddenEmptyItemChange}
            >
              <span class='hidden-empty-icon' />
              <span>{$t('隐藏无数据')}</span>
            </bk-checkbox>
          </div>
          <div class={['bklog-v3-tag-list', { 'is-empty': indexSetTagList.value.length === 0 }]}>
            <div
              class='move-icon left-icon'
              onClick={e => tagScrollTo(e, 'left')}
            >
              <i class='bk-icon icon-angle-left-line' />
            </div>
            <div
              class='move-icon right-icon'
              onClick={e => tagScrollTo(e, 'right')}
            >
              <i class='bk-icon icon-angle-right-line' />
            </div>
            <div class='tag-scroll-container'>
              {indexSetTagList.value.map(item => (
                <span
                  key={item.tag_id}
                  class={['tag-item', { 'is-active': item.tag_id === tagItem.value.tag_id }]}
                  onClick={() => handleTagItemClick(item)}
                >
                  {item.name}
                </span>
              ))}
            </div>
          </div>
        </div>
      );
    };

    return () => (
      <div class='bklog-v3-index-set-root'>
        {getFilterRow()}
        <div class='bklog-v3-content-list'>{props.type === 'single' ? getSingleBody() : getUnionBody()}</div>
      </div>
    );
  },
});
