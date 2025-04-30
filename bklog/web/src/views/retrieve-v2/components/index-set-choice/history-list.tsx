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
import './history-list.scss';

export default defineComponent({
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    isLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['delete', 'value-click'],
  setup(props, { emit }) {
    const handleItemClick = (itme: any) => {
      emit('value-click', itme);
    };
    const handleDeleteItem = (e: MouseEvent, item: any) => {
      e.stopPropagation();
      emit('delete', item);
    };

    const listItemRender = (item: any) => {
      if (item.index_set_names !== undefined) {
        return (
          <div
            class='history-row multi'
            onClick={() => handleItemClick(item)}
          >
            <span class='row-left'>
              <span class='bklog-icon bklog-history-2'></span>
              <span class='row-item-list'>
                {item.index_set_names.map(name => (
                  <span class='row-item'>{name}</span>
                ))}
              </span>
            </span>
            <span
              class='bklog-icon bklog-log-delete'
              onClick={e => handleDeleteItem(e, item)}
            ></span>
          </div>
        );
      }

      return (
        <div
          class='history-row single'
          onClick={() => handleItemClick(item)}
        >
          <span class='row-left'>
            <span class='bklog-icon bklog-history-2'></span>
            <span class='row-item'>{item.index_set_name}</span>
          </span>
          <span
            class='bklog-icon bklog-log-delete'
            onClick={e => handleDeleteItem(e, item)}
          ></span>
        </div>
      );
    };

    const getBodyRender = () => {
      if (props.list.length === 0 && !props.isLoading) {
        return (
          <bk-exception
            type='empty'
            scene='part'
          ></bk-exception>
        );
      }

      return props.list.map(item => listItemRender(item));
    };

    return () => (
      <div
        class='bklog-v3-index-set-history'
        v-bkloading={{ isLoading: props.isLoading }}
      >
        <div class='history-header'>
          <span>搜索历史（{props.list.length}/10）</span>
          <span
            class='bklog-icon bklog-saoba'
            onClick={e => handleDeleteItem(e, null)}
          >
            清空历史
          </span>
        </div>
        <div class='history-list'>{getBodyRender()}</div>
      </div>
    );
  },
});
