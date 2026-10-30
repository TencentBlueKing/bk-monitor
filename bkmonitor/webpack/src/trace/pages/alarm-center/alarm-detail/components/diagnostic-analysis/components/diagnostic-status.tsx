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
import { type PropType, defineComponent } from 'vue';

import { Button, Exception, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './diagnostic-status.scss';

/** 诊断面板状态：诊断中 / 诊断失败 / 未配置 */
export type DiagnosticStatusType = 'diagnosing' | 'error' | 'unconfigured';

export default defineComponent({
  name: 'DiagnosticStatus',
  props: {
    status: {
      type: String as PropType<DiagnosticStatusType>,
      required: true,
    },
  },
  emits: ['configure', 'contactAdmin', 'diagnose', 'retry'],
  setup(_, { emit }) {
    const { t } = useI18n();

    return {
      t,
      handleConfigure: () => emit('configure'),
      handleContactAdmin: () => emit('contactAdmin'),
      handleDiagnose: () => emit('diagnose'),
      handleRetry: () => emit('retry'),
    };
  },
  render() {
    if (this.status === 'diagnosing') {
      return (
        <div
          class='diagnostic-status is-diagnosing'
          role='status'
        >
          <Loading
            loading
            theme='primary'
            mode='spin'
            title={this.t('AI诊断中，请稍候…')}
          />
        </div>
      );
    }

    const isError = this.status === 'error';

    return (
      <div class={['diagnostic-status', isError ? 'is-error' : 'is-unconfigured']}>
        <Exception
          scene='part'
          title={isError ? this.t('AI诊断错误') : this.t('当前告警未配置AI诊断')}
          type={isError ? '500' : 'empty'}
          v-slots={
            isError
              ? {
                  type: () => (
                    <i
                      class='diagnostic-status-error-icon icon-monitor icon-mc-close-fill'
                      aria-hidden='true'
                    />
                  ),
                }
              : undefined
          }
        >
          <div class={['diagnostic-status-actions', isError ? 'is-error' : 'is-unconfigured']}>
            {isError ? (
              <>
                <Button
                  theme='primary'
                  onClick={this.handleRetry}
                >
                  {this.t('重试')}
                </Button>
                <Button onClick={this.handleContactAdmin}>{this.t('联系管理员')}</Button>
              </>
            ) : (
              <>
                <Button
                  theme='primary'
                  onClick={this.handleDiagnose}
                >
                  {this.t('立即诊断')}
                </Button>
                <Button
                  outline
                  theme='primary'
                  onClick={this.handleConfigure}
                >
                  {this.t('前往配置')}
                </Button>
              </>
            )}
          </div>
        </Exception>
      </div>
    );
  },
});
