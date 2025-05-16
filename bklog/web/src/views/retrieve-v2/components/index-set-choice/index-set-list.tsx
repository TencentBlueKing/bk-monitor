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
import './index-set-list.scss';

import * as authorityMap from '../../../../common/authority-map';
import BklogPopover from '../../../../components/bklog-popover';
import useLocale from '@/hooks/use-locale';
import useIndexSetList from './use-index-set-list';

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

    const hiddenEmptyItem = ref(false);
    const searchText = ref('');
    const refFavoriteItemName = ref(null);
    const refFavoriteGroup = ref(null);
    const favoriteFormData = ref({
      name: '',
    });

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

    const formatList = computed(() =>
      props.list.map((item: any) => {
        let is_shown_node = true;

        // 判定是不是已经选中Tag进行过滤
        // 如果已经选中了Tag进行过滤，这里需要判定当前索引是否满足Tag标签
        if (tagItem.value.tag_id !== undefined) {
          is_shown_node = item.tags.some(tag => tag.tag_id === tagItem.value.tag_id);
        }

        // 如果满足Tag标签或者当前条目为显示状态
        // 继续判断其他过滤条件
        if (is_shown_node) {
          // 如果启用隐藏空数据
          if (hiddenEmptyItem.value) {
            // 如果当前索引不是传入的选中值
            if (!props.value.includes(`${item.index_set_id}`)) {
              // 判断当前索引Tag标签是否有标识为空数据
              // 如果结果为True，说明当前索引不展示
              is_shown_node = !item.tags.some(tag => tag.tag_id === 4);
            }
          }

          // 如果此时判定结果仍然为true
          // 继续判定检索匹配是否满足匹配条件
          if (is_shown_node) {
            is_shown_node = item.index_set_name.indexOf(searchText.value) !== -1;
          }
        }
        Object.assign(item, { is_shown_node });
        return item;
      }),
    );

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
    const handleIndexSetItemClick = (e: MouseEvent, item: any, is_root_checked = false) => {
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
        const list = [];

        (item.children ?? []).forEach(child => {
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
                const index = disableList.value.findIndex(v => (v = id));
                if (index >= 0) {
                  disableList.value.splice(index, 1);
                }
              }
            }
          }
        });

        handleIndexSetItemCheck(item, isChecked, list);
      }
    };

    const handleFavoriteClick = (e: MouseEvent, item: any) => {
      e.stopPropagation();
      emit('favorite-change', item, !item.is_favorite);
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
      const nextStatus = listNodeOpenManager.value[node.index_set_id] === 'closed' ? 'opened' : 'closed';
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
        ></bk-checkbox>
      );
    };

    /**
     * 渲染节点数据
     * @param item
     * @param is_child
     * @param has_child
     * @param is_root_checked
     * @returns
     */
    const renderNodeItem = (item: any, is_child = false, has_child = true, is_root_checked = false) => {
      const hasPermission = item.permission?.[authorityMap.SEARCH_LOG_AUTH];
      return (
        <div
          class={[
            'index-set-item',
            {
              'no-authority': !hasPermission,
              'is-child': is_child,
              'has-child': has_child,
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
              ></span>
            )}
            <span
              class={[
                'node-open-arrow',
                {
                  'is-closed': listNodeOpenManager.value[item.index_set_id] === 'closed',
                },
              ]}
              onClick={e => handleNodeOpenClick(e, item)}
            >
              <i class='bklog-icon bklog-arrow-down-filled'></i>
            </span>

            <bdi class={['index-set-name', { 'no-data': item.tags?.some(tag => tag.tag_id === 4) ?? false }]}>
              {getCheckBoxRender(item, is_root_checked)}

              <span class='group-icon'>
                <i class='bklog-icon bklog-suoyin-mulu'></i>
              </span>
              {item.index_set_name}
            </bdi>
          </div>
          <div class='index-set-tags'>
            {hasPermission ? (
              item.tags
                .filter(tag => tag?.tag_id !== 4)
                .map((tag: any) => <span class='index-set-tag-item'>{tag.name}</span>)
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
              type={type}
              scene='part'
            ></bk-exception>
          </div>
        );
      }

      return (
        <div class='bklog-v3-index-set-list'>
          {filterList.value.map((item: any) => {
            const result = [];
            const is_root_checked = propValueStrList.value.includes(item.index_set_id);

            if (listNodeOpenManager.value[item.index_set_id] !== 'closed') {
              (item.children ?? []).forEach(child => {
                if (child.is_shown_node || disableList.value.includes(child.index_set_id)) {
                  result.push(renderNodeItem(child, true, false, is_root_checked));
                }
              });
            }

            result.unshift(renderNodeItem(item, false, item.children?.length > 0, false));

            return result;
          })}
        </div>
      );
    };

    const getSingleBody = () => {
      return [
        getMainRender(),
        // <div class='bklog-v3-item-info'>
        //   {activeValueItems.value.map((item: any) => (
        //     <ObjectView
        //       object={item}
        //       showList={objectShowList}
        //       labelWidth={100}
        //       class='item-row'
        //     ></ObjectView>
        //   ))}
        // </div>,
      ];
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
              <BklogPopover
                trigger='click'
                ref={refFavoriteGroup}
                {...{
                  scopedSlots: {
                    content: () => (
                      <bk-form
                        label-width={200}
                        form-type='vertical'
                        style='padding: 16px; width: 300px;'
                      >
                        <bk-form-item
                          label={$t('收藏名称')}
                          required={true}
                          property='name'
                          ref={refFavoriteItemName}
                        >
                          <bk-input
                            value={favoriteFormData.value.name}
                            on-change={val => (favoriteFormData.value.name = val)}
                          ></bk-input>
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
                  class='bklog-icon bklog-lc-star-shape'
                  style='color: #DCDEE5; font-size: 14px; margin-right: 4px;'
                ></span>
                <span style='font-size: 12px;color: #3A84FF;'>{$t('收藏该组合')}</span>
              </BklogPopover>
            </div>
            <div class='row-item-list'>
              {valueList.value.map((item: any) => (
                <span class='row-value-item'>
                  {item.index_set_name}
                  <span
                    class='bklog-icon bklog-close'
                    onClick={e => handleDeleteCheckedItem(e, item)}
                  ></span>
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

    const getFilterRow = () => {
      return (
        <div class='bklog-v3-content-filter'>
          <div class='bklog-v3-search-input'>
            <bk-input
              clearable
              placeholder='请输入 索引集、采集项 搜索'
              right-icon="'bk-icon icon-search'"
              style='width: 650px; margin-right: 12px;'
              value={searchText.value}
              on-input={val => (searchText.value = val)}
            ></bk-input>
            <bk-checkbox
              checked={hiddenEmptyItem.value}
              true-value={true}
              false-value={false}
              on-change={handleHiddenEmptyItemChange}
            >
              <span class='hidden-empty-icon'></span>
              <span>隐藏无数据</span>
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
                  class={['tag-item', { 'is-active': item.tag_id === tagItem.value.tag_id }]}
                  onClick={e => handleTagItemClick(item)}
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
