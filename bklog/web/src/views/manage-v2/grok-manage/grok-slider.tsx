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

import { computed, defineComponent, reactive, ref, watch } from 'vue';

import http from '@/api';
import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { useSidebarDiff } from '@/views/manage-v2/hooks/use-sidebar-diff';

import { DebugStatus, IGrokItem } from './types';

import './grok-slider.scss';

export default defineComponent({
  name: 'GrokDialog',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    editData: {
      type: Object as () => IGrokItem | null,
      default: null,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['confirm', 'cancel'],
  setup(props, { emit }) {
    const store = useStore();
    const formRef = ref(null);

    // 表单数据
    const formData = reactive({
      name: '',
      description: '',
      pattern: '',
      sample: '',
    });

    // 使用侧栏变更检测 hooks
    const { initSidebarFormData, handleCloseSidebar } = useSidebarDiff(formData);

    // 调试相关状态
    const debugStatus = ref<DebugStatus>(DebugStatus.NONE); // 调试状态
    const debugResult = ref(''); // 调试结果
    const debugLoading = ref(false); // 调试加载状态
    const debugErrorMsg = ref(''); // 调试错误信息

    // 记录上次调试成功时的 pattern 和 sample
    const lastDebuggedPattern = ref('');
    const lastDebuggedSample = ref('');

    // 表单验证规则
    const formRules = {
      name: [
        {
          required: true,
          trigger: 'blur',
        },
        {
          validator: (val: string) => /^[A-Z_]+$/.test(val),
          message: t('仅支持大写字母、下划线'),
          trigger: 'blur',
        },
      ],
      pattern: [
        {
          required: true,
          trigger: 'blur',
        },
      ],
      sample: [
        {
          required: true,
          trigger: 'blur',
        },
      ],
    };

    // 侧栏标题
    const sliderTitle = computed(() => {
      return props.isEdit ? t('编辑 Grok 模式') : t('新建 Grok 模式');
    });

    // 提交按钮是否可用（仅调试成功后启用）
    const canSubmit = computed(() => {
      return debugStatus.value === DebugStatus.SUCCESS;
    });

    // 提交按钮的 tooltip 内容
    const submitTooltip = computed(() => {
      if (canSubmit.value) {
        return '';
      }
      return t('请先完成调试，方可提交');
    });

    // 重置表单
    const resetForm = () => {
      formData.name = '';
      formData.description = '';
      formData.pattern = '';
      formData.sample = '';
      debugStatus.value = DebugStatus.NONE;
      debugResult.value = '';
      debugErrorMsg.value = '';
      lastDebuggedPattern.value = '';
      lastDebuggedSample.value = '';
    };

    // 监听侧栏显示和编辑数据变化
    watch(
      () => props.isShow,
      (isShow) => {
        if (isShow) {
          if (props.isEdit && props.editData) {
            // 编辑模式，填充数据
            formData.name = props.editData.name || '';
            formData.description = props.editData.description || '';
            formData.pattern = props.editData.pattern || '';
          }
          // 初始化侧栏表单数据，用于变更检测
          initSidebarFormData();
        } else {
          resetForm();
          formRef.value?.clearError();
        }
      },
    );

    // 监听 pattern 和 sample 的变化，更新调试状态
    watch(
      () => [formData.pattern, formData.sample],
      () => {
        // 如果已调试成功，检测内容是否变更
        if (debugStatus.value === DebugStatus.SUCCESS) {
          if (
            formData.pattern !== lastDebuggedPattern.value
            || formData.sample !== lastDebuggedSample.value
          ) {
            debugStatus.value = DebugStatus.CHANGED;
          }
        }
      },
    );

    // 调试功能
    const handleDebug = async () => {
      try {
        await Promise.all([
          (formRef.value as any)?.validateField('pattern'),
          (formRef.value as any)?.validateField('sample'),
        ]);

        debugLoading.value = true;
        debugStatus.value = DebugStatus.NONE;
        debugResult.value = '';
        debugErrorMsg.value = '';

        const response = await http.request('grok/debugGrok', {
          data: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            pattern: formData.pattern,
            sample: formData.sample,
          },
        });

        // 处理调试结果
        const data = response.data;
        if (data === null) {
          // 匹配失败，不展示结果
          debugStatus.value = DebugStatus.FAILED;
          debugResult.value = '';
        } else {
          // 调试成功
          debugStatus.value = DebugStatus.SUCCESS;
          // 获取除 _matched 外的其他字段
          const { _matched, ...rest } = data;
          // 如果只有 _matched 字段，显示其内容（字符串）
          // 否则显示剩下的键值对，格式为 key: value
          if (Object.keys(rest).length === 0) {
            debugResult.value = _matched;
          } else {
            debugResult.value = Object.entries(rest)
              .map(([key, value]) => `${key}: ${value}`)
              .join(',');
          }
        }
        // 记录调试的内容
        lastDebuggedPattern.value = formData.pattern;
        lastDebuggedSample.value = formData.sample;
      } catch (error: any) {
        console.warn('调试失败:', error);
      } finally {
        debugLoading.value = false;
      }
    };

    // 确认提交
    const handleConfirm = async () => {
      if (!canSubmit.value) {
        return;
      }

      try {
        await (formRef.value as any)?.validate();
        emit('confirm', {
          ...formData,
          sample: debugResult.value,
          id: props.editData?.id,
        });
      } catch (error) {
        console.warn('表单验证失败:', error);
      }
    };

    // 取消/关闭侧栏
    const handleCancel = async () => {
      const canClose = await handleCloseSidebar();
      if (canClose) {
        emit('cancel');
      }
    };

    // 渲染调试状态
    const renderDebugStatus = () => {
      if (debugStatus.value === DebugStatus.NONE) {
        return null;
      }

      if (debugStatus.value === DebugStatus.SUCCESS) {
        return (
          <div class='debug-status debug-status-success'>
            <i class='bk-icon icon-check-circle-shape'></i>
            <span class='status-text'>{t('调试成功')}</span>
          </div>
        );
      }

      if (debugStatus.value === DebugStatus.CHANGED) {
        return (
          <div class='debug-status debug-status-warning'>
            <i class='bk-icon icon-exclamation-circle-shape'></i>
            <span class='status-text'>{t('内容有变更，请重新调试')}</span>
          </div>
        );
      }

      if (debugStatus.value === DebugStatus.FAILED) {
        return (
          <div class='debug-status debug-status-error'>
            <i class='bk-icon icon-close-circle-shape'></i>
            <span class='status-text'>{debugErrorMsg.value || t('调试失败')}</span>
          </div>
        );
      }

      return null;
    };

    // 渲染调试结果
    const renderDebugResult = () => {
      if (debugStatus.value !== DebugStatus.SUCCESS || !debugResult.value) {
        return null;
      }

      return (
        <div class='debug-result'>
          <div class='debug-result-content'>{debugResult.value}</div>
        </div>
      );
    };

    // 渲染提交按钮
    const renderSubmitButton = () => {
      return (
        <span
          v-bk-tooltips={{
            placement: 'bottom',
            content: submitTooltip.value,
            disabled: canSubmit.value,
          }}
        >
          <bk-button
            theme='primary'
            disabled={!canSubmit.value}
            loading={props.loading}
            onClick={handleConfirm}
          >
            {t('提交')}
          </bk-button>
        </span>
      );
    };

    return () => (
      <bk-sideslider
        width={640}
        ext-cls='grok-slider'
        is-show={props.isShow}
        title={sliderTitle.value}
        quick-close={true}
        transfer
        before-close={handleCancel}
      >
        <template slot='content'>
          <div
            class='grok-slider-content'
            v-bkloading={{ isLoading: props.loading }}
          >
            <bk-form
              ref={formRef}
              form-type='vertical'
              label-width={560}
              {...{
                props: {
                  model: formData,
                  rules: formRules,
                },
              }}
            >
              {/* 名称 */}
              <bk-form-item
                label={t('名称')}
                property='name'
                required
              >
                <bk-input
                  disabled={props.isEdit}
                  value={formData.name}
                  placeholder={t('仅支持大写字母、下划线')}
                  on-change={(val: string) => (formData.name = val)}
                />
              </bk-form-item>

              {/* 描述 */}
              <bk-form-item label={t('描述')}>
                <bk-input
                  value={formData.description}
                  placeholder={t('选填')}
                  on-change={(val: string) => (formData.description = val)}
                />
              </bk-form-item>

              {/* Grok 定义 */}
              <bk-form-item
                label={t('Grok 定义（可引用其他模式）')}
                property='pattern'
                required
              >
                <bk-input
                  value={formData.pattern}
                  type='textarea'
                  rows={4}
                  placeholder={t('例如  %{IPORHOST: client} %{HTTPVERB:verb} %{URIPATHPARAM:path}')}
                  maxlength={100}
                  show-word-limit
                  on-change={(val: string) => (formData.pattern = val)}
                />
              </bk-form-item>

              {/* 调试区域 */}
              <div class='debug-section'>
                <div class='debug-section-title'>{t('调试')}</div>

                {/* 输入样例 */}
                <bk-form-item
                  label={t('输入样例')}
                  property='sample'
                  required
                >
                  <bk-input
                    value={formData.sample}
                    type='textarea'
                    rows={4}
                    placeholder={t('请输入需要调试的样例')}
                    maxlength={100}
                    show-word-limit
                    on-change={(val: string) => (formData.sample = val)}
                  />
                </bk-form-item>

                {/* 调试按钮和状态 */}
                <div class='debug-action'>
                  <bk-button
                    theme='primary'
                    outline
                    loading={debugLoading.value}
                    onClick={handleDebug}
                  >
                    {t('调试')}
                  </bk-button>
                  {renderDebugStatus()}
                </div>

                {/* 调试结果 */}
                {renderDebugResult()}
              </div>

              {/* 底部按钮 */}
              <bk-form-item class='slider-footer'>
                {renderSubmitButton()}
                <bk-button onClick={handleCancel}>{t('取消')}</bk-button>
              </bk-form-item>
            </bk-form>
          </div>
        </template>
      </bk-sideslider>
    );
  },
});
