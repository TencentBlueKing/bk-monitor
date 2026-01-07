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

import { computed, defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';

import $http from '@/api';

import './multiline-reg-dialog.scss';
/**
 * 行首正则调试弹窗
 */

export default defineComponent({
  name: 'MultilineRegDialog',
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
    const store = useStore();
    const route = useRoute();
    const matchLines = ref(null);
    const isMatchLoading = ref(false);
    const formRef = ref(null);
    const formData = ref({
      log_sample: '', // 日志样例
      multiline_pattern: '', // 行首正则表达式
    });
    const notEmptyRule = ref([
      {
        required: true,
        trigger: 'blur',
      },
    ]);

    const getDialogWidth = computed(() => {
      return store.getters.isEnLanguage ? '800' : '680';
    });

    const getLabelWidth = computed(() => {
      return store.getters.isEnLanguage ? EN_LABEL_WIDTH : CN_LABEL_WIDTH;
    });

    const dialogTop = computed(() => {
      const top = (window.innerHeight - DIALOG_HEIGHT) / 2;
      return top < DIALOG_MIN_TOP ? DIALOG_MIN_TOP : top;
    });

    const handleSave = () => {
      emit('update', formData.value.multiline_pattern);
    };
    const handleValueChange = val => {
      emit('cancel', val);
      if (val) {
        // 打开时填入采集页行首正则内容
        formData.value.multiline_pattern = props.oldPattern;
      } else {
        // 关闭时重置数据
        formData.value.log_sample = '';
        formData.value.multiline_pattern = '';
        matchLines.value = null;
      }
    };

    // 匹配验证
    const handleMatch = async () => {
      try {
        await formRef.value?.validate();
        isMatchLoading.value = true;
        const res = await $http.request('collect/regexDebug', {
          params: {
            collector_id: Number(route.params.collectorId),
          },
          data: formData.value,
        });
        matchLines.value = res.data.match_lines;
      } catch (e) {
        console.log(e);
        matchLines.value = 0;
      } finally {
        isMatchLoading.value = false;
      }
    };
    const handleLogSample = (val: string, key: string) => {
      formData.value[key] = val.trim();
    };
    const handleCancel = () => {
      emit('cancel', !props.showDialog);
    };

    return () => (
      <bk-dialog
        width={getDialogWidth.value}
        class='multiline-reg-dialog-box'
        header-position='left'
        mask-close={false}
        ok-text={t('保存')}
        position={{ top: dialogTop.value }}
        title={t('行首正则调试')}
        value={props.showDialog}
        on-cancel={handleCancel}
        on-confirm={handleSave}
        on-value-change={handleValueChange}
      >
        <div class='multiline-reg-dialog-content'>
          <bk-form
            ref={formRef}
            label-width={getLabelWidth.value}
            {...{
              props: {
                model: formData.value,
              },
            }}
          >
            <bk-form-item
              style='margin-bottom: 20px'
              label={t('日志样例')}
              property='log_sample'
              required={true}
              rules={notEmptyRule.value}
            >
              <bk-input
                rows={6}
                type='textarea'
                value={formData.value.log_sample}
                onInput={val => handleLogSample(val, 'log_sample')}
              />
            </bk-form-item>
            <bk-form-item
              style='margin-bottom: 20px'
              label={t('行首正则表达式')}
              property='multiline_pattern'
              required={true}
              rules={notEmptyRule.value}
            >
              <bk-input
                value={formData.value.multiline_pattern}
                onInput={val => handleLogSample(val, 'multiline_pattern')}
              />
            </bk-form-item>
          </bk-form>
          <div
            style={`padding-left: ${getLabelWidth.value}px;`}
            class='test-container'
          >
            <bk-button
              class='mr15'
              loading={isMatchLoading.value}
              theme='primary'
              on-click={handleMatch}
            >
              {t('匹配验证')}
            </bk-button>
            {matchLines.value !== null && (
              <div class='test-result'>
                <span
                  class={matchLines.value ? 'bk-icon icon-check-circle-shape' : 'bk-icon icon-close-circle-shape'}
                />
                {matchLines.value ? (
                  <i18n path='成功匹配 {0} 条日志'>
                    <span class='match-counts'>{matchLines.value}</span>
                  </i18n>
                ) : (
                  <span>{t('未成功匹配')}</span>
                )}
              </div>
            )}
          </div>
        </div>
      </bk-dialog>
    );
  },
});
