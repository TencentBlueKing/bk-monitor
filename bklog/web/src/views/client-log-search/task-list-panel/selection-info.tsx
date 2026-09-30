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

import { defineComponent, nextTick, ref } from 'vue';

import SelectedTaskTable from './selected-task-table';
import { MAX_BATCH_DOWNLOAD_TASKS } from '../types';
import type { LogItem } from '../types';
import BklogPopover from '@/components/bklog-popover';
import { t } from '@/hooks/use-locale';

export default defineComponent({
  name: 'TaskSelectionInfo',
  props: {
    /** 当前批量选中的已采集任务 */
    selectedItems: {
      type: Array as () => LogItem[],
      default: () => [],
    },
    /** 搜索使用的时区，传给悬停详情表格 */
    timezone: {
      type: String,
      default: '',
    },
  },
  /** 全选、清空、移出和下载操作均由页面层处理 */
  emits: ['select-all', 'clear', 'remove', 'download'],
  setup(props, { emit }) {
    const popoverRef = ref<{ hide: () => void; update: (force?: boolean) => boolean } | null>(null);
    /** 表格仅在浮层显示期间挂载，避免隐藏时数据变化按 0 宽度布局后再次显示未铺满 */
    const isPopoverVisible = ref(false);

    const handlePopoverShow = () => {
      isPopoverVisible.value = true;
      nextTick(() => popoverRef.value?.update());
    };

    const handlePopoverHidden = () => {
      isPopoverVisible.value = false;
    };

    const handleRemove = (item: LogItem) => {
      if (props.selectedItems.length === 1) popoverRef.value?.hide();
      emit('remove', item);
    };

    /** 渲染悬停浮层中的已选任务列表 */
    const renderPopoverContent = () => (
      <div class='task-selection-popover-content'>
        <div class='task-selection-popover-title'>{t('已选 {0} 个任务', [props.selectedItems.length])}</div>
        {isPopoverVisible.value && (
          <SelectedTaskTable
            items={props.selectedItems}
            timezone={props.timezone}
            compact
            removable
            on-remove={handleRemove}
          />
        )}
      </div>
    );

    return () => {
      const count = props.selectedItems.length;
      const isOverLimit = count > MAX_BATCH_DOWNLOAD_TASKS;

      return (
        <BklogPopover
          ref={popoverRef}
          class='task-selection-popover-anchor'
          contentClass='task-selection-popover-root'
          trigger='hover'
          options={
            {
              appendTo: document.body,
              arrow: true,
              interactive: true,
              maxWidth: 'none',
              placement: 'right-start',
              theme: 'bklog-basic-light',
              onShow: handlePopoverShow,
              onHidden: handlePopoverHidden,
            } as any
          }
          content={renderPopoverContent}
        >
          <div class={['task-selection-info', { 'is-over-limit': isOverLimit }]}>
            <div class='task-selection-count'>
              <i18n path='已选 {0} 个任务'>
                <strong class='task-selection-number'>{count}</strong>
              </i18n>
            </div>
            {isOverLimit && (
              <div class='task-selection-warning'>
                <i class='bk-icon icon-info-circle' />
                {t('超过单次上限（{n} 个任务）', { n: MAX_BATCH_DOWNLOAD_TASKS })}
              </div>
            )}
            <div class='task-selection-actions'>
              <bk-button
                size='small'
                onClick={() => emit('select-all')}
              >
                {t('全选已采集')}
              </bk-button>
              <bk-button
                size='small'
                onClick={() => emit('clear')}
              >
                {t('取消')}
              </bk-button>
            </div>
            <bk-button
              class='task-selection-download'
              disabled={isOverLimit}
              size='small'
              theme='primary'
              onClick={() => emit('download')}
            >
              {t('下载已选（{n}）', { n: count })}
            </bk-button>
          </div>
        </BklogPopover>
      );
    };
  },
});
