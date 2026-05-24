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
import { computed, defineComponent, nextTick, ref, watch } from 'vue';

import http from '@/api';
import { getOsCommandLabel } from '@/common/util';
import { t } from '@/hooks/use-locale';
import store from '@/store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import ItemSkeleton from '@/skeleton/item-skeleton';

import type { IGrokItem } from '../types';

import './grok-popover-list.scss';

type DebugResultRow = {
  field: string;
  value: string;
};

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
  emits: ['select', 'cancel'],
  setup(props, { emit, expose }) {
    const listRef = ref<HTMLDivElement>();
    const searchKeyword = ref('');
    const list = ref<IGrokItem[]>([]);
    const isLoading = ref(false);
    const isLoadingMore = ref(false);
    const debugLoading = ref(false);
    const page = ref(1);
    const pagesize = 20;
    const total = ref(0);
    const activeIndex = ref(-1);
    const debugResult = ref<DebugResultRow[]>([]);
    let searchTimer: ReturnType<typeof setTimeout> | null = null;
    let scrollThrottleTimer: ReturnType<typeof setTimeout> | null = null;

    const hasMore = computed(() => list.value.length < total.value);
    const activeItem = computed(() => list.value[activeIndex.value]);

    const formatDebugResult = (data: Record<string, unknown> | null): DebugResultRow[] => {
      if (!data) return [];
      return Object.entries(data)
        .filter(([key]) => key !== '_matched')
        .map(([field, value]) => ({
          field,
          value: typeof value === 'string' ? value : JSON.stringify(value),
        }));
    };

    const selectIndex = (index: number) => {
      activeIndex.value = index;
      scrollToActiveItem();
      nextTick(() => {
        debugResult.value = formatDebugResult(activeItem.value.sample_result);
      });
    };

    const updateActiveByList = () => {
      activeIndex.value = list.value.length ? 0 : -1;
      nextTick(() => {
        debugResult.value = formatDebugResult(activeItem.value?.sample_result || null);
      });
    };

    // 获取 Grok 列表数据
    const fetchGrokList = async (append = false) => {
      if (isLoading.value || isLoadingMore.value) return;

      if (!append) {
        page.value = 1;
      }

      if (append && !hasMore.value) return;

      if (append) {
        isLoadingMore.value = true;
      } else {
        isLoading.value = true;
      }
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            page: page.value,
            pagesize,
            ...(searchKeyword.value && { keyword: searchKeyword.value }),
          },
        };
        const response = await http.request('grok/searchGrok', params);
        const newList = response.data?.list || [];
        total.value = response.data?.total || 0;

        if (append) {
          list.value = [...list.value, ...newList];
        } else {
          list.value = newList;
          updateActiveByList();
        }
      } catch (error) {
        console.warn('获取 Grok 列表失败:', error);
      } finally {
        isLoading.value = false;
        isLoadingMore.value = false;
      }
    };

    // 监听滚动事件，触底分页加载，做简单节流
    const handleScroll = (e: Event) => {
      if (scrollThrottleTimer) return;

      scrollThrottleTimer = setTimeout(() => {
        scrollThrottleTimer = null;
        const target = e.target as HTMLDivElement;
        const { scrollTop, scrollHeight, clientHeight } = target;

        if (scrollHeight - scrollTop - clientHeight < 50 && hasMore.value && !isLoading.value && !isLoadingMore.value) {
          page.value += 1;
          fetchGrokList(true);
        }
      }, 200);
    };

    const handleSearch = () => {
      if (searchTimer) {
        clearTimeout(searchTimer);
        searchTimer = null;
      }
      fetchGrokList();
    };

    const handleSearchChange = (val: string) => {
      searchKeyword.value = val;
      if (searchTimer) {
        clearTimeout(searchTimer);
      }
      searchTimer = setTimeout(() => {
        fetchGrokList();
      }, 300);
    };

    const handleConfirm = () => {
      if (activeItem.value) {
        emit('select', activeItem.value);
      }
    };

    const handleCancel = () => {
      emit('cancel');
    };

    // 处理行点击 - 只高亮，不触发选择
    const handleRowClick = (_item: IGrokItem, index: number) => {
      selectIndex(index);
    };

    // 处理键盘导航
    const handleKeydown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleConfirm();
        return;
      }

      if (!list.value.length) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          selectIndex(activeIndex.value === -1 ? 0 : Math.min(activeIndex.value + 1, list.value.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          selectIndex(activeIndex.value === -1 ? 0 : Math.max(activeIndex.value - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          selectIndex(activeIndex.value === -1 ? 0 : activeIndex.value);
          break;
      }
    };

    // 滚动到激活项
    const scrollToActiveItem = () => {
      nextTick(() => {
        if (!listRef.value) return;
        const activeItemElement = listRef.value.querySelector('.grok-popover-list-row.active');
        if (activeItemElement) {
          activeItemElement.scrollIntoView({ block: 'nearest' });
        }
      });
    };

    // 监听 visible 变化，打开时加载数据
    watch(
      () => props.visible,
      (val) => {
        if (val) {
          searchKeyword.value = props.keyword;
          fetchGrokList();
        }
      },
      { immediate: true },
    );

    // 监听 keyword 变化，重新搜索
    watch(
      () => props.keyword,
      (val) => {
        searchKeyword.value = val;
        if (props.visible) {
          handleSearchChange(val);
        }
      },
    );

    // 重置状态
    const reset = () => {
      searchKeyword.value = '';
      list.value = [];
      debugResult.value = [];
      page.value = 1;
      total.value = 0;
      activeIndex.value = -1;
      isLoading.value = false;
      isLoadingMore.value = false;
    };

    expose({
      handleKeydown,
      reset,
      fetchGrokList,
    });

    const shortcutLabel = computed(() => {
      return `${getOsCommandLabel()} + Enter ${t('确认')}`;
    });

    const renderListSkeleton = (count = 6) => (
      <div class='grok-popover-list-skeleton'>
        <ItemSkeleton
          rows={count}
          columns={1}
          rowHeight='40px'
          gap='8px'
          widths={['100%']}
          type='text'
        />
      </div>
    );

    const renderDetailSkeleton = () => (
      <div class='grok-popover-debug-skeleton'>
        <ItemSkeleton
          rows={6}
          columns={1}
          rowHeight='20px'
          gap='14px'
          widths={['32%', '100%', '24%', '100%', '24%', '100%']}
          type='text'
        />
      </div>
    );

    return () => (
      <div class='grok-popover-list'>
        <div class='grok-popover-list-left'>
          {/* 搜索框 */}
          <div class='grok-popover-search'>
            <bk-input
              clearable
              right-icon='bk-icon icon-search'
              value={searchKeyword.value}
              placeholder={t('输入关键字搜索')}
              on-change={handleSearchChange}
              on-enter={handleSearch}
            />
          </div>
          {/* 列表内容 */}
          <div
            ref={listRef}
            class='grok-popover-list-body'
            onScroll={handleScroll}
          >
            {isLoading.value && renderListSkeleton()}
            {!isLoading.value && list.value.map((item, index) => (
              <div
                key={item.id}
                class={['grok-popover-list-row', { active: index === activeIndex.value }]}
                onClick={() => handleRowClick(item, index)}
              >
                <div class='grok-popover-list-name'>{item.name}</div>
                <div class='grok-popover-list-description'>{item.description}</div>
              </div>
            ))}

            {isLoadingMore.value && (
              <div class='grok-popover-list-more-skeleton'>
                {renderListSkeleton(2)}
              </div>
            )}

            {/* 空状态 */}
            {!isLoading.value && list.value.length === 0 && (
              <div class='grok-popover-list-empty'>{t('暂无数据')}</div>
            )}
          </div>
        </div>

        {/* 右侧调试结果 */}
        <div class='grok-popover-list-right'>
          <div class='grok-popover-debug'>
            {isLoading.value ? renderDetailSkeleton() : activeItem.value ? (
              <div class='grok-popover-debug-content'>
                {/* name */}
                <div class='grok-popover-debug-name'>{activeItem.value.name}</div>

                {/* 定义 */}
                <div class='grok-popover-debug-section'>
                  <div class='grok-popover-debug-label'>{t('定义')}</div>
                  <div class='grok-popover-debug-value grok-popover-debug-pattern'>
                    {activeItem.value.pattern || '--'}
                  </div>
                </div>

                {/* 样例 */}
                <div class='grok-popover-debug-section'>
                  <div class='grok-popover-debug-label'>{t('样例')}</div>
                  <div class='grok-popover-debug-value grok-popover-debug-sample'>
                    {activeItem.value.sample || '--'}
                  </div>
                </div>

                {/* 输出结果 */}
                <div class='grok-popover-debug-section'>
                  <div class='grok-popover-debug-label'>{t('输出结果')}</div>
                  {debugResult.value.length > 0 ? (
                    <table class='grok-popover-debug-table'>
                      <thead>
                        <tr>
                          <th>{t('字段名')}</th>
                          <th>{t('解析结果')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {debugResult.value.map(row => (
                          <tr key={row.field}>
                            <td class='grok-popover-debug-field'>{row.field}</td>
                            <td class='grok-popover-debug-value'>{row.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    !debugLoading.value && (
                      <div class='grok-popover-debug-empty'>{t('暂无调试结果')}</div>
                    )
                  )}
                </div>
              </div>
            ) : (
              <div class='grok-popover-debug-empty'>{t('请选择一条 Grok 模式查看调试结果')}</div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div class='grok-popover-list-footer'>
          <div class='grok-popover-list-shortcut'>
            <span class='bklog-icon bklog-arrow-down-filled label up'></span>
            <span class='bklog-icon bklog-arrow-down-filled label'></span>
            <span class='value'>{t('移动光标')}</span>
          </div>
          <div class='grok-popover-list-actions'>
            <bk-button
              size='small'
              theme='primary'
              disabled={!activeItem.value}
              onClick={handleConfirm}
            >
              {shortcutLabel.value}
            </bk-button>
            <bk-button
              size='small'
              onClick={handleCancel}
            >
              {t('取消')}
            </bk-button>
          </div>
        </div>
      </div>
    );
  },
});
