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

import useLocale from '@/hooks/use-locale';

import EllipsisTagList from '../../../../components/ellipsis-tag-list';

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
    idField: {
      type: [String, Function],
      default: 'id',
    },
    nameField: {
      type: [String, Function],
      default: 'name',
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
    value: {
      type: [Number, String],
    },
  },
  emits: ['delete', 'value-click', 'icon-click'],
  setup(props, { emit }) {
    const { $t } = useLocale();
    const textMap = ref({
      history: {
        title: $t('搜索历史'),
        delLable: $t('清空历史'),
        delAll: true,
        itemIcon: 'bklog-history-2',
      },
      favorite: {
        title: $t('我的收藏'),
        delLable: $t('清空收藏'),
        delAll: false,
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

    const getFuncionalPropVal = (prop, args) => {
      if (typeof prop === 'function') {
        return prop(...args);
      }

      return prop;
    };

    const isActiveItem = (item: any) => {
      return `${props.value}` === `${item[getFuncionalPropVal(props.idField, [item])]}`;
    };

    const getEllipsisItem = item => {
      const list = item[getFuncionalPropVal(props.nameField, [item])];

      return (
        <EllipsisTagList
          activeEllipsisCount={list.length > 1}
          list={list}
          {...{
            scopedSlots: {
              item: v => <span class='row-item'>{v}</span>,
            },
          }}
        />
      );
    };

    const listItemRender = (item: any) => {
      if (Array.isArray(item?.[getFuncionalPropVal(props.nameField, [item])])) {
        return (
          <div
            class={['common-row multi', { active: isActiveItem(item) }]}
            onClick={() => handleItemClick(item)}
          >
            <span class='row-left'>
              <span
                style={{
                  color: props.itemIcon?.color,
                }}
                class={['bklog-icon', props.itemIcon?.icon ?? activeMap.value.itemIcon]}
                onClick={e => handleItemIconClick(e, item)}
              />
              <span class='row-item-list'>{getEllipsisItem(item)}</span>
            </span>
            {props.showDelItem && (
              <span
                class='bklog-icon bklog-log-delete'
                onClick={e => handleDeleteItem(e, item)}
              />
            )}
          </div>
        );
      }

      return (
        <div
          class={['common-row single', { active: isActiveItem(item) }]}
          onClick={() => handleItemClick(item)}
        >
          <span class='row-left'>
            <span
              style={{
                color: props.itemIcon?.color,
              }}
              class={['bklog-icon', props.itemIcon?.icon ?? activeMap.value.itemIcon]}
              onClick={e => handleItemIconClick(e, item)}
            />
            <span class='row-item'>{item[getFuncionalPropVal(props.nameField, [item])]}</span>
          </span>
          {props.showDelItem && (
            <span
              class='bklog-icon bklog-log-delete'
              onClick={e => handleDeleteItem(e, item)}
            />
          )}
        </div>
      );
    };

    const getBodyRender = () => {
      if (props.list.length === 0 && !props.isLoading) {
        return (
          <bk-exception
            scene='part'
            type='empty'
          />
        );
      }

      return props.list.map(item => listItemRender(item));
    };

    return () => (
      <div
        class='bklog-v3-index-set-common-list'
        v-bkloading={{ isLoading: props.isLoading, size: 'mini' }}
      >
        <div class='common-header'>
          <span>
            {activeMap.value.title}（{props.list.length}/20）
          </span>
          <span
            style={{ display: activeMap.value.delAll ? 'block' : 'none' }}
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
