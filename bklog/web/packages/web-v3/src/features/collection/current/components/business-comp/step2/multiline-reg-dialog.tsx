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


import { useApplicationStore } from '@/app/state/domains/application-store';
import {
  Button as TButton,
  Dialog as TDialog,
  Form as TForm,
  FormItem as TFormItem,
  Input as TInput,
  Textarea as TTextarea,
} from 'tdesign-vue-next';
import type { FormInstanceFunctions, FormRule } from 'tdesign-vue-next';
import SourceTranslation from '@/platform/i18n/translation';
import { ServicesInstance } from '@/platform/services';

import { computed, defineComponent, ref, watch } from 'vue';

import useLocale from '@/shared/composables/use-locale';

import { useRoute } from 'vue-router';

import './multiline-reg-dialog.scss';
/**
 * 行首正则调试弹窗
 */

export default defineComponent({
  name: 'MultilineRegDialog',
  compatConfig: { MODE: 3 },
  props: {
    showDialog: {
      type: Boolean,
      default: false,
    },
    oldPattern: {
      // 父组件输入的行首正则内容
      type: String,
      default: '',
    },
  },
  emits: ['update', 'cancel'],

  setup(props, { emit }) {
    const EN_LABEL_WIDTH = 215;
    const CN_LABEL_WIDTH = 124;
    const DIALOG_HEIGHT = 380;
    const DIALOG_MIN_TOP = 70;

    const { t } = useLocale();
    const store = useApplicationStore();
    const route = useRoute();
    const matchLines = ref<number | null>(null);
    const isMatchLoading = ref(false);
    let matchGeneration = 0;
    const formRef = ref<FormInstanceFunctions<{ log_sample: string; multiline_pattern: string }>>();
    const formData = ref({
      log_sample: '', // 日志样例
      multiline_pattern: '', // 行首正则表达式
    });
    const notEmptyRule = ref<FormRule[]>([
      {
        required: true,
        trigger: 'blur',
      },
    ]);

    const getDialogWidth = computed(() => {
      return store.isEnLanguage ? '800' : '680';
    });

    const getLabelWidth = computed(() => {
      return store.isEnLanguage ? EN_LABEL_WIDTH : CN_LABEL_WIDTH;
    });

    const dialogTop = computed(() => {
      const top = (window.innerHeight - DIALOG_HEIGHT) / 2;
      return top < DIALOG_MIN_TOP ? DIALOG_MIN_TOP : top;
    });

    const handleSave = () => {
      emit('update', formData.value.multiline_pattern);
      emit('cancel', false);
    };
    const handleValueChange = (val: boolean) => {
      matchGeneration++;
      emit('cancel', val);
      if (val) {
        // 打开时填入采集页行首正则内容
        formData.value.multiline_pattern = props.oldPattern;
      } else {
        // 关闭时重置数据
        formData.value.log_sample = '';
        formData.value.multiline_pattern = '';
        matchLines.value = null;
        isMatchLoading.value = false;
        formRef.value?.clearValidate();
      }
    };

    watch(
      () => props.showDialog,
      (value, previous) => {
        if (previous === undefined && !value) return;
        handleValueChange(value);
      },
      { immediate: true },
    );

    // 匹配验证
    const handleMatch = async () => {
      const generation = ++matchGeneration;
      try {
        const result = await formRef.value?.validate();
        if (generation !== matchGeneration) return;
        if (result !== true) {
          matchLines.value = 0;
          return;
        }
        isMatchLoading.value = true;
        const res = await ServicesInstance.collect.regexDebug({
          params: {
            collector_id: Number(route.params.collectorId),
          },
          data: { ...formData.value },
        });
        if (generation === matchGeneration) matchLines.value = res.data.match_lines;
      } catch (e) {
        console.log(e);
        if (generation === matchGeneration) matchLines.value = 0;
      } finally {
        if (generation === matchGeneration) isMatchLoading.value = false;
      }
    };
    const handleLogSample = (val: string | number, key: keyof typeof formData.value) => {
      formData.value[key] = String(val).trim();
    };
    const handleCancel = () => {
      emit('cancel', !props.showDialog);
    };

    return () => (
      <TDialog
        width={getDialogWidth.value}
        class='multiline-reg-dialog-box'
        closeOnOverlayClick={false}
        footer={() => (
          <>
            <TButton theme='primary' onClick={handleSave}>
              {t('保存')}
            </TButton>
            <TButton theme='default' onClick={handleCancel}>
              {t('取消')}
            </TButton>
          </>
        )}
        top={dialogTop.value}
        header={t('行首正则调试')}
        visible={props.showDialog}
        onClose={handleCancel}
        onConfirm={handleSave}
      >
        <div class='multiline-reg-dialog-content'>
          <TForm
            ref={formRef}
            labelWidth={getLabelWidth.value}
            requiredMarkPosition='right'
            {...{
              ...{
                data: { ...formData.value },
              },
            }}
          >
            <TFormItem
              style='margin-bottom: 20px'
              label={t('日志样例')}
              name='log_sample'
              requiredMark={true}
              rules={notEmptyRule.value}
            >
              <TTextarea
                autosize={{ minRows: 6, maxRows: 6 }}
                value={formData.value.log_sample}
                onChange={(value) => handleLogSample(value, 'log_sample')}
              />
            </TFormItem>
            <TFormItem
              style='margin-bottom: 20px'
              label={t('行首正则表达式')}
              name='multiline_pattern'
              requiredMark={true}
              rules={notEmptyRule.value}
            >
              <TInput
                value={formData.value.multiline_pattern}
                onChange={(value) => handleLogSample(value, 'multiline_pattern')}
              />
            </TFormItem>
          </TForm>
          <div style={`padding-left: ${getLabelWidth.value}px;`} class='test-container'>
            <TButton class='mr15' loading={isMatchLoading.value} theme='primary' onClick={handleMatch}>
              {t('匹配验证')}
            </TButton>
            {matchLines.value !== null && (
              <div class='test-result'>
                <span
                  class={matchLines.value ? 'bk-icon icon-check-circle-shape' : 'bk-icon icon-close-circle-shape'}
                />
                {matchLines.value ? (
                  <SourceTranslation path='成功匹配 {0} 条日志'>
                    <span class='match-counts'>{matchLines.value}</span>
                  </SourceTranslation>
                ) : (
                  <span>{t('未成功匹配')}</span>
                )}
              </div>
            )}
          </div>
        </div>
      </TDialog>
    );
  },
});
