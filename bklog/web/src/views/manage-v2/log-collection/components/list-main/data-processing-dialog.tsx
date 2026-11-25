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

import { computed, defineComponent, ref, watch } from 'vue';
import useLocale from '@/hooks/use-locale';
import BklogPopover from '@/components/bklog-popover';
import type { Props as TippyProps } from 'tippy.js';
import {
  namespaceDataSourceUrl,
  namespaceLabel,
  useNamespaceAuthorization,
} from '../../hook/use-namespace-authorization';
import './data-processing-dialog.scss';

export default defineComponent({
  name: 'DataProcessingDialog',
  props: {
    visible: { type: Boolean, default: false },
    collectorConfigId: { type: [Number, String], default: '' },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const state = useNamespaceAuthorization();
    const confirmRef = ref<{ show: () => void; hide: () => void } | null>(null);
    const targetUrl = ref('');
    const selectedLabel = computed(() =>
      state.selectedNamespace.value ? namespaceLabel(state.selectedNamespace.value) : '',
    );
    const syncDescription = computed(() =>
      t('该日志数据源将自动同步至 BKBase 指定空间「{space}」。', { space: selectedLabel.value }),
    );
    const syncHint = () => t('您可以针对这部分数据进行清洗配置等操作，不会影响该采集。是否确认？');
    const canConfirm = computed(
      () => !!state.selectedNamespace.value && !state.loading.value && !state.submitting.value,
    );
    const confirmText = computed(() => {
      if (state.submitting.value) return t('授权中');
      return targetUrl.value ? t('前往') : t('确定');
    });

    const close = () => {
      if (state.submitting.value) return;
      confirmRef.value?.hide();
      emit('close');
    };

    watch(
      () => [props.visible, props.collectorConfigId],
      () => {
        confirmRef.value?.hide();
        targetUrl.value = '';
        if (props.visible) void state.load(props.collectorConfigId);
        else state.reset();
      },
      { immediate: true },
    );

    const confirmAuthorization = async () => {
      if (!canConfirm.value) return;
      confirmRef.value?.hide();
      const data = await state.authorize();
      if (!data) return;
      targetUrl.value = namespaceDataSourceUrl(window.BKBASE_V4_URL, data);
    };

    const handleConfirm = () => {
      if (!canConfirm.value) return;
      if (targetUrl.value) {
        window.open(targetUrl.value, '_blank', 'noopener,noreferrer');
        close();
        return;
      }
      confirmRef.value?.show();
    };

    const renderConfirmation = () => (
      <div
        class='namespace-confirm'
        data-test-id='namespace-confirm'
      >
        <div class='namespace-confirm-content'>
          <div class='namespace-confirm-icon'>
            <i class='bk-icon icon-info-circle' />
          </div>
          <div class='namespace-confirm-copy'>
            <div class='namespace-confirm-title'>{t('确认同步')}</div>
            <div class='namespace-confirm-description'>
              {syncDescription.value}
              {syncHint()}
            </div>
          </div>
        </div>
        <div class='namespace-confirm-actions'>
          <bk-button
            theme='primary'
            size='small'
            loading={state.submitting.value}
            on-click={confirmAuthorization}
            data-test-id='namespace-submit'
          >
            {t('确认')}
          </bk-button>
          <bk-button
            size='small'
            disabled={state.submitting.value}
            on-click={() => confirmRef.value?.hide()}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );

    return () => (
      <bk-dialog
        value={props.visible}
        width={480}
        ext-cls='data-processing-dialog'
        title={t('数据加工')}
        header-position='left'
        mask-close={false}
        draggable={false}
        close-icon={!state.submitting.value}
        esc-close={!state.submitting.value}
        on-value-change={(visible: boolean) => {
          if (!visible) close();
        }}
        scopedSlots={{
          footer: () => (
            <div class='namespace-dialog-actions'>
              <BklogPopover
                ref={confirmRef}
                trigger='manual'
                content={renderConfirmation}
                options={
                  {
                    placement: 'bottom-start',
                    theme: 'light namespace-confirm-popover',
                    interactive: true,
                    arrow: true,
                    appendTo: document.body,
                    hideOnClick: false,
                    maxWidth: 320,
                  } as unknown as TippyProps
                }
              >
                <bk-button
                  theme='primary'
                  disabled={!canConfirm.value}
                  on-click={handleConfirm}
                  data-test-id='namespace-confirm-trigger'
                >
                  {confirmText.value}
                </bk-button>
              </BklogPopover>
              <bk-button
                disabled={state.submitting.value}
                on-click={close}
              >
                {t('取消')}
              </bk-button>
            </div>
          ),
        }}
      >
        <div class='namespace-dialog-content'>
          <bk-alert
            class='namespace-alert'
            title={t('选择数据平台空间后，该日志数据自动同步至数据平台对应空间')}
          />
          <div class='namespace-form'>
            <div class='namespace-form-label'>
              {t('数据平台空间')}
              <span class='required'>*</span>
            </div>
            <bk-select
              value={state.selectedName.value}
              loading={state.loading.value}
              disabled={state.submitting.value}
              searchable
              clearable={false}
              popover-options={{ boundary: 'window' }}
              ext-popover-cls='namespace-select-dropdown'
              class='namespace-select'
              onInput={(name: string) => {
                confirmRef.value?.hide();
                if (name !== state.selectedName.value) targetUrl.value = '';
                state.selectedName.value = name;
              }}
            >
              {state.namespaces.value.map(item => (
                <bk-option
                  key={item.name}
                  id={item.name}
                  name={item.alias ? `${item.alias}（${item.name}）` : item.name}
                >
                  <div class='namespace-option-heading'>
                    <span class='namespace-option-alias'>{namespaceLabel(item)}</span>
                    {item.is_authorized && <span class='namespace-tag authorized'>{t('已授权')}</span>}
                  </div>
                  <div class='namespace-option-name'>{item.name}</div>
                </bk-option>
              ))}
            </bk-select>
            {state.selectedNamespace.value && (
              <div class='namespace-description'>
                <div>{syncDescription.value}</div>
                <div>{syncHint()}</div>
              </div>
            )}
          </div>
        </div>
      </bk-dialog>
    );
  },
});
