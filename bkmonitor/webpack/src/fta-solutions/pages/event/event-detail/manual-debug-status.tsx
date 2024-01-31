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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getDemoActionDetail } from '../../../../monitor-api/modules/action';

import './manual-debug-status.scss';

interface IProps {
  actionIds: number[];
  debugKey: string;
  bizIds: Array<number | string>;
  mealInfo?: any;
}

@Component
export default class ManualDebugStatus extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) actionIds: number[];
  @Prop({ default: '', type: String }) debugKey: string;
  @Prop({ default: () => [], type: Array }) bizIds: Array<number | string>;
  @Prop({ default: () => null }) mealInfo: { name: string };

  // 手动处理状态轮询
  isQueryStatus = false;
  debugStatusData: {
    status?: '' | 'success' | 'failure' | 'received' | 'running';
    is_finished?: boolean;
    content?: { text: string; url: string; action_plugin_type: string };
  } = {};

  get actionUrl() {
    const queryString = `?queryString=套餐名称: "${this.mealInfo?.name || ''}"`;
    return `${location.origin}${location.pathname}${location.search}#/event-center${queryString}&searchType=action&activeFilterId=action&from=now-24h&to=now&bizIds=-1`;
  }

  @Watch('debugKey')
  async handleDebugKey() {
    if (this.actionIds.length) {
      this.isQueryStatus = true;
      this.debugStatusData = await this.getDebugStatus(this.actionIds);
    }
  }

  // 轮询调试状态
  getDebugStatus(actionIds) {
    let timer = null;
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    return new Promise(async resolve => {
      if (!this.isQueryStatus) {
        resolve({});
        return;
      }
      this.debugStatusData = await getDemoActionDetail({
        bk_biz_id: this.bizIds[0] || this.$store.getters.bizId,
        action_id: actionIds[0]
      })
        .then(res => (this.isQueryStatus ? res : {}))
        .catch(() => false);
      if (this.debugStatusData.is_finished || !this.debugStatusData) {
        resolve(this.debugStatusData);
      } else {
        timer = setTimeout(() => {
          clearTimeout(timer);
          if (!this.isQueryStatus) {
            resolve({});
            return;
          }
          this.getDebugStatus(actionIds).then(data => {
            if (!this.isQueryStatus) {
              this.debugStatusData = {};
              resolve(this.debugStatusData);
              return;
            }
            this.debugStatusData = data as any;
            if (this.debugStatusData.is_finished) {
              resolve(this.debugStatusData);
            }
          });
        }, 2000);
      }
    });
  }
  handleStopDebug() {
    this.debugStatusData = {};
    this.isQueryStatus = false;
  }

  debugStatusIcon() {
    const loading = (
      <svg
        class='loading-svg'
        viewBox='0 0 64 64'
      >
        <g>
          <path d='M20.7,15c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0l-2.8-2.8c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L20.7,15z' />
          <path d='M12,28c2.2,0,4,1.8,4,4s-1.8,4-4,4H8c-2.2,0-4-1.8-4-4s1.8-4,4-4H12z' />
          <path d='M15,43.3c1.6-1.6,4.1-1.6,5.7,0c1.6,1.6,1.6,4.1,0,5.7l-2.8,2.8c-1.6,1.6-4.1,1.6-5.7,0s-1.6-4.1,0-5.7L15,43.3z' />
          <path d='M28,52c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V52z' />
          <path d='M51.8,46.1c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0L43.3,49c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L51.8,46.1z' />
          <path d='M56,28c2.2,0,4,1.8,4,4s-1.8,4-4,4h-4c-2.2,0-4-1.8-4-4s1.8-4,4-4H56z' />
          <path d='M46.1,12.2c1.6-1.6,4.1-1.6,5.7,0s1.6,4.1,0,5.7l0,0L49,20.7c-1.6,1.6-4.1,1.6-5.7,0c-1.6-1.6-1.6-4.1,0-5.7L46.1,12.2z' />
          <path d='M28,8c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V8z' />
        </g>
      </svg>
    );
    const statusMap = {
      received: loading,
      running: loading,
      success: (
        <div class='success'>
          <span class='icon-monitor icon-mc-check-small'></span>
        </div>
      ),
      failure: (
        <div class='failure'>
          <span class='icon-monitor icon-mc-close'></span>
        </div>
      )
    };
    return statusMap[this.debugStatusData?.status];
  }
  debugStatusTitle() {
    const statusMap = {
      received: `${this.$t('处理中...')}...`,
      running: `${this.$t('处理中...')}...`,
      success: this.$t('处理成功'),
      failure: this.$t('处理失败')
    };
    return statusMap[this.debugStatusData?.status];
  }
  /* 以下为调试内容 */
  debugStatusText(content) {
    if (!content) return undefined;
    const contentText = { text: '', link: '' };
    const arrContent = content?.text?.split('$');
    contentText.text = arrContent?.[0] || '';
    contentText.link = arrContent?.[1] || '';
    return (
      <div class='info-jtnr'>
        {contentText.text}
        {contentText.link ? (
          <span
            class='info-jtnr-link'
            onClick={() => content?.url && window.open(content.url)}
          >
            <span class='icon-monitor icon-copy-link'></span>
            {contentText.link}
          </span>
        ) : undefined}
      </div>
    );
  }
  debugStatusOperate() {
    const statusMap = {
      success: (
        <div class='status-operate'>
          {/* <bk-button theme="primary" style={{ marginRight: '8px' }}>{this.$t('查看详情')}</bk-button> */}
          <bk-button onClick={() => this.handleStopDebug()}>{this.$t('button-完成')}</bk-button>
        </div>
      ),
      failure: (
        <div class='status-operate'>
          <bk-button
            theme='primary'
            onClick={() => this.handleStopDebug()}
          >
            {this.$t('再次处理')}
          </bk-button>
        </div>
      )
    };
    return statusMap[this.debugStatusData?.status];
  }
  render() {
    return (
      <bk-dialog
        extCls={'manual-debug-running-dialog'}
        value={!!this.debugStatusData?.status}
        width={400}
        renderDirective={'if'}
        maskClose={false}
        showFooter={false}
        on-cancel={() => this.handleStopDebug()}
      >
        <div class='status-content'>
          <div class='spinner'>{this.debugStatusIcon()}</div>
          <div class='status-title'>{this.debugStatusTitle()}</div>
          <div class='status-text'>{this.debugStatusText(this.debugStatusData?.content)}</div>
          {!['success', 'failure'].includes(this.debugStatusData?.status) && [
            <div class='status-tip'>
              <span class='icon-monitor icon-hint'></span>
              <i18n
                class='text'
                path='退出当前窗口可前往{0}查看结果'
              >
                <a
                  class='link'
                  href={this.actionUrl}
                  target='_blank'
                >
                  {this.$t('处理记录')}
                </a>
              </i18n>
            </div>,
            this.debugStatusOperate()
          ]}
        </div>
      </bk-dialog>
    );
  }
}
