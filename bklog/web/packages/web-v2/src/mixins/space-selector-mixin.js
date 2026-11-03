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

import { SPACE_TYPE_MAP } from '@/store/constant';

export default {
  data() {
    return {
      /** 空间多选 */
      spaceMultiple: true,
      /** 是否展示正在使用的标记 */
      isUseMark: true,
    };
  },
  methods: {
    /** 空间选择 */
    handleSelectSpaceChange(bizId) {
      this.visibleBkBiz = this.visibleBkBiz.includes(bizId)
        ? this.visibleBkBiz.filter(val => val !== bizId)
        : [...this.visibleBkBiz, bizId];
    },
    /** 空间选择器下拉选择面板 */
    virtualscrollSpaceList(item, h) {
      return h(
        'div',
        {
          class: `space-code-option ${this.spaceMultiple && this.visibleBkBiz.includes(item.bk_biz_id) ? 'is-selected' : ''}`,
          on: {
            click: e => {
              e.stopPropagation();
              this.handleSelectSpaceChange(item.bk_biz_id);
            },
          },
        },
        [
          h(
            'div',
            {
              class: 'list-item-left',
            },
            [
              this.isUseMark &&
                h('span', { class: `identify-icon ${this.isUseMark && item.is_use ? 'is-use' : 'not-use'}` }),
              h('span', { class: 'code-name' }, [
                item.space_full_code_name,
                this.isUseMark && item.is_use ? `（${this.$t('正在使用')}）` : '',
              ]),
            ],
          ),
          h(
            'div',
            {
              class: 'list-item-right',
            },
            [
              item.space_type_name &&
                item.tags.map(tag =>
                  h(
                    'span',
                    {
                      class: 'list-item-tag light-theme',
                      style: {
                        ...SPACE_TYPE_MAP[tag.id].light,
                      },
                    },
                    tag.name,
                  ),
                ),
              this.spaceMultiple &&
                h('span', {
                  class: this.visibleBkBiz.includes(item.bk_biz_id) && 'bk-icon icon-check-1',
                }),
            ],
          ),
        ],
      );
    },
  },
};
