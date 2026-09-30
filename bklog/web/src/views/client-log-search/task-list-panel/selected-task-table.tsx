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

import type { LogItem } from '../types';
import { formatTimeZoneString } from '@/global/utils/time';
import { t } from '@/hooks/use-locale';

export default defineComponent({
  name: 'SelectedTaskTable',
  props: {
    /** 当前批量选中的任务 */
    items: {
      type: Array as () => LogItem[],
      default: () => [],
    },
    /** 悬停浮层使用紧凑的月日时分格式 */
    compact: {
      type: Boolean,
      default: false,
    },
    /** 是否显示逐项移出操作 */
    removable: {
      type: Boolean,
      default: false,
    },
    /** 搜索使用的时区，与页面其他时间展示保持一致 */
    timezone: {
      type: String,
      default: '',
    },
  },
  /** 移出所选任务，由上层维护勾选状态 */
  emits: ['remove'],
  setup(props, { emit }) {
    /** 两种来源均以处理完成时间作为采集时间，UTC 值转换到当前搜索时区 */
    const getCollectionTime = (item: LogItem) => {
      if (!item.processed_at) return '--';
      const format = props.compact ? 'MM-DD HH:mm' : 'YYYY-MM-DD HH:mm:ss';
      return formatTimeZoneString(item.processed_at, props.timezone, format, false);
    };

    /** 仅当表格位于悬停浮层中时，将溢出提示挂在浮层内，避免鼠标移入提示时浮层关闭 */
    const getOverflowTipsContainer = (reference: HTMLElement) =>
      reference.closest('.task-selection-popover-root') || document.body;

    return () => (
      <bk-table
        class='selected-task-table'
        data={props.items}
        max-height={320}
      >
        <bk-table-column
          label={t('采集时间')}
          resizable={false}
          width={props.compact ? '100' : '160'}
          scopedSlots={{ default: ({ row }: { row: LogItem }) => getCollectionTime(row) }}
        />
        <bk-table-column
          label={t('任务')}
          min-width={props.compact ? '200' : '220'}
          resizable={false}
          scopedSlots={{
            default: ({ row }: { row: LogItem }) => (
              <span
                class='selected-task-name'
                v-bk-overflow-tips={{
                  appendTo: getOverflowTipsContainer,
                }}
              >
                {row.file_name}
              </span>
            ),
          }}
        />
        {props.removable && (
          <bk-table-column
            resizable={false}
            width='64'
            scopedSlots={{
              default: ({ row }: { row: LogItem }) => (
                <bk-button
                  class='selected-task-remove'
                  text
                  theme='primary'
                  onClick={() => emit('remove', row)}
                >
                  {t('移出')}
                </bk-button>
              ),
            }}
          />
        )}
      </bk-table>
    );
  },
});
