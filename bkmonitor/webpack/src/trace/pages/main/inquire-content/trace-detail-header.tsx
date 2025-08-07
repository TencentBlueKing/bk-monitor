/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { Message, Popover } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import './trace-detail-header.scss';

const traceHeaderProps = {
  isInTable: {
    type: Boolean,
    default: false,
  },
  appName: {
    type: String,
    default: true,
  },
  traceId: {
    type: String,
    default: '',
  },
  fullscreen: {
    type: Boolean,
    default: false,
  },
  hasFullscreen: {
    type: Boolean,
    default: true,
  },
};

export default defineComponent({
  name: 'TraceDetailHeader',
  props: traceHeaderProps,
  emits: ['fullscreenChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    // 复制操作
    const handleCopy = (content: string) => {
      let text = '';
      const { traceId } = props;
      if (content === 'text') {
        text = traceId;
      } else {
        const hash = `#${window.__BK_WEWEB_DATA__?.baseroute || '/'}home/?app_name=${
          props.appName
        }&search_type=accurate&sceneMode=trace&trace_id=${traceId}`;
        text = location.href.replace(location.hash, hash);
      }
      copyText(text, (msg: string) => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
        width: 200,
      });
    };

    const handleFullScreen = (flag: boolean) => {
      emit('fullscreenChange', flag);
    };

    return {
      t,
      handleCopy,
      handleFullScreen,
    };
  },

  render() {
    const { isInTable, traceId } = this.$props;

    return (
      <div class={`trace-detail-header ${isInTable ? 'is-in-table' : ''}`}>
        <div class='trace-header-title'>
          <span class='trace-id'>{isInTable ? `Trace ID：${traceId}` : traceId}</span>
          <Popover
            content={this.t('复制 TraceID')}
            placement='right'
            theme='light'
          >
            <span
              class='icon-monitor icon-mc-copy'
              onClick={() => this.handleCopy('text')}
            />
          </Popover>
          <Popover
            content={this.t('复制链接')}
            placement='right'
            theme='light'
          >
            <span
              class='icon-monitor icon-copy-link'
              onClick={() => this.handleCopy('link')}
            />
          </Popover>
        </div>

        <div class='header-tool'>
          {this.hasFullscreen && (
            <div class='tool-item'>
              <div
                class='tool-item-content'
                onClick={() => this.handleFullScreen(!this.fullscreen)}
              >
                <i class='icon-monitor icon-fullscreen' />
                <span>{this.t(this.fullscreen ? '退出全屏' : '全屏')}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  },
});
