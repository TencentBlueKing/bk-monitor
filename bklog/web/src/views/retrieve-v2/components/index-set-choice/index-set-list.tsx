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

import { computed, defineComponent, ref } from 'vue';
import './index-set-list.scss';

import * as authorityMap from '../../../../common/authority-map';
import BklogPopover from '../../../../components/bklog-popover';
import useLocale from '@/hooks/use-locale';
import useIndexSetList from './use-index-set-list';
import ObjectView from '../../../../components/object-view';

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
  emits: ['value-change', 'favorite-change'],
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

    const tagItem = ref({
      tag_id: undefined,
      name: undefined,
      color: undefined,
    });

    const propValueStrList = computed(() => props.value.map(id => `${id}`));
    const valueList = computed(() =>
      props.list.filter((item: any) => propValueStrList.value.includes(`${item.index_set_id}`)),
    );

    const filterList = computed(() =>
      props.list
        .filter((item: any) => {
          if (tagItem.value.tag_id === undefined) {
            return true;
          }

          return item.tags.some(tag => tag.tag_id === tagItem.value.tag_id);
        })
        .filter((item: any) => {
          if (hiddenEmptyItem.value) {
            if (props.value.includes(`${item.index_set_id}`)) {
              return true;
            }

            return !item.tags.some(tag => tag.tag_id === 4) && item.index_set_name.indexOf(searchText.value) !== -1;
          }

          return item.index_set_name.indexOf(searchText.value) !== -1;
        }),
    );

    const activeValueItems = computed(() => {
      return propValueStrList.value.map((item: any) => {
        return props.list.find((indexSet: any) => indexSet.index_set_id === item);
      });
    });

    const objectShowList = [
      { fieldName: 'index_set_name', label: $t('索引集名称') },
      { fieldName: 'index_set_id', label: $t('索引集ID') },
      { fieldName: 'index_set_id', label: $t('关联采集项') },
    ];

    /**
     * 索引集选中操作
     * @param e
     * @param item
     */
    const handleIndexSetItemClick = (e: MouseEvent, item: any) => {
      if (props.type === 'single') {
        emit('value-change', [item.index_set_id]);
        return;
      }

      if (props.type === 'union') {
        handleIndexSetItemCheck(item, !propValueStrList.value.includes(`${item.index_set_id}`));
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

    const getCheckBoxRender = item => {
      if (props.type === 'single') {
        return null;
      }

      return (
        <bk-checkbox
          style='margin-right: 4px'
          checked={propValueStrList.value.includes(item.index_set_id)}
          // on-change={value => handleIndexSetItemCheck(item, value)}
        ></bk-checkbox>
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
            return (
              <div
                class={[
                  'index-set-item',
                  {
                    'no-authority': item.permission?.[authorityMap.SEARCH_LOG_AUTH],
                    active: propValueStrList.value.includes(item.index_set_id),
                  },
                ]}
                onClick={e => handleIndexSetItemClick(e, item)}
              >
                <div dir={props.textDir}>
                  {props.type === 'single' && (
                    <span
                      class={['favorite-icon bklog-icon bklog-lc-star-shape', { 'is-favorite': item.is_favorite }]}
                      onClick={e => handleFavoriteClick(e, item)}
                    ></span>
                  )}
                  <span class='group-icon'></span>

                  <bdi class={['index-set-name', { 'no-data': item.tags?.some(tag => tag.tag_id === 4) ?? false }]}>
                    {getCheckBoxRender(item)}
                    {item.index_set_name}
                  </bdi>
                </div>
                <div class='index-set-tags'>
                  {item.tags.map((tag: any) => (
                    <span class='index-set-tag-item'>{tag.name}</span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      );
    };

    const getSingleBody = () => {
      return [
        getMainRender(),
        <div class='bklog-v3-item-info'>
          {activeValueItems.value.map((item: any) => (
            <ObjectView
              object={item}
              showList={objectShowList}
              labelWidth={120}
            ></ObjectView>
          ))}
        </div>,
      ];
    };

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
          <div class='bklog-v3-tag-list'>
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
