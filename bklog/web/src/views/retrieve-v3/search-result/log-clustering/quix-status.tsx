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
import { defineComponent, type InjectionKey, type ComputedRef, type PropType } from 'vue';
import useLocale from '@/hooks/use-locale';
import { type QuixStatus } from '@/services/retrieve';

export const quixPage: InjectionKey<{ status: ComputedRef<QuixStatus | undefined>; refresh: () => void }> =
  Symbol('quixPage');

const phaseText = {
  enabling: '正在开启聚类',
  updating: '正在更新聚类配置',
  disabling: '正在关闭聚类',
  stopped: '聚类已关闭',
  reopening: '正在重新开启聚类',
};
const failureText = {
  enable: '开启聚类失败',
  update: '更新聚类配置失败',
  update_model: '更新模型参数失败',
  disable: '关闭聚类失败',
  reopen: '重新开启聚类失败',
};

export default defineComponent({
  props: {
    status: { type: Object as PropType<QuixStatus>, required: true },
    busy: Boolean,
    showProgress: Boolean,
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    return () => {
      const { phase, operation, bkfara } = props.status;
      const retryable = operation?.status === 'failed';
      const failed = retryable || (operation?.status === 'canceled' && !!operation.last_error);
      const awaitingReceipt = operation?.status === 'awaiting_receipt';
      const canClose = (failed || awaitingReceipt) && !['running', 'disabling', 'stopped'].includes(phase);
      const operationError = (failed || operation?.status === 'running') && operation?.last_error;
      if (
        phase === 'running' &&
        !failed &&
        !awaitingReceipt &&
        !operationError &&
        !bkfara?.error &&
        !bkfara?.pending_result_count
      ) {
        return null;
      }
      if (
        props.showProgress &&
        !failed &&
        !canClose &&
        !operation?.last_error &&
        !bkfara?.error &&
        !bkfara?.pending_result_count
      ) {
        return null;
      }
      return (
        <div
          class='quix-status'
          aria-live='polite'
        >
          {failed && phase !== 'stopped' ? (
            <strong>{t(failureText[operation.operation_type])}</strong>
          ) : phase !== 'running' && (
            <strong>{t(phaseText[phase])}</strong>
          )}
          {awaitingReceipt && (
            <span>{t(operation.operation_type === 'disable' ? '等待后台资源收尾' : '配置已下发，等待采用确认')}</span>
          )}
          {operationError && <span>{operationError}</span>}
          {bkfara?.error && <span>{bkfara.error}</span>}
          {!!bkfara?.pending_result_count && (
            <span>
              {t('待处理结果数')}：{bkfara.pending_result_count}
            </span>
          )}
          {phase === 'stopped' && props.status.distance_threshold && (
            <span>{t('历史聚类结果仍可查询；资源释放状态需单独确认。')}</span>
          )}
          {!window.IS_EXTERNAL && (
            <span class='quix-actions'>
              {retryable && (
                <bk-button
                  text
                  disabled={props.busy}
                  on-click={() => emit('retry')}
                >
                  {t('重试')}
                </bk-button>
              )}
              {phase === 'stopped' && props.status.can_reopen && (
                <bk-button
                  text
                  disabled={props.busy}
                  on-click={() => emit('reopen')}
                >
                  {t('重新开启聚类')}
                </bk-button>
              )}
              {canClose && (
                <bk-button
                  text
                  disabled={props.busy}
                  on-click={() => emit('close')}
                >
                  {t('关闭聚类')}
                </bk-button>
              )}
            </span>
          )}
        </div>
      );
    };
  },
});
