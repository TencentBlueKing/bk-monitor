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
import useChoice from './use-choice';

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
  },
  emits: ['value-change'],
  setup(props, { emit }) {
    const { handleIndexSetItemCheck, indexSetTagList } = useChoice(props, { emit });

    const hiddenEmptyItem = ref(true);
    const searchText = ref('');

    const tagItem = ref({
      tag_id: undefined,
      name: undefined,
      color: undefined,
    });
    const noDataReg = /^No\sData$/i;

    const valueList = computed(() => props.list.filter((item: any) => props.value.includes(item.index_set_id)));

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
            return (
              !item.tags.some(tag => noDataReg.test(tag.name)) && item.index_set_name.indexOf(searchText.value) !== -1
            );
          }

          return item.index_set_name.indexOf(searchText.value) !== -1;
        }),
    );

    /**
     * 索引集选中操作
     * @param e
     * @param item
     */
    const handleIndexSetItemClick = (e: MouseEvent, item: any) => {
      if (props.type === 'single') {
        emit('value-change', [item.index_set_id]);
      }
    };

    const handleFavoriteClick = (e: MouseEvent, item: any) => {};
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

    const getCheckBoxRender = item => {
      if (props.type === 'single') {
        return null;
      }

      return (
        <bk-checkbox
          style='margin-right: 4px'
          checked={props.value.includes(item.index_set_id)}
          on-change={value => handleIndexSetItemCheck(item, value)}
        ></bk-checkbox>
      );
    };

    const getMainRender = () => {
      return (
        <div class='bklog-v3-index-set-list'>
          {filterList.value.map((item: any) => {
            return (
              <div
                class={[
                  'index-set-item',
                  {
                    'no-authority': item.permission?.[authorityMap.SEARCH_LOG_AUTH],
                    active: props.value.includes(item.index_set_id),
                  },
                ]}
                onClick={e => handleIndexSetItemClick(e, item)}
              >
                <div dir={props.textDir}>
                  <span
                    class={['favorite-icon bklog-icon bklog-lc-star-shape', { 'is-favorite': item.is_favorite }]}
                    onClick={e => handleFavoriteClick(e, item)}
                  ></span>
                  <span class='group-icon'></span>

                  <bdi
                    class={['index-set-name', { 'no-data': item.tags?.some(tag => noDataReg.test(tag.name)) ?? false }]}
                  >
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
      return [getMainRender(), <div class='bklog-v3-item-info'></div>];
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
                , <span style='color: #3A84FF;font-size: 12px;cursor: pointer;'>清空选择</span>
              </div>
              <div>
                <span
                  class='bklog-icon bklog-lc-star-shape'
                  style='color: #DCDEE5; font-size: 14px; margin-right: 4px;'
                ></span>
                <span style='font-size: 12px;color: #3A84FF;'>收藏该组合</span>
              </div>
            </div>
            <div class='row-item-list'>
              {valueList.value.map((item: any) => (
                <span class='row-value-item'>
                  {item.index_set_name}
                  <span
                    class='bklog-icon bklog-close'
                    onClick={() => handleIndexSetItemCheck(item, false)}
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
                onClick={() => handleTagItemClick(item)}
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
