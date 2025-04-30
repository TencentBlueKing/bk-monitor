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

import { defineComponent } from 'vue';
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
    const handleIndexSetTagItemClick = (item: any, tag: any) => {
      console.log(item, tag);
    };

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

    const { handleIndexSetItemCheck } = useChoice(props, { emit });

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

    const noDataReg = /^No\sData$/i;

    return () => {
      return (
        <div class='bklog-v3-index-set-list'>
          {props.list.map((item: any) => {
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
                    <span
                      class='index-set-tag-item'
                      onClick={() => handleIndexSetTagItemClick(item, tag)}
                    >
                      {tag.name}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      );
    };
  },
});
