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

import { computed, defineComponent, ref, set } from 'vue';

import useLocale from '@/hooks/use-locale';

import * as authorityMap from '../../../../common/authority-map';
import BklogPopover from '../../../../components/bklog-popover';
import useIndexSetList from './use-index-set-list';

import './index-set-list.scss';

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
      type: Array,
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
    const searchText = ref('');
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

    const propValueStrList = computed(() => props.value.map(id => `${id}`));
    const valueList = computed(() =>
      props.list.filter((item: any) => propValueStrList.value.includes(`${item.index_set_id}`)),
    );

    const formatList = computed(() => {
      const filterFn = node => {
        return ['index_set_name', 'index_set_id', 'bk_biz_id', 'collector_config_id'].some(
          key =>
            `${node[key]}`.indexOf(searchText.value) !== -1 ||
            (node.indices ?? []).some(idc => `${idc.result_table_id}`.indexOf(searchText.value) !== -1),
        );
      };
      // 检查节点是否应该显示
      const checkNodeShouldShow = (node: any, defaultIsShown = true) => {
        // 如果当前节点在选中列表中，直接返回 true
        if (propValueStrList.value.includes(`${node.index_set_id}`) && searchText.value.length === 0) {
          return true;
        }

        let is_shown_node = defaultIsShown;

        // 判定是不是已经选中Tag进行过滤
        if (tagItem.value.tag_id !== undefined) {
          is_shown_node = node.tags.some(tag => tag.tag_id === tagItem.value.tag_id);
        }

        // 如果满足Tag标签或者当前条目为显示状态
        // 如果启用隐藏空数据
        if (is_shown_node && hiddenEmptyItem.value && !props.value.includes(`${node.index_set_id}`)) {
          is_shown_node = !node.tags.some(tag => tag.tag_id === 4);
        }

        // 继续判定检索匹配是否满足匹配条件
        if (searchText.value.length > 0) {
          is_shown_node = filterFn(node);
        }

        return is_shown_node;
      };

      // 处理子节点
      const processChildren = (children: any[], parentNode) => {
        if (!children?.length) {
          return [];
        }

        // 处理子节点的显示状态
        const processedChildren = children.map(child => ({
          ...child,
          is_shown_node: checkNodeShouldShow(child, listNodeOpenManager.value[parentNode.index_set_id] === 'opened'),
          __unique_id__: `Child_${parentNode.index_set_id}_${child.index_set_id}`,
        }));

        // 对子节点进行排序
        // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
        return processedChildren.sort((a: any, b: any) => {
          // 单选模式下才进行特殊排序
          if (props.type === 'single') {
            // 如果节点在选中列表中，优先级最高
            const aIsSelected = propValueStrList.value.includes(`${a.index_set_id}`);
            const bIsSelected = propValueStrList.value.includes(`${b.index_set_id}`);
            if (aIsSelected !== bIsSelected) {
              return aIsSelected ? -1 : 1;
            }
          }

          // 其次按是否有数据排序
          const aHasNoData = a.tags.some(tag => tag.tag_id === 4);
          const bHasNoData = b.tags.some(tag => tag.tag_id === 4);
          if (aHasNoData !== bHasNoData) {
            return aHasNoData ? 1 : -1;
          }

          return 0;
        });
      };

      // 处理根节点
      // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
      const processedList = props.list.map((item: any) => {
        const is_shown_node = checkNodeShouldShow(item);

        // 处理子节点
        if (item.children?.length) {
          item.children = processChildren(item.children, item);
        }

        const isOpenNode = item.children?.some(child => child.is_shown_node);
        // 检查是否有子节点被选中
        const hasSelectedChild = item.children?.some(child => propValueStrList.value.includes(`${child.index_set_id}`));

        if (isOpenNode) {
          for (const child of item.children) {
            child.is_shown_node = true;

            if (hiddenEmptyItem.value && !props.value.includes(`${child.index_set_id}`)) {
              // 如果启用隐藏空数据
              child.is_shown_node = !child.tags.some(tag => tag.tag_id === 4);
            }
          }
        }

        return {
          ...item,
          is_shown_node: is_shown_node || isOpenNode,
          is_children_open: isOpenNode,
          has_selected_child: hasSelectedChild,
          has_no_data_child: item.children?.every(child => child.tags?.some(tag => tag.tag_id === 4)),
          __unique_id__: `Root_${item.index_set_id}`,
        };
      });

      // 对根节点进行排序
      // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
      return processedList.sort((a: any, b: any) => {
        // 单选模式下才进行特殊排序
        if (props.type === 'single') {
          // 如果节点在选中列表中，优先级最高
          const aIsSelected = propValueStrList.value.includes(`${a.index_set_id}`);
          const bIsSelected = propValueStrList.value.includes(`${b.index_set_id}`);
          if (aIsSelected !== bIsSelected) {
            return aIsSelected ? -1 : 1;
          }

          // 如果节点有子节点被选中，次优先级
          const aHasSelectedChild = a.has_selected_child;
          const bHasSelectedChild = b.has_selected_child;
          if (aHasSelectedChild !== bHasSelectedChild) {
            return aHasSelectedChild ? -1 : 1;
          }
        }

        // 按是否有数据排序（所有模式都生效）
        const aHasNoData = a.tags.some(tag => tag.tag_id === 4);
        const bHasNoData = b.tags.some(tag => tag.tag_id === 4);
        if (aHasNoData !== bHasNoData) {
          return aHasNoData ? 1 : -1;
        }

        return 0;
      });
    });

    const filterFullList = computed(() => formatList.value.filter((item: any) => item.is_shown_node));

    const rootList = computed(() => formatList.value.filter((item: any) => !item.is_child_node));

    const filterList = computed(() =>
      rootList.value.filter((item: any) => {
        return (
          filterFullList.value.includes(item) ||
          (item.children ?? []).filter(child => filterFullList.value.includes(child)).length > 0
        );
      }),
    );

    /**
     * 索引集选中操作
     * @param e
     * @param item
     */

    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const handleIndexSetItemClick = (_e: MouseEvent, item: any, is_root_checked = false) => {
      if (!item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
        return;
      }

      if (props.type === 'single') {
        emit('value-change', [item.index_set_id]);
        return;
      }

      if (props.type === 'union') {
        if (is_root_checked) {
          return;
        }

        const indexSetId = `${item.index_set_id}`;
        const isChecked = !(propValueStrList.value.includes(indexSetId) || disableList.value.includes(indexSetId));
        const list: string[] = [];

        for (const child of item.children ?? []) {
          if (child.is_shown_node) {
            const childId = `${child.index_set_id}`;
            if (propValueStrList.value.includes(childId) || disableList.value.includes(childId)) {
              const id = `${child.index_set_id}`;
              list.push(id);
              // 如果当前为选中操作，检查所有子节点是否有选中态，选中节点会被放置到 disableList
              if (isChecked) {
                disableList.value.push(id);
              } else {
                // 如果是非选中，从 disableList 中移除
                const index = disableList.value.indexOf(id);
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
        Object.assign(item, { id: item.id ?? item.index_set_id, index_set_type: 'single' }),
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
      handleIndexSetItemCheck(item, false);
    };

    const handleClearValues = (e: MouseEvent) => {
      e.stopPropagation();
      clearAllValue();
    };

    const handleNodeOpenClick = (e: MouseEvent, node) => {
      e.stopPropagation();
      let nextStatus = listNodeOpenManager.value[node.index_set_id] === 'opened' ? 'closed' : 'opened';

      if (searchText.value?.length > 0 && listNodeOpenManager.value[node.index_set_id] !== 'forceClosed') {
        nextStatus = 'forceClosed';
      }

      if (node.is_children_open) {
        nextStatus = 'forceClosed';
      }

      if (listNodeOpenManager.value[node.index_set_id] === 'forceClosed') {
        nextStatus = 'opened';
      }

      set(listNodeOpenManager.value, node.index_set_id, nextStatus);
    };

    const handleAuthBtnClick = (e: MouseEvent, item: any) => {
      e.stopPropagation();
      emit('auth-request', item);
    };

    const getCheckBoxRender = (item, is_root_checked = false) => {
      if (props.type === 'single') {
        return null;
      }

      return (
        <bk-checkbox
          style='margin-right: 4px'
          checked={propValueStrList.value.includes(item.index_set_id) || disableList.value.includes(item.index_set_id)}
          disabled={is_root_checked}
        />
      );
    };

    const isClosedNode = (item: any) => {
      if (listNodeOpenManager.value[item.index_set_id] === 'forceClosed') {
        return true;
      }

      if (searchText.value?.length > 0) {
        return false;
      }

      if (item.is_children_open) {
        return false;
      }

      return !['opened'].includes(listNodeOpenManager.value[item.index_set_id]);
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
      is_child = false,
      has_child = true,
      is_root_checked = false,
      has_no_data_child = false,
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
              'is-child': is_child,
              'has-child': has_child,
              // 'is-empty': isEmptyNode,
              'has-no-data-child': has_no_data_child,
              active: propValueStrList.value.includes(item.index_set_id),
            },
          ]}
          onClick={e => handleIndexSetItemClick(e, item, is_root_checked)}
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
              {getCheckBoxRender(item, is_root_checked)}
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
            const is_root_checked = propValueStrList.value.includes(item.index_set_id);

            if (!isClosedNode(item)) {
              for (const child of item.children ?? []) {
                if (child.is_shown_node || disableList.value.includes(child.index_set_id)) {
                  result.push(renderNodeItem(child, true, false, is_root_checked, item.has_no_data_child));
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
              {valueList.value.map((item: any) => (
                <span
                  key={item}
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

    const handleSearchTextChange = (val: string) => {
      searchText.value = val;
      if (searchText.value.length > 0) {
        for (const key of Object.keys(listNodeOpenManager.value)) {
          if (listNodeOpenManager.value[key] === 'forceClosed') {
            delete listNodeOpenManager.value[key];
          }
        }
      }
    };

    const getFilterRow = () => {
      return (
        <div class='bklog-v3-content-filter'>
          <div class='bklog-v3-search-input'>
            <bk-input
              style='width: 650px; margin-right: 12px;'
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
