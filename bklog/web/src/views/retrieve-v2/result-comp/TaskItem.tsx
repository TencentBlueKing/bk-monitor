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
import { bkProgress, bkLink } from 'bk-magic-vue';
import { t } from '@/hooks/use-locale';
import { formatNumber } from '@/views/retrieve-v2/result-comp/download/downloadProgress';
import './TaskItem.scss';

export default defineComponent({
  name: 'TaskItem',
  components: {
    bkProgress,
    bkLink
  },
  props: {
    item: {
      type: Object,
      required: true
    }
  },
  emits: ['view-detail'],
  setup(props, { emit }) {
    /**
     * 判断是否为下载中的状态
     */
    const isDownloading = () => {
      const downloadingStatuses = ['download_log', 'export_package', 'export_upload'];
      return downloadingStatuses.includes(props.item.export_status as string);
    };

    /**
     * 判断是否为失败状态
     */
    const isFailed = () => {
      return props.item.export_status === 'failed';
    };

    /**
     * 判断是否为未启动状态
     */
    const isNotStarted = () => {
      return props.item.export_status === null;
    };

    /**
     * 获取进度条的主题
     * primary: 蓝色 (下载中)
     * danger: 红色 (失败)
     * undefined: 灰色 (未启动)
     */
    const progressTheme = () => {
      if (isDownloading()) return 'primary';
      if (isFailed()) return 'danger';
      return undefined;
    };

    /**
     * 渲染右侧状态区域的内容
     */
    const renderStatusContent = () => {
      if (isFailed()) {
        return (
          <div class="status-content failed">
            <span class="status-dot failed-dot"></span>
            <span class="status-text">{t('失败')}</span>
            <span
              class="detail-link" 
            >
              {t('查看详情')}
            </span>
          </div>
        );
      }
      if (isNotStarted()) {
        return (
          <div class="status-content not-started">
            <span class="status-dot pending-dot"></span>
            <span class="status-text">{t('未启动')}</span>
          </div>
        );
      }
      if (isDownloading()) {
        // 下载中状态：显示百分比和数量详情
        return (
          <div class="status-content downloading">
            <span class="progress-text">
              {props.item.progressPercent} % ({formatNumber(props.item.exported_count)} / {formatNumber(props.item.export_total_count)})
            </span>
          </div>
        );
      }
      return null;
    };

    return () => (
      <div class="task-item-wrapper">
        {/* 头部区域：ID + 状态信息 */}
        <div class="task-header">
          <div class="task-id">#{props.item.id}</div>
          <div class="task-status-area">
            {renderStatusContent()}
          </div>
        </div>
        
        {/* 进度条区域 */}
        <div class="task-progress-area">
          <bk-progress
            percent={(props.item.progressPercent ?? 0) / 100}
            theme={progressTheme()}
            showText={false}
            strokeWidth={6}
          />
        </div>
      </div>
    );
  }
});
