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

import SelectedTaskTable from './selected-task-table';
import type { LogItem } from '../types';
import { t } from '@/hooks/use-locale';

export default defineComponent({
  name: 'BatchDownloadDialog',
  props: {
    /** 控制二次确认弹窗的显示 */
    visible: {
      type: Boolean,
      default: false,
    },
    /** 弹窗中待确认的已选任务 */
    selectedItems: {
      type: Array as () => LogItem[],
      default: () => [],
    },
    /** 搜索使用的时区，传给确认表格 */
    timezone: {
      type: String,
      default: '',
    },
  },
  /** 关闭与确认事件由页面层处理；确认后页面层清空勾选、关闭弹窗并发起批量下载 */
  emits: ['close', 'confirm'],
  setup(props, { emit }) {
    return () => (
      <bk-dialog
        class='batch-download-dialog'
        width={640}
        header-position='left'
        mask-close={false}
        render-directive='if'
        title={t('下载 {n} 个采集任务', { n: props.selectedItems.length })}
        value={props.visible}
        on-value-change={(visible: boolean) => {
          if (!visible) emit('close');
        }}
      >
        <SelectedTaskTable
          items={props.selectedItems}
          timezone={props.timezone}
        />
        <div slot='footer'>
          <bk-button onClick={() => emit('close')}>{t('取消')}</bk-button>
          <bk-button
            class='batch-download-confirm'
            disabled={props.selectedItems.length === 0}
            theme='primary'
            onClick={() => emit('confirm')}
          >
            {t('开始下载')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  },
});
