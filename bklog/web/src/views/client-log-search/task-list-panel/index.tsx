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

import { defineComponent, ref, watch } from 'vue';

import type { LogItem, ProcessStatus } from '../types';
import { t } from '@/hooks/use-locale';

import './index.scss';

/** 面板展开宽度 */
const EXPANDED_WIDTH = 360;

export default defineComponent({
  name: 'TaskListPanel',
  props: {
    /** 外部控制的收起状态，用于从父组件展开 */
    collapsed: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['log-item-select', 'toggle'],
  setup(props, { emit }) {
    /** 是否收起 */
    const isCollapsed = ref(false);

    /** 监听外部 collapsed 变化，同步内部状态 */
    watch(() => props.collapsed, (val) => {
      isCollapsed.value = val;
    });

    /** 当前选中的条目 ID */
    const selectedItemId = ref<number | null>(null);

    /** 日志条目列表数据 */
    const logItemList: LogItem[] = [];

    /**
     * 切换收起/展开
     */
    const handleToggle = () => {
      isCollapsed.value = !isCollapsed.value;
      emit('toggle', isCollapsed.value);
    };

    /**
     * 点击日志条目
     */
    const handleLogItemSelect = (item: LogItem) => {
      selectedItemId.value = item.id;
      emit('log-item-select', item);
    };

    return () => (
      <div
        class={['card-base', 'task-list-panel', { 'is-collapsed': isCollapsed.value }]}
        style={{ width: `${isCollapsed.value ? 0 : EXPANDED_WIDTH}px` }}
      >
        {/* 标题栏：收起箭头 + 标题 */}
        <div class='panel-header' onClick={handleToggle}>
          <i class='bklog-icon bklog-collapse'></i>
          <span class='panel-title'>{t('任务列表')}</span>
        </div>

        {/* 日志条目列表 */}
        <div class='task-list'>
          {logItemList.map(item => (
            <div
              key={item.id ?? item.task_id}
              class={['task-item', { active: selectedItemId.value === item.id }]}
              onClick={() => handleLogItemSelect(item)}
            >
              {/* 第一行：时间 + 状态标签 */}
              <div class='task-header'>
                <span class='task-time'>{item.report_time ?? item.processed_at}</span>
                <span class={`task-status ${(item.process_status ?? '') as ProcessStatus}`}>
                  <i class='status-dot'></i>
                  {item.process_status}
                </span>
              </div>

              {/* 第二行：文件名 + 来源 */}
              <div class='task-title-row'>
                <span class='task-title'>{item.file_name}</span>
                <span class='task-separator'></span>
                <span class='task-id'>{item.source}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
