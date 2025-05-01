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
import './common-list.scss';

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
    type: {
      type: String,
      default: 'history',
    },
    itemIcon: {
      type: Object,
      default: () => ({
        onClick: undefined,
        icon: undefined,
        color: undefined,
      }),
    },
    showDelItem: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['delete', 'value-click', 'icon-click'],
  setup(props, { emit }) {
    const textMap = ref({
      history: {
        title: '搜索历史',
        delLable: '清空历史',
        itemIcon: 'bklog-history-2',
      },
      favorite: {
        title: '我的收藏',
        delLable: '清空收藏',
        itemIcon: 'bklog-lc-star-shape',
      },
    });

    const activeMap = computed(() => {
      return textMap.value[props.type] ?? textMap.value.history;
    });

    const handleItemIconClick = (e: MouseEvent, item: any) => {
      if (props.itemIcon?.onClick) {
        props.itemIcon.onClick(e, item);
      }

      emit('icon-click', item);
    };

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
            class='common-row multi'
            onClick={() => handleItemClick(item)}
          >
            <span class='row-left'>
              <span
                class={['bklog-icon', props.itemIcon?.icon ?? activeMap.value.itemIcon]}
                style={{
                  color: props.itemIcon?.color,
                }}
                onClick={e => handleItemIconClick(e, item)}
              ></span>
              <span class='row-item-list'>
                {item.index_set_names.map(name => (
                  <span class='row-item'>{name}</span>
                ))}
              </span>
            </span>
            {props.showDelItem && (
              <span
                class='bklog-icon bklog-log-delete'
                onClick={e => handleDeleteItem(e, item)}
              ></span>
            )}
          </div>
        );
      }

      return (
        <div
          class='common-row single'
          onClick={() => handleItemClick(item)}
        >
          <span class='row-left'>
            <span
              class={['bklog-icon', props.itemIcon?.icon ?? activeMap.value.itemIcon]}
              style={{
                color: props.itemIcon?.color,
              }}
              onClick={e => handleItemIconClick(e, item)}
            ></span>
            <span class='row-item'>{item.index_set_name}</span>
          </span>
          {props.showDelItem && (
            <span
              class='bklog-icon bklog-log-delete'
              onClick={e => handleDeleteItem(e, item)}
            ></span>
          )}
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
        class='bklog-v3-index-set-common-list'
        v-bkloading={{ isLoading: props.isLoading }}
      >
        <div class='common-header'>
          <span>
            {activeMap.value.title}（{props.list.length}/10）
          </span>
          <span
            class='bklog-icon bklog-saoba'
            onClick={e => handleDeleteItem(e, null)}
          >
            {activeMap.value.delLable}
          </span>
        </div>
        <div class='common-list'>{getBodyRender()}</div>
      </div>
    );
  },
});
