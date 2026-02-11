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
import { defineComponent, ref, watch, nextTick } from 'vue';

import http from '@/api';
import { t } from '@/hooks/use-locale';
import store from '@/store';
import { BK_LOG_STORAGE } from '@/store/store.type';

import type { IGrokItem } from '../types';

import './grok-popover-list.scss';

export default defineComponent({
  name: 'GrokPopoverList',
  props: {
    keyword: {
      type: String,
      default: '',
    },
    visible: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['select'],
  setup(props, { emit, expose }) {
    const listRef = ref<HTMLDivElement>();
    const list = ref<IGrokItem[]>([]);
    const isLoading = ref(false);
    const page = ref(1);
    const pagesize = 20;
    const hasMore = ref(true);
    const total = ref(0);
    const activeIndex = ref(-1);

    // 获取 Grok 列表数据
    const fetchGrokList = async (append = false) => {
      if (isLoading.value) return;
      if (!append) {
        page.value = 1;
        hasMore.value = true;
      }

      if (!hasMore.value) return;

      isLoading.value = true;
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            page: page.value,
            pagesize,
            ...(props.keyword && { keyword: props.keyword }),
          },
        };
        const response = await http.request('grok/getGrokList', params);
        const newList = response.data?.list || [];
        total.value = response.data?.total || 0;

        if (append) {
          list.value = [...list.value, ...newList];
        } else {
          list.value = newList;
          activeIndex.value = -1;
        }

        // 判断是否还有更多数据
        hasMore.value = list.value.length < total.value;
      } catch (error) {
        console.warn('获取 Grok 列表失败:', error);
      } finally {
        isLoading.value = false;
      }
    };

    // 监听滚动事件，实现触底加载
    const handleScroll = (e: Event) => {
      const target = e.target as HTMLDivElement;
      const { scrollTop, scrollHeight, clientHeight } = target;

      // 距离底部小于 50px 时加载更多
      if (scrollHeight - scrollTop - clientHeight < 50 && hasMore.value && !isLoading.value) {
        page.value += 1;
        fetchGrokList(true);
      }
    };

    // 选择某一项
    const handleSelect = (item: IGrokItem) => {
      emit('select', item);
    };

    // 处理行点击
    const handleRowClick = (item: IGrokItem, index: number) => {
      activeIndex.value = index;
      handleSelect(item);
    };

    // 处理键盘导航
    const handleKeydown = (e: KeyboardEvent) => {
      if (!list.value.length) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          // 第一次按下时选中第一项
          if (activeIndex.value === -1) {
            activeIndex.value = 0;
          } else {
            activeIndex.value = Math.min(activeIndex.value + 1, list.value.length - 1);
          }
          scrollToActiveItem();
          break;
        case 'ArrowUp':
          e.preventDefault();
          // 第一次按下时选中第一项
          if (activeIndex.value === -1) {
            activeIndex.value = 0;
          } else {
            activeIndex.value = Math.max(activeIndex.value - 1, 0);
          }
          scrollToActiveItem();
          break;
        case 'Enter':
          e.preventDefault();
          if (activeIndex.value >= 0 && activeIndex.value < list.value.length) {
            handleSelect(list.value[activeIndex.value]);
          }
          break;
      }
    };

    // 滚动到激活项
    const scrollToActiveItem = () => {
      nextTick(() => {
        if (!listRef.value) return;
        const activeItem = listRef.value.querySelector('.grok-popover-list-row.active');
        if (activeItem) {
          activeItem.scrollIntoView({ block: 'nearest' });
        }
      });
    };

    // 监听 visible 变化，打开时加载数据
    watch(
      () => props.visible,
      (val) => {
        if (val) {
          fetchGrokList();
        }
      },
      { immediate: true },
    );

    // 监听 keyword 变化，重新搜索
    watch(
      () => props.keyword,
      () => {
        if (props.visible) {
          fetchGrokList();
        }
      },
    );

    // 重置状态
    const reset = () => {
      list.value = [];
      page.value = 1;
      hasMore.value = true;
      activeIndex.value = -1;
    };

    expose({
      handleKeydown,
      reset,
      fetchGrokList,
    });

    return () => (
      <div class='grok-popover-list'>
        {/* 列表内容 */}
        <div
          ref={listRef}
          class='grok-popover-list-body'
          v-bkloading={{ isLoading: isLoading.value && page.value === 1, zIndex: 10 }}
          onScroll={handleScroll}
        >
          {list.value.map((item, index) => (
            <div
              key={item.id}
              class={['grok-popover-list-row', { active: index === activeIndex.value }]}
              onClick={() => handleRowClick(item, index)}
              v-bk-tooltips={{
                placement: 'right',
                content: `${t('样例')}: ${item.sample || '--'}`,
                appendTo: () => document.body,
              }}
            >
              <div class='grok-popover-list-cell name'>{item.name}</div>
              <div
                class='grok-popover-list-cell description'
              >
                {item.description || '--'}
              </div>
              <div
                class='grok-popover-list-cell pattern'
              >
                {item.pattern}
              </div>
            </div>
          ))}

          {/* 加载中状态 */}
          {isLoading.value && (
            <div class='grok-popover-list-loading'>
              <bk-spin/>
            </div>
          )}

          {/* 空状态 */}
          {!isLoading.value && list.value.length === 0 && <div class='grok-popover-list-empty'>{t('暂无数据')}</div>}

          {/* 没有更多数据 */}
          {!hasMore.value && list.value.length > 0 && <div class='grok-popover-list-no-more'>{t('没有更多数据')}</div>}
        </div>
      </div>
    );
  },
});
