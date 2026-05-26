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
    /** 任务列表数据 */
    taskList: {
      type: Array as () => LogItem[],
      default: () => [],
    },
    /** 是否还有更多数据 */
    hasMore: {
      type: Boolean,
      default: true,
    },
    /** 是否正在加载 */
    isLoading: {
      type: Boolean,
      default: false,
    },
    /** 当前选中的日志条目 */
    selectedLogItem: {
      type: Object as () => LogItem | null,
      default: null,
    },
    /** 当前选中的任务来源 */
    activeSource: {
      type: String,
      default: '',
    },
  },
  emits: ['log-item-select', 'toggle', 'load-more', 'source-change'],
  setup(props, { emit, expose }) {
    /** 是否收起 */
    const isCollapsed = ref(false);

    /** 滚动容器引用 */
    const scrollContainerRef = ref<HTMLElement | null>(null);

    /** 重置滚动位置到顶部，供父组件在重新查询时调用 */
    const resetScroll = () => {
      scrollContainerRef.value?.scrollTo({
        top: 0,
        behavior: 'auto',
      });
    };

    // 暴露 resetScroll 方法供父组件调用
    expose({ resetScroll });

    /** 监听外部 collapsed 变化，同步内部状态 */
    watch(() => props.collapsed, (val) => {
      isCollapsed.value = val;
    });

    /**
     * 切换收起/展开
     */
    const handleToggle = () => {
      isCollapsed.value = !isCollapsed.value;
      emit('toggle', isCollapsed.value);
    };

    /**
     * 隐藏滚动区域内的 overflow-tips tooltip，
     * 防止滚动后 tooltip 不消失并随滚动偏移
     */
    const hideOverflowTips = () => {
      scrollContainerRef.value?.querySelectorAll('.task-title, .task-id').forEach((el: any) => {
        if (el._tippy) {
          el._tippy.hide();
        }
      });
    };

    /**
     * 触底加载检测
     */
    const handleScroll = (e: Event) => {
      hideOverflowTips();
      const el = e.target as HTMLElement;
      if (el.scrollTop + el.clientHeight + 50 >= el.scrollHeight) {
        if (!props.isLoading && props.hasMore) {
          emit('load-more');
        }
      }
    };

    /**
     * 点击日志条目
     */
    const handleLogItemSelect = (item: LogItem) => {
      if (item === props.selectedLogItem) return;
      emit('log-item-select', item);
    };

    /**
     * 将任务处理状态映射为采集状态
     */
    const mapToCollectionStatus = (status: ProcessStatus | null): string => {
      const statusMap: Record<ProcessStatus, string> = {
        init: 'uncollected',
        pending: 'uncollected',
        running: 'collecting',
        success: 'collected',
        failed: 'failed',
      };
      return status ? statusMap[status] : 'uncollected';
    };

    /** 采集状态对应的显示文本 */
    const mapToCollectionStatusText = (status: ProcessStatus | null): string => {
      const statusMap: Record<ProcessStatus, string> = {
        init: '未采集',
        pending: '未采集',
        running: '采集中',
        success: '已采集',
        failed: '采集失败',
      };
      return status ? statusMap[status] : '未采集';
    };

    const handleTabChange = (source: string) => {
      if (props.activeSource === source) return;
      emit('source-change', source);
    };

    return () => {
      const tabIndex = props.activeSource === '' ? 0 : props.activeSource === 'report' ? 1 : 2;

      return (
        <div
          class={['card-base', 'task-list-panel', { 'is-collapsed': isCollapsed.value }]}
          style={{ width: `${isCollapsed.value ? 0 : EXPANDED_WIDTH}px` }}
        >
          {/* 标题栏：收起箭头 + 标题 */}
          <div class='panel-header' onClick={handleToggle}>
            <i class='bklog-icon bklog-collapse'></i>
            <span class='panel-title'>{t('任务列表')}</span>
          </div>

          {/* 选项卡：全部 / 用户上报 / 主动采集 */}
          <div class='task-source-tabs'>
            <div class='tab-slider' style={{ transform: `translateX(${tabIndex * 100}%)` }}></div>
            <div
              class={['tab-item', { active: props.activeSource === '', 'hide-divider': tabIndex === 0 || tabIndex === 1 }]}
              onClick={() => handleTabChange('')}
            >
              {t('全部')}
            </div>
            <div
              class={['tab-item', { active: props.activeSource === 'report', 'hide-divider': tabIndex === 1 || tabIndex === 2 }]}
              onClick={() => handleTabChange('report')}
            >
              {t('用户上报')}
            </div>
            <div
              class={['tab-item', { active: props.activeSource === 'task' }]}
              onClick={() => handleTabChange('task')}
            >
              {t('主动采集')}
            </div>
          </div>

          {/* 日志条目列表 */}
          <div class='task-list' ref={scrollContainerRef} onScroll={handleScroll}>
          {props.taskList.map((item, index) => (
            <div
              key={`${item.file_name}_${index}`}
              class={['task-item', { active: props.selectedLogItem === item }]}
              onClick={() => handleLogItemSelect(item)}
            >
              {/* 第一行：时间 + 状态标签 */}
              <div class='task-header'>
                <span class='task-time'>{item.report_time ?? item.processed_at}</span>
                <span class={`task-status ${mapToCollectionStatus(item.process_status)}`}>
                  {item.process_status === 'running'
                    ? <bk-spin size='mini'></bk-spin> : <i class='status-dot'></i>}
                  {t(mapToCollectionStatusText(item.process_status))}
                </span>
              </div>

              {/* 第二行：文件名 + openid */}
              <div class='task-title-row'>
                <span class='task-title' v-bk-overflow-tips>{item.file_name}</span>
                {item.openid && (
                  <span class='task-id' v-bk-overflow-tips>{item.openid}</span>
                )}
              </div>
            </div>
          ))}
          {props.isLoading && props.hasMore && (
            <div class='task-list-loading'>loading...</div>
          )}
        </div>
      </div>
      );
    };
  },
});
