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

import { computed, defineComponent, onMounted, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import { useRoute } from 'vue-router/composables';

import { BK_LOG_STORAGE } from '../../../../store/store.type';
// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import CommonList from './common-list';
// #else
// #code const CommonList = () => null;
// #endif
import IndexSetList from './index-set-list';
import useChoice, { type IndexSetType } from './use-choice';

import './content.scss';

export default defineComponent({
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String as PropType<IndexSetType>,
      default: 'single',
    },
    activeId: {
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
    zIndex: {
      type: Number,
      default: 101,
    },
  },
  emits: ['type-change', 'value-change', 'auth-request'],
  setup(props, { emit, expose }) {
    const { $t } = useLocale();
    const route = useRoute();

    const {
      requestHistoryList,
      requestFavoriteList,
      handleHistoryItemClick,
      handleValueChange,
      handleDeleteHistory,
      cancelFavorite,
      favoriteIndexSet,
      historyLoading,
      favoriteLoading,
      favoriteList,
      historyList,
      unionListValue,
    } = useChoice(props, { emit });

    const favoriteId = computed(() => {
      return route.query[BK_LOG_STORAGE.FAVORITE_ID] as string;
    });

    const historyId = computed(() => {
      return route.query[BK_LOG_STORAGE.HISTORY_ID] as string;
    });

    /**
     * 当前选中的索引集
     * 根据type判断，如果当前是single，判断value是否只有一个
     * 如果只有一个，返回这个值，否则说明是从多选Tab切换到单选，此时返回空数组
     * 如果是union，返回 unionListValue
     */
    const currentValue = computed(() => {
      if (props.type === 'single') {
        if (props.value.length > 1) {
          return [];
        }

        return props.value;
      }

      return unionListValue.value;
    });

    const handleFavoriteItemClick = item => {
      if (item.index_set_type === 'single') {
        handleValueChange([`${item.index_set_id}`], 'single', item.index_set_id);
        return;
      }

      handleValueChange(
        item.index_set_ids.map(id => `${id}`),
        'union',
        item.id,
      );
    };

    const indexSetActiveId = computed(() => {
      if (['union', 'single'].includes(props.activeId)) {
        return props.activeId;
      }

      return props.type;
    });

    const handleFavoriteChange = (args, isFavorite = true) => {
      if (isFavorite) {
        favoriteIndexSet(args);
        return;
      }

      cancelFavorite(args);
    };

    const renderIndexSetList = () => {
      return (
        <IndexSetList
          list={props.list}
          spaceUid={props.spaceUid}
          textDir={props.textDir}
          type={indexSetActiveId.value}
          value={currentValue.value}
          on-auth-request={item => emit('auth-request', item)}
          on-favorite-change={handleFavoriteChange}
          on-value-change={handleValueChange}
        />
      );
    };

    // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
    const renderHistoryList = () => (
      <CommonList
        idField='id'
        isLoading={historyLoading.value}
        list={historyList.value}
        nameField={item => (item.index_set_type === 'single' ? 'index_set_name' : 'index_set_names')}
        type='history'
        value={historyId.value}
        on-delete={handleDeleteHistory}
        on-value-click={handleHistoryItemClick}
      />
    );

    /**
     * 我的收藏渲染
     * @returns
     */
    const renderFavoriteList = () => (
      <CommonList
        itemIcon={{
          color: '#F8B64F',
          onClick: (e, item) => {
            e.stopPropagation();
            cancelFavorite(item, 'favorite');
          },
        }}
        idField={item => (item.index_set_type === 'single' ? 'index_set_id' : 'id')}
        isLoading={favoriteLoading.value}
        list={favoriteList.value}
        nameField={item => (item.index_set_type === 'single' ? 'index_set_name' : 'name')}
        showDelItem={false}
        type='favorite'
        value={favoriteId.value}
        on-delete={() => alert('API not support')}
        on-value-click={handleFavoriteItemClick}
      />
    );
    // #endif

    const tabList = computed(() => [
      { name: $t('单选'), id: 'single', render: renderIndexSetList },
      { name: $t('多选'), id: 'union', render: renderIndexSetList },
      // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
      { name: $t('历史记录'), id: 'history', render: renderHistoryList },
      { name: $t('我的收藏'), id: 'favorite', render: renderFavoriteList },
      // #endif
    ]);

    const activeTab = computed(() => tabList.value.find(item => item.id === props.activeId));
    const handleTabItemClick = (_e: MouseEvent, item: { name: string; id: string }) => {
      if (item.id === 'history') {
        requestHistoryList();
      }

      if (item.id === 'favorite') {
        requestFavoriteList(null);
      }

      emit('type-change', item.id);
    };

    onMounted(() => {
      if (props.activeId === 'history') {
        requestHistoryList();
      }

      if (props.activeId === 'favorite') {
        requestFavoriteList(null);
      }
    });

    expose({
      resetUnionList: () => (unionListValue.value = [...props.value]),
    });

    return () => (
      <div
        style={{ zIndex: props.zIndex }}
        class='bklog-v3-content-root'
      >
        <div class='content-header'>
          <div class='bklog-v3-tabs'>
            {tabList.value.map(item => (
              <span
                key={item.id}
                class={[{ 'is-active': props.activeId === item.id }, 'tab-item']}
                onClick={e => handleTabItemClick(e, item)}
              >
                {item.name}
              </span>
            ))}
          </div>
          <div class='bklog-v3-keys'>
            {/* <span class='key-item'>
              <span class='key-code text'>tab</span>
              <span class='key-name'>快速切换标签</span>
            </span>
            <span class='key-item'>
              <span class='key-code up-icon bklog-icon bklog-arrow-down-filled-2'></span>
              <span class='key-code bklog-icon bklog-arrow-down-filled-2'></span>
              <span class='key-name'>移动光标</span>
            </span>
            <span class='key-item'>
              <span class='key-code text'>enter</span>
              <span class='key-name'>选中</span>
            </span> */}
          </div>
        </div>
        {activeTab.value.render?.()}
      </div>
    );
  },
});
