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

import { computed, defineComponent, onMounted, PropType, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import IndexSetList from './index-set-list';
import './content.scss';
import useChoice, { IndexSetType } from './use-choice';
import CommonList from './common-list';

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
  },
  emits: ['type-change', 'value-change'],
  setup(props, { emit }) {
    const { $t } = useLocale();
    const historyList = ref([]);

    const {
      getHistoryList,
      getFavoriteList,
      handleHistoryItemClick,
      handleValueChange,
      handleDeleteHistory,
      cancelFavorite,
      historyLoading,
      favoriteLoading,
      favoriteList,
    } = useChoice(props, { emit });

    const handleDeleteHistoryItem = item => {
      handleDeleteHistory(item).then(resp => {
        if (resp !== undefined) {
          historyList.value = resp;
        }
      });
    };

    const indexSetActiveId = computed(() => {
      if (['union', 'single'].includes(props.activeId)) {
        return props.activeId;
      }

      return props.type;
    });

    const renderIndexSetList = () => {
      return (
        <IndexSetList
          list={props.list}
          type={indexSetActiveId.value}
          value={props.value}
          textDir={props.textDir}
          on-value-change={handleValueChange}
        ></IndexSetList>
      );
    };

    const renderHistoryList = () => (
      <CommonList
        list={historyList.value}
        isLoading={historyLoading.value}
        type='history'
        on-value-click={handleHistoryItemClick}
        on-delete={handleDeleteHistoryItem}
      ></CommonList>
    );

    const renderFavoriteList = () => (
      <CommonList
        list={favoriteList.value}
        isLoading={favoriteLoading.value}
        showDelItem={false}
        type='favorite'
        itemIcon={{
          color: '#F8B64F',
          onClick: (e, item) => {
            e.stopPropagation();
            cancelFavorite(item);
          },
        }}
      ></CommonList>
    );

    const tabList = computed(() => [
      { name: $t('单选'), id: 'single', render: renderIndexSetList },
      { name: $t('多选'), id: 'union', render: renderIndexSetList },
      { name: $t('历史记录'), id: 'history', render: renderHistoryList },
      { name: $t('我的收藏'), id: 'favorite', render: renderFavoriteList },
    ]);

    const activeTab = computed(() => tabList.value.find(item => item.id === props.activeId));

    const handleTabItemClick = (e: MouseEvent, item: { name: string; id: string }) => {
      if (item.id === 'history') {
        getHistoryList().then(resp => {
          historyList.value = resp;
        });
      }

      if (item.id === 'favorite') {
        getFavoriteList();
      }

      emit('type-change', item.id);
    };

    onMounted(() => {
      if (props.activeId === 'history') {
        getHistoryList().then(resp => {
          historyList.value = resp;
        });
      }

      if (props.activeId === 'favorite') {
        getFavoriteList();
      }
    });

    return () => (
      <div class='bklog-v3-content-root'>
        <div class='content-header'>
          <div class='bklog-v3-tabs'>
            {tabList.value.map(item => (
              <span
                class={[{ 'is-active': props.activeId === item.id }, 'tab-item']}
                key={item.id}
                onClick={e => handleTabItemClick(e, item)}
              >
                {item.name}
              </span>
            ))}
          </div>
          <div class='bklog-v3-keys'>
            <span class='key-item'>
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
            </span>
          </div>
        </div>
        {activeTab.value.render?.()}
      </div>
    );
  },
});
