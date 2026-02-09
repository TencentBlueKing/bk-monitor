/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, defineComponent, shallowRef } from 'vue';

import { Checkbox, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './index-set-selector-pop.scss';

export const SELECTOR_TYPE = {
  single: 'single',
  multiple: 'multiple',
} as const;
const SELECTOR_TYPE_LIST = [
  {
    id: SELECTOR_TYPE.single,
    name: window.i18n.t('单选'),
  },
  {
    id: SELECTOR_TYPE.multiple,
    name: window.i18n.t('多选'),
  },
];

export interface IOptions {
  id: string;
  name: string;
}

export default defineComponent({
  name: 'IndexSetSelectorPop',
  props: {
    type: {
      type: String as PropType<(typeof SELECTOR_TYPE)[keyof typeof SELECTOR_TYPE]>,
      default: SELECTOR_TYPE.single,
    },
  },
  setup() {
    const { t } = useI18n();
    const tags = shallowRef([
      {
        id: 'xx',
        name: 'tag1',
      },
      {
        id: 'xx2',
        name: 'tag2',
      },
    ]);
    const filterList = shallowRef([
      {
        id: 'xx',
        name: 'xxx1',
      },
      {
        id: 'xx2',
        name: 'xxx2',
      },
      {
        id: 'xx3',
        name: 'xxx3',
      },
    ]);
    const searchValue = shallowRef('');

    return {
      tags,
      filterList,
      searchValue,
      t,
    };
  },
  render() {
    function renderOption(item: IOptions) {
      return (
        <div
          key={item.id}
          class='index-set-item'
        >
          <span class='item-left'>
            <span class='favorite-icon'>
              <i class='icon-monitor icon-mc-collect' />
            </span>
            <span class='node-open-arrow'>
              <span class='icon-monitor icon-mc-arrow-right' />
            </span>
            <span class='index-set-name'>
              <Checkbox />
              <span class='empty-icon' />
              <span class='group-icon'>
                <span class='icon-monitor icon-FileFold-Close' />
              </span>
              <span class='name'>{item.name}</span>
            </span>
          </span>

          <span class='index-set-tags'>
            <span class='index-set-tag-item'>BCS-K8S-00000</span>
          </span>
        </div>
      );
    }
    return (
      <div class='alarm-center-detail-panel-alarm-log-index-set-selector-pop'>
        <div class='tab-wrap'>
          <div class='tab-list'>
            {SELECTOR_TYPE_LIST.map(item => (
              <div
                key={item.id}
                class='tab-item'
              >
                {item.name}
              </div>
            ))}
          </div>
        </div>
        <div class='search-wrap'>
          <Input
            class='search-input'
            modelValue={this.searchValue}
            placeholder={this.t('搜索')}
          />
          <Checkbox>{this.t('隐藏无数据')}</Checkbox>
        </div>
        <div class='tags-list'>
          <div class='move-icon left-icon'>
            <i class='icon-monitor icon-arrow-left' />
          </div>
          <div class='move-icon right-icon'>
            <i class='icon-monitor icon-arrow-right' />
          </div>
          <div class='tag-scroll-container'>
            {this.tags.map(item => (
              <div
                key={item.id}
                class='tag-item'
              >
                {item.name}
              </div>
            ))}
          </div>
        </div>
        <div class='index-set-list'>{this.filterList.map(item => renderOption(item))}</div>
      </div>
    );
  },
});
