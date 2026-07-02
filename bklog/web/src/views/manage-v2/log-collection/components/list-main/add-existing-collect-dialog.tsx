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

import { defineComponent, ref, computed, onBeforeUnmount } from 'vue';
import useLocale from '@/hooks/use-locale';
import $http from '@/api';
import BklogPopover from '@/components/bklog-popover';
import axios from 'axios';
import './add-existing-collect-dialog.scss';

const CancelToken = axios.CancelToken;

/** 日志类型图标映射（log_access_type -> icon） */
const LOG_TYPE_ICON_MAP: Record<string, string> = {
  // 主机日志
  linux: 'bklog-icon bklog-zhujicaiji-zhujirizhi',
  // windows events日志
  winevent: 'bklog-icon bklog-zhujicaiji-windows-event-rizhi',
  // 容器文件采集
  container_file: 'bklog-icon bklog-k8s-wenjiancaiji',
  // 容器标准输出
  container_stdout: 'bklog-icon bklog-k8s-biaozhunshuchu',
  // 计算平台
  bkdata: 'bklog-icon bklog-3fang-jisuanpingtai',
  // 第三方ES
  es: 'bklog-icon bklog-3fang-es',
  // 自定义上报
  custom_report: 'bklog-icon bklog-3fang-zidingyishangbao',
};

interface IAvailableItem {
  index_set_id: number;
  name: string;
  /** 数据ID */
  bk_data_id?: number | string;
  /** 数据名 */
  bk_data_name?: string;
  /** 日志接入类型 */
  log_access_type?: string;
  /** 是否关联空间 */
  is_related_space?: boolean;
  /** 空间名称 */
  space_name?: string;
}

/**
 * 关联采集项管理弹窗
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
    // 三部分已选列表
    const addedItems = ref<IAvailableItem[]>([]);      // 新增采集项
    const existingItems = ref<IAvailableItem[]>([]);   // 默认已有采集项
    const removedItems = ref<IAvailableItem[]>([]);    // 删除的采集项
    const addListLoading = ref(false);
    const selectedListLoading = ref(false);
    const submitting = ref(false);
    const currentPage = ref(1);
    const hasMore = ref(true);
    const addListInterfaceCancel = ref<(() => void) | null>(null);
    const selectedListInterfaceCancel = ref<(() => void) | null>(null);

    const PAGE_SIZE = 50;
    const SELECTED_PAGE_SIZE = 1000;

    /** 新增+已有采集项总数 */
    const totalSelectedCount = computed(() => addedItems.value.length + existingItems.value.length);
    /** 是否有选中项 */
    const hasSelectedItems = computed(() => addedItems.value.length + existingItems.value.length + removedItems.value.length > 0);

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
            include_related_spaces: true,
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
      selectedListInterfaceCancel.value?.();
      selectedListInterfaceCancel.value = null;
    };

    /** 获取已选采集项列表 */
    const fetchSelectedList = async () => {
      if (!props.indexSetId) return;
      selectedListLoading.value = true;
      try {
        const params: Record<string, unknown> = {
          space_uid: props.spaceUid,
          page: 1,
          pagesize: SELECTED_PAGE_SIZE,
          parent_index_set_id: props.indexSetId,
          include_related_spaces: true,
        };
        const res = await $http.request(
          'collect/newCollectList',
          { data: params },
          {
            cancelToken: new CancelToken((c) => {
              selectedListInterfaceCancel.value = c;
            }),
          },
        );
        const list = (res.data?.list || []) as IAvailableItem[];
        existingItems.value = list;
        selectedListLoading.value = false;
      } catch (err: unknown) {
        if (axios.isCancel(err)) {
          return;
        }
        selectedListLoading.value = false;
        console.error('获取已选列表失败:', err);
      }
    };

    /** 弹窗打开时加载数据 */
    const handlePopoverShow = () => {
      fetchAvailableList();
      fetchSelectedList();
    };

    /** 弹窗关闭时重置状态 */
    const handlePopoverHide = () => {
      searchKeyword.value = '';
      hideNoData.value = true;
      availableList.value = [];
      addedItems.value = [];
      existingItems.value = [];
      removedItems.value = [];
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
      availableListRef.value?.scrollTo(0, 0);
    };

    /** 触底加载更多 */
    const handleScrollLoadMore = () => {
      if (!addListLoading.value && hasMore.value) {
        fetchAvailableList(true);
      }
    };

    /** 检查采集项是否已在已选列表中（新增或已有） */
    const isInSelectedList = (indexSetId: number) => {
      return addedItems.value.some(item => item.index_set_id === indexSetId)
        || existingItems.value.some(item => item.index_set_id === indexSetId);
    };

    /** 检查采集项是否在新增列表中 */
    const isInAddedList = (indexSetId: number) => {
      return addedItems.value.some(item => item.index_set_id === indexSetId);
    };

    /** 检查采集项是否在已有列表中 */
    const isInExistingList = (indexSetId: number) => {
      return existingItems.value.some(item => item.index_set_id === indexSetId);
    };

    /** 检查采集项是否在移除列表中 */
    const isInRemovedList = (indexSetId: number) => {
      return removedItems.value.some(item => item.index_set_id === indexSetId);
    };

    /** 切换采集项选中状态 - 从左侧添加到新增列表 */
    const toggleSelect = (item: IAvailableItem) => {
      const inAddedList = isInAddedList(item.index_set_id);
      const inExistingList = isInExistingList(item.index_set_id);
      const inRemovedList = isInRemovedList(item.index_set_id);

      if (inAddedList) {
        // 如果在新增列表中，从新增列表移除
        removeFromAdded(item.index_set_id);
      } else if (inExistingList) {
        // 如果在已有列表中，放入移除列表
        removeFromExisting(item);
      } else if (inRemovedList) {
        // 如果在移除列表中，恢复到已有列表
        restoreFromRemoved(item.index_set_id);
      } else {
        // 都不在，添加到新增列表
        addedItems.value.push(item);
      }
    };

    /** 从新增列表移除采集项 */
    const removeFromAdded = (indexSetId: number) => {
      const index = addedItems.value.findIndex(item => item.index_set_id === indexSetId);
      if (index !== -1) {
        addedItems.value.splice(index, 1);
      }
    };

    /** 从已有列表移除采集项，放入删除列表 */
    const removeFromExisting = (item: IAvailableItem) => {
      const index = existingItems.value.findIndex(selected => selected.index_set_id === item.index_set_id);
      if (index !== -1) {
        existingItems.value.splice(index, 1);
        removedItems.value.push(item);
      }
    };

    /** 从删除列表恢复采集项到已有列表 */
    const restoreFromRemoved = (indexSetId: number) => {
      const index = removedItems.value.findIndex(item => item.index_set_id === indexSetId);
      if (index !== -1) {
        const [item] = removedItems.value.splice(index, 1);
        if (item) {
          existingItems.value.push(item);
        }
      }
    };

    /** 确定：提交已选采集项到当前索引集 */
    const handleConfirm = async () => {
      if (addedItems.value.length === 0 && removedItems.value.length === 0) {
        popoverRef.value?.hide();
        return;
      }
      submitting.value = true;
      try {
        // 并行提交新增和删除的采集项
        const addPromise = addedItems.value.length > 0
          ? $http.request('collect/addIndexSetsToGroup', {
            params: { index_set_id: props.indexSetId },
            data: { child_index_set_ids: addedItems.value.map(item => item.index_set_id) },
          })
          : Promise.resolve();
        const removePromise = removedItems.value.length > 0
          ? $http.request('collect/removeIndexSetsFromGroup', {
            params: { index_set_id: props.indexSetId },
            data: { child_index_set_ids: removedItems.value.map(item => item.index_set_id) },
          })
          : Promise.resolve();
        await Promise.all([addPromise, removePromise]);
        emit('confirm');
        popoverRef.value?.hide();
      } catch (err) {
        console.error('提交失败:', err);
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
          <span class='popover-title'>{t('关联采集项管理')}</span>
          <i
            class='bk-icon icon-close popover-close'
            onClick={handleCancel}
          />
        </div>
        <div class='popover-body'>
          {/* 左侧：可选采集项 */}
          <div class='popover-column'>
            <div class='popover-search'>
              <bk-input
                class='search-input'
                clearable
                placeholder={t('搜索 数据ID、采集名、存储名')}
                value={searchKeyword.value}
                on-input={(val: string) => {
                  searchKeyword.value = val;
                  if (val === '') {
                    handleSearch(false);
                  }
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
            <div class='popover-field-list-wrapper'
              v-bkloading={{ isLoading: addListLoading.value && currentPage.value === 1 }}
            >
              <div
                ref={availableListRef}
                class='popover-field-list'
                onScroll={(e: Event) => {
                  const target = e.target as HTMLDivElement;
                  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 50) {
                    handleScrollLoadMore();
                  }
                }}
              >
              {availableList.value.map((item) => {
                const isSelected = isInSelectedList(item.index_set_id);
                const logTypeIcon = LOG_TYPE_ICON_MAP[item.log_access_type || ''] || '';
                return (
                  <div
                    class={{
                      'popover-field-item': true,
                      'is-selected': isSelected,
                    }}
                    key={item.index_set_id}
                    onClick={() => toggleSelect(item)}
                  >
                    {/* 左侧：多选框、日志类型图标和详细信息 */}
                    <div class='field-left-content'>
                      <bk-checkbox
                        value={isSelected}
                      />
                      {logTypeIcon && (
                        <div class='log-type-icon'>
                          <i class={logTypeIcon} />
                        </div>
                      )}
                      <div class='field-details'>
                        {/* 第一行：name */}
                        <div class='field-row-name'>
                          <span class='field-name-text'>{item.name}</span>
                        </div>
                        {/* 第二行：数据id和数据名 */}
                        {(item.bk_data_id || item.bk_data_name) && (
                          <div class='field-row-id'>
                            {item.bk_data_id && <span class='field-id-text'>[{item.bk_data_id}]</span>}
                            {item.bk_data_name && <span class='field-table-id-text'>{item.bk_data_name}</span>}
                          </div>
                        )}
                      </div>
                    </div>
                    {/* 右侧：空间类型标签 */}
                    <div class='field-right-content'>
                      {!item.is_related_space && <span class='space-tag current'>{t('当前空间')}</span>}
                      {item.is_related_space && (
                        <span
                          class='space-tag related'
                          v-bk-tooltips={{
                            content: t('关联空间') + (item.space_name ? `: ${item.space_name}` : ''),
                            placements: ['right'],
                          }}
                        >
                          {t('关联空间')}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {!addListLoading.value && availableList.value.length === 0 && (
                <bk-exception type='empty' scene='part' />
              )}
              {addListLoading.value && currentPage.value > 1 && (
                <div class='list-loading'>loading...</div>
              )}
              </div>
            </div>
          </div>

          {/* 右侧：关联预览 */}
          <div class='selected-column'>
            <div class='selected-column-header'>
              <div class='header-left'>
                <span class='header-title'>{t('关联预览')}</span>
                <i18n path='共 {0} 个' class='header-count'>
                  <span class={['count-num', { 'is-zero': totalSelectedCount.value === 0 }]}>{totalSelectedCount.value}</span>
                </i18n>
              </div>
              <bk-button
                text
                theme='primary'
                class='header-clear-btn'
                onClick={() => {
                  addedItems.value = [];
                  existingItems.value = [...existingItems.value, ...removedItems.value];
                  removedItems.value = [];
                }}
              >
                {t('重置')}
              </bk-button>
            </div>
            <div class='selected-field-list'>
              {/* 新增采集项 */}
              {addedItems.value.map(item => (
                <div class='selected-tag bklog-v3-popover-tag' key={item.index_set_id} onClick={(e: MouseEvent) => {
                  e.stopPropagation();
                  removeFromAdded(item.index_set_id);
                }}>
                  <span class='tag-label tag-added'>{t('新增')}</span>
                  <span class='tag-name'>{item.name}</span>
                  <i
                    class='bk-icon icon-close-circle-shape tag-remove'
                  />
                </div>
              ))}
              {/* 已关联的采集项 */}
              {existingItems.value.map(item => (
                <div class='selected-tag bklog-v3-popover-tag' key={item.index_set_id} onClick={(e: MouseEvent) => {
                  e.stopPropagation();
                  removeFromExisting(item);
                }}>
                  <span class='tag-name'>{item.name}</span>
                  <i
                    class='bk-icon icon-close-circle-shape tag-remove'
                  />
                </div>
              ))}
              {/* 删除的采集项 */}
              {removedItems.value.map(item => (
                <div class='selected-tag bklog-v3-popover-tag' key={item.index_set_id} onClick={(e: MouseEvent) => {
                  e.stopPropagation();
                  restoreFromRemoved(item.index_set_id);
                }}>
                  <span class='tag-label tag-removed'>{t('移除')}</span>
                  <span class='tag-name name-removed'>{item.name}</span>
                  <i
                    class='bk-icon bklog-icon bklog-return'
                  />
                </div>
              ))}
              {/* 未选择采集项 */}
              {!hasSelectedItems.value && (
                <bk-exception class='exception-wrap-item exception-part' type='empty' scene='part'>
                  <span>{t('请先在左侧选择')}</span>
                </bk-exception>
              )}
            </div>
          </div>
        </div>

        {/* 底部按钮 */}
        <div class='popover-actions'>
          <bk-button theme='primary' onClick={handleConfirm} loading={submitting.value || selectedListLoading.value}>
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
