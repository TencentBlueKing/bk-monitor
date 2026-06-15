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

import { defineComponent, ref, onBeforeUnmount } from 'vue';
import useLocale from '@/hooks/use-locale';
import $http from '@/api';
import BklogPopover from '@/components/bklog-popover';
import axios from 'axios';
import { messageWarn } from '@/common/bkmagic';
import './add-existing-collect-dialog.scss';

const CancelToken = axios.CancelToken;

interface IAvailableItem {
  index_set_id: number;
  name: string;
}

/**
 * 添加已有采集项弹窗
 * 包裹触发按钮，点击弹出左右两栏采集项选择面板
 */
export default defineComponent({
  name: 'AddExistingCollectDialog',
  props: {
    /** 当前选中的索引集 ID */
    indexSetId: {
      type: [String, Number],
      default: '',
    },
    spaceUid: {
      type: String,
      default: '',
    },
  },
  emits: ['confirm'],

  setup(props, { emit, slots }) {
    const { t } = useLocale();

    const popoverRef = ref<any>(null);
    const availableListRef = ref<HTMLDivElement | null>(null);
    const searchKeyword = ref('');
    const hideNoData = ref(true);
    const availableList = ref<IAvailableItem[]>([]);
    const selectedItemsList = ref<IAvailableItem[]>([]);
    const addListLoading = ref(false);
    const submitting = ref(false);
    const currentPage = ref(1);
    const hasMore = ref(true);
    const PAGE_SIZE = 50;
    const addListInterfaceCancel = ref<(() => void) | null>(null);

    /** 获取可选采集项列表 */
    const fetchAvailableList = async (isLoadMore = false) => {
      if (!props.indexSetId) return;
      if (!isLoadMore) {
        currentPage.value = 1;
        hasMore.value = true;
      }
      if (!isLoadMore || hasMore.value) {
        addListInterfaceCancel.value?.();
        addListLoading.value = true;
        try {
          const params: Record<string, unknown> = {
            space_uid: props.spaceUid,
            page: currentPage.value,
            pagesize: PAGE_SIZE,
            exclude_parent_index_set_id: props.indexSetId,
          };
          if (searchKeyword.value) {
            params.keyword = searchKeyword.value;
          }
          if (hideNoData.value) {
            params.exclude_not_data = true;
            params.conditions = [{ key: 'status', value: ['running', 'success', 'failed'] }];
          }
          const res = await $http.request(
            'collect/newCollectList',
            { data: params },
            {
              cancelToken: new CancelToken((c) => {
                addListInterfaceCancel.value = c;
              }),
            },
          );
          const list = (res.data?.list || []) as IAvailableItem[];
          if (isLoadMore) {
            availableList.value = [...availableList.value, ...list];
          } else {
            availableList.value = list;
          }
          hasMore.value = list.length >= PAGE_SIZE;
          currentPage.value += 1;
          addListLoading.value = false;
        } catch (err: unknown) {
          // 忽略取消请求的错误
          if (axios.isCancel(err)) {
            return;
          }
          addListLoading.value = false;
          console.error(err);
          if (!isLoadMore) {
            availableList.value = [];
          }
        }
      }
    };

    /** 取消请求 */
    const cancelRequest = () => {
      addListInterfaceCancel.value?.();
      addListInterfaceCancel.value = null;
    };

    /** 弹窗打开时加载数据 */
    const handlePopoverShow = () => {
      fetchAvailableList();
    };

    /** 弹窗关闭时重置状态 */
    const handlePopoverHide = () => {
      searchKeyword.value = '';
      hideNoData.value = true;
      selectedItemsList.value = [];
      availableList.value = [];
      currentPage.value = 1;
      hasMore.value = true;
      submitting.value = false;
      cancelRequest();
    };

    /** 搜索框确认搜索 */
    const handleSearch = (checkEmpty = true) => {
      if (checkEmpty && searchKeyword.value === '') {
        return;
      }
      availableListRef.value?.scrollTo(0, 0);
      fetchAvailableList();
    };

    /** 隐藏无数据/停用 复选框变化 */
    const handleHideNoDataChange = (val: boolean) => {
      hideNoData.value = val;
      fetchAvailableList();
    };

    /** 触底加载更多 */
    const handleScrollLoadMore = () => {
      if (!addListLoading.value && hasMore.value) {
        fetchAvailableList(true);
      }
    };

    /** 切换采集项选中状态 */
    const toggleSelect = (item: IAvailableItem) => {
      const index = selectedItemsList.value.findIndex(selected => selected.index_set_id === item.index_set_id);
      if (index !== -1) {
        selectedItemsList.value.splice(index, 1);
      } else {
        selectedItemsList.value.push(item);
      }
    };

    /** 从已选中移除采集项 */
    const removeSelected = (id: number) => {
      const index = selectedItemsList.value.findIndex(selected => selected.index_set_id === id);
      if (index !== -1) {
        selectedItemsList.value.splice(index, 1);
      }
    };

    /** 确定：提交已选采集项到当前索引集 */
    const handleConfirm = async () => {
      if (selectedItemsList.value.length === 0) {
        messageWarn(t('已选采集项不能为空'));
        return;
      }
      submitting.value = true;
      try {
        const ids = selectedItemsList.value.map(item => item.index_set_id);
        const res = await $http.request('collect/addIndexSetsToGroup', {
          params: { index_set_id: props.indexSetId },
          data: { child_index_set_ids: ids },
        });
        if (res.result) {
          emit('confirm');
          cancelRequest();
          popoverRef.value?.hide();
        }
      } finally {
        submitting.value = false;
      }
    };

    /** 取消关闭弹窗 */
    const handleCancel = () => {
      cancelRequest();
      popoverRef.value?.hide();
    };

    const handleBeforeHide = (e: MouseEvent) => {
      if ((e.target as HTMLElement)?.closest?.('.bklog-v3-popover-tag')) {
        return false;
      }
      return true;
    };

    const renderContent = () => (
      <div class='add-existing-collect-popover'>
        <div class='popover-header'>
          <span class='popover-title'>{t('添加已有采集项')}</span>
          <i
            class='bk-icon icon-close popover-close'
            onClick={handleCancel}
          />
        </div>
        <div class='popover-body'>
          {/* 左侧：可选采集项 */}
          <div class='popover-column'>
            <div class='popover-column-title'>
              <span>{t('可选采集项')}</span>
              <i18n path='点击添加到 {0}' class='sub-title'>
                <span>{`<${t('已选采集项')}>`}</span>
              </i18n>
            </div>
            <div class='popover-search'>
              <bk-input
                class='search-input'
                clearable
                placeholder={t('搜索 采集项')}
                value={searchKeyword.value}
                on-input={(val: string) => {
                  searchKeyword.value = val;
                }}
                on-enter={() => handleSearch(true)}
                on-clear={() => handleSearch(false)}
                on-right-icon-click={() => handleSearch(true)}
                right-icon='bk-icon icon-search'
              />
              <bk-checkbox
                class='hide-checkbox'
                value={hideNoData.value}
                onChange={handleHideNoDataChange}
              >
                {t('隐藏无数据')} / {t('停用')}
              </bk-checkbox>
            </div>
            <div
              ref={availableListRef}
              class='popover-field-list'
              v-bkloading={{ isLoading: addListLoading.value }}
              onScroll={(e: MouseEvent) => {
                const target = e.target as HTMLDivElement;
                if (target.scrollTop + target.clientHeight >= target.scrollHeight - 10) {
                  handleScrollLoadMore();
                }
              }}
            >
              {availableList.value.map(item => {
                const isSelected = selectedItemsList.value.some(selected => selected.index_set_id === item.index_set_id);
                return (
                  <div
                    class={{
                      'popover-field-item': true,
                      'is-selected': isSelected,
                    }}
                    key={item.index_set_id}
                    onClick={() => toggleSelect(item)}
                  >
                    <bk-checkbox
                      value={isSelected}
                    />
                    <span class='field-id'>#{item.index_set_id}</span>
                    <span class='field-name'>{item.name}</span>
                  </div>
                );
              })}
              {!addListLoading.value && availableList.value.length === 0 && (
                <bk-exception type='empty' scene='part' />
              )}
              {addListLoading.value && currentPage.value > 1 && hasMore.value && (
                <div class='list-loading'>loading...</div>
              )}
            </div>
          </div>

          {/* 分割线 */}
          <div class='popover-divider' />

          {/* 右侧：已选采集项 */}
          <div class='popover-column'>
            <div class='popover-column-title'>
              <span>{t('已选采集项')}</span>
            </div>
            <div class='popover-field-list selected-field-list'>
              {selectedItemsList.value.map(item => (
                <div class='selected-tag bklog-v3-popover-tag' key={item.index_set_id} onClick={() => removeSelected(item.index_set_id)}>
                  <span class='tag-id'>#{item.index_set_id}</span>
                  <span class='tag-name'>{item.name}</span>
                  <i
                    class='bk-icon icon-close-circle-shape tag-remove'
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 底部按钮 */}
        <div class='popover-actions'>
          <bk-button theme='primary' onClick={handleConfirm} loading={submitting.value}>
            {t('确定')}
          </bk-button>
          <bk-button onClick={handleCancel} disabled={submitting.value}>{t('取消')}</bk-button>
        </div>
      </div>
    );

    onBeforeUnmount(() => {
      cancelRequest();
    });

    return () => (
      <BklogPopover
        ref={popoverRef}
        options={{
          arrow: false,
          hideOnClick: false,
          interactive: true,
          placement: 'bottom-start',
          theme: 'light',
          maxWidth: 'none',
          onShown: handlePopoverShow,
          onHidden: handlePopoverHide,
        }}
        trigger='click'
        content-class='add-existing-collect-popover-content'
        content={renderContent}
        beforeHide={handleBeforeHide}
      >
        {slots.default?.()}
      </BklogPopover>
    );
  },
});
