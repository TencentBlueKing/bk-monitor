/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import { useI18n } from 'vue-i18n';

import './topk-list-header.scss';

/**
 * TopK 区块标题（字段名 + 去重统计数）与下载入口，弹层头部与侧栏头部共用。
 * 下载入口：loading 时显示转圈图标；showText 带文字（侧栏），showTooltips 带悬浮提示（弹层）。
 */
export default defineComponent({
  name: 'TopKListHeader',
  props: {
    /** 字段名 */
    displayName: {
      type: String,
      default: '',
    },
    /** 去重后的字段统计数 */
    distinctCount: {
      type: Number,
      default: 0,
    },
    downloadLoading: {
      type: Boolean,
      default: false,
    },
    /** 是否展示下载入口（侧栏耗时模式下隐藏） */
    showDownload: {
      type: Boolean,
      default: true,
    },
    /** 下载按钮带文字（侧栏） */
    showText: {
      type: Boolean,
      default: false,
    },
    /** 下载按钮带悬浮提示（弹层） */
    showTooltips: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    download: () => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();

    function handleDownload() {
      emit('download');
    }

    return { t, handleDownload };
  },
  render() {
    return (
      <>
        <div class='dimension-top-k-title'>
          <span
            class='field-name'
            v-overflow-tips
          >
            {this.displayName}
          </span>
          <span class='divider' />
          <span class='desc'>
            {this.t('去重后的字段统计')} ({this.distinctCount || 0})
          </span>
        </div>
        {this.showDownload &&
          (this.downloadLoading ? (
            <img
              class='loading-icon'
              alt=''
              src={loadingIcon}
            />
          ) : (
            <div
              class='download-tool'
              v-bk-tooltips={{ content: this.t('下载'), boundary: 'parent', disabled: !this.showTooltips }}
              onClick={this.handleDownload}
            >
              <i class='icon-monitor icon-xiazai2' />
              {this.showText && <span class='text'>{this.t('下载')}</span>}
            </div>
          ))}
      </>
    );
  },
});
