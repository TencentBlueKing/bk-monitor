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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { Alert, Button, Message, Sideslider } from 'bkui-vue';
import { copyText } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { PROTOCOLS } from './sdk-protocols';

import type { IRumAppConfig } from '../../typings/rum-app-config';

import './sdk-report.scss';

const operateTypeMap = {
  init: 'init',
  success: 'success',
  fail: 'fail',
} as const;
type EOperateType = (typeof operateTypeMap)[keyof typeof operateTypeMap];

export default defineComponent({
  name: 'SDKReport',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    appInfo: {
      type: Object as PropType<Partial<IRumAppConfig>>,
      default: () => null,
    },
  },
  emits: {
    showChange: (_v: boolean) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();
    const protocol = shallowRef(PROTOCOLS[0].id);
    const operateType = shallowRef<EOperateType>(operateTypeMap.init);
    const submitLoading = shallowRef(false);
    const handleShowChange = (show: boolean) => {
      emit('showChange', show);
    };
    const handleProtocolChange = id => {
      protocol.value = id;
    };
    const handleSkip = () => {
      handleShowChange(false);
    };
    const handleCopyToken = () => {
      copyText('token', (msg: string) => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };
    const handleResetToken = () => {
      console.log('reset token');
    };
    const handleSubmit = async () => {
      if (submitLoading.value) {
        return;
      }
      submitLoading.value = true;
      const type = await (() =>
        new Promise(resolve => {
          setTimeout(() => {
            resolve(Date.now() % 2 === 1 ? operateTypeMap.success : operateTypeMap.fail);
          }, 2000);
        }))();
      operateType.value = type as EOperateType;
      submitLoading.value = false;
    };
    return {
      protocol,
      operateType,
      submitLoading,
      handleSubmit,
      t,
      handleShowChange,
      handleProtocolChange,
      handleSkip,
      handleCopyToken,
      handleResetToken,
    };
  },
  render() {
    const stepRender = (
      stepInfo: { index: number; title: string } = { index: 0, title: '' },
      descRender: () => JSX.Element = () => <span />,
      contentRender: () => JSX.Element = () => <div />
    ) => {
      return (
        <div class='step-item-wrap'>
          <div class='top-wrap'>
            <span class='step-index'>{stepInfo.index}</span>
            <span class='step-title'>{stepInfo.title}</span>
            <span class='split-line' />
            {descRender()}
          </div>
          <div class='bottom-wrap'>{contentRender()}</div>
        </div>
      );
    };

    const stepListRender = () => {
      const stepRenderMap = {
        1: {
          index: 1,
          title: this.t('选择 SDK 协议'),
          descRender: () => (
            <span style='color: #8896B3;font-size: 12px;'>
              {this.t('不同协议的数据格式和上报联路有所差异，请根据技术栈选择')}
            </span>
          ),
          contentRender: () => (
            <div class='protocols-wrap'>
              {PROTOCOLS.map(item => (
                <div
                  key={item.id}
                  class={['protocols-wrap-card', item.id === this.protocol ? 'active' : '']}
                  onClick={() => this.handleProtocolChange(item.id)}
                >
                  <div class='card-header'>
                    <span class={`icon-monitor ${item.icon}`} />
                    <span class='card-header-title'>{item.name}</span>
                    <span class='card-header-labels'>
                      {item.labels.map(l => (
                        <span key={l}>{l}</span>
                      ))}
                    </span>
                  </div>
                  <div class='card-desc'>{item.desc}</div>
                  <div class='card-tags'>
                    {item.tags.map(t => (
                      <span key={t}>{t}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ),
        },
        2: {
          index: 2,
          title: this.t('选择安装方式'),
          descRender: () => <span style='color: #8896B3;font-size: 12px;'>根据项目类型选择安装方式</span>,
          contentRender: () => <div>contentRender</div>,
        },
        3: {
          index: 3,
          title: this.t('接入指引'),
          descRender: () => <span>descRender</span>,
          contentRender: () => <div>contentRender</div>,
        },
      };
      return [1, 2, 3].map(item =>
        stepRender(
          {
            index: stepRenderMap[item].index,
            title: stepRenderMap[item].title,
          },
          stepRenderMap[item].descRender,
          stepRenderMap[item].contentRender
        )
      );
    };

    return (
      <Sideslider
        width={800}
        class='rum-sdk-report-sideslider'
        isShow={this.show}
        title={this.t('SDK 上报')}
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          default: () => (
            <div class='rum-sdk-report-content'>
              <div class='create-success'>
                <div class='icon-wrap'>
                  <span class='icon-monitor icon-mc-check-small' />
                </div>
                <div class='success-text'>{this.t('应用创建成功，请根据指引完成上报')}</div>
              </div>
              <div class='rum-app-info-box'>
                <div class='left-wrap'>
                  <i class='icon-monitor icon-mc-global' />
                </div>
                <div class='right-wrap'>
                  <div class='right-wrap-top'>{this.appInfo?.app_name || '--'}</div>
                  <div class='right-wrap-bottom'>
                    <span class='desc-text'>{this.appInfo?.app_alias || '--'}</span>
                    <span class='split-line' />
                    <span class='token-title'>TOKEN:</span>
                    <span class='token-text'>{'todo'}</span>
                    <span
                      class='copy-btn'
                      onClick={() => this.handleCopyToken()}
                    >
                      <span class='icon-monitor icon-mc-copy' />
                      <span>{this.t('复制')}</span>
                    </span>
                    <span
                      class='reset-btn'
                      onClick={() => this.handleResetToken()}
                    >
                      <span class='icon-monitor icon-zhongzhi1' />
                      <span>{this.t('重置')}</span>
                    </span>
                  </div>
                </div>
              </div>
              {stepListRender()}
            </div>
          ),
          footer: () => (
            <div class='bottom-submit-wrap'>
              <div class='tips-wrap'>
                {this.operateType === operateTypeMap.success ? (
                  <Alert
                    class='mt-8'
                    theme='success'
                    title='已检测到数据上报，接入成功，可前往查看数据！'
                  >
                    {{
                      icon: () => (
                        <span
                          style='color: #2CAF5E;margin-right: 8px;'
                          class='icon-monitor icon-duihao'
                        />
                      ),
                    }}
                  </Alert>
                ) : undefined}
                {this.operateType === operateTypeMap.fail ? (
                  <Alert
                    class='mt-8'
                    theme='warning'
                    title='尚未检测到数据上报，请稍后重试，也可以跳过。'
                  />
                ) : undefined}
              </div>
              <div class='btns-wrap'>
                <Button
                  class='mr-8'
                  loading={this.submitLoading}
                  theme='primary'
                  outline
                  onClick={this.handleSubmit}
                >
                  {this.operateType === operateTypeMap.fail ? this.t('重新检测上报') : this.t('检测数据上报')}
                </Button>
                <Button
                  class='mr-8'
                  disabled={this.operateType !== operateTypeMap.success}
                  theme='primary'
                >
                  {this.t('查看数据')}
                </Button>
                <Button
                  disabled={this.operateType === operateTypeMap.success}
                  onClick={this.handleSkip}
                >
                  {this.t('跳过，稍后接入')}
                </Button>
              </div>
            </div>
          ),
        }}
      </Sideslider>
    );
  },
});
