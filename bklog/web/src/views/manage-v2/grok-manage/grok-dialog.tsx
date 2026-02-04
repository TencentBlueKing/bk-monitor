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

import { t } from '@/hooks/use-locale';

import { IGrokItem } from './types';

import './grok-dialog.scss';

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
    const formRef = ref(null);

    // 表单数据
    const formData = ref({
      name: '',
      description: '',
      pattern: '',
    });

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
    };

    // 弹窗标题
    const dialogTitle = computed(() => {
      return props.isEdit ? t('编辑 Grok 模式') : t('新建 Grok 模式');
    });

    // 重置表单
    const resetForm = () => {
      formData.value = {
        name: '',
        description: '',
        pattern: '',
      };
    };

    // 监听弹窗显示和编辑数据变化
    watch(
      () => props.isShow,
      (isShow) => {
        if (isShow) {
          if (props.isEdit && props.editData) {
            // 编辑模式，填充数据
            formData.value = {
              name: props.editData.name || '',
              description: props.editData.description || '',
              pattern: props.editData.pattern || '',
            };
          }
        } else {
          resetForm();
          formRef.value?.clearError();
        }
      },
    );

    // 确认提交
    const handleConfirm = async () => {
      try {
        await (formRef.value as any)?.validate();
        emit('confirm', {
          ...formData.value,
          id: props.editData?.id,
        });
      } catch (error) {
        console.warn('表单验证失败:', error);
      }
    };

    // 弹窗值变化（关闭弹窗时触发）
    const handleValueChange = (val: boolean) => {
      if (!val) {
        emit('cancel');
      }
    };

    return () => (
      <bk-dialog
        width={640}
        ext-cls='grok-dialog'
        value={props.isShow}
        confirm-fn={handleConfirm}
        header-position='left'
        mask-close={false}
        title={dialogTitle.value}
        transfer
        on-value-change={handleValueChange}
      >
        <div
          class='grok-dialog-content'
          v-bkloading={{ isLoading: props.loading }}
        >
          <bk-form
            ref={formRef}
            form-type='vertical'
            label-width={590}
            {...{
              props: {
                model: formData.value,
                rules: formRules,
              },
            }}
          >
            <bk-form-item
              label={t('名称')}
              property='name'
              required
            >
              <bk-input
                disabled={props.isEdit}
                value={formData.value.name}
                placeholder={t('仅支持大写字母、下划线')}
                on-change={(val: string) => (formData.value.name = val)}
              />
            </bk-form-item>
            <bk-form-item label={t('描述')}>
              <bk-input
                value={formData.value.description}
                placeholder={t('选填')}
                on-change={(val: string) => (formData.value.description = val)}
              />
            </bk-form-item>
            <bk-form-item
              label={t('Grok 定义（可引用其他模式）')}
              property='pattern'
              required
            >
              <bk-input
                value={formData.value.pattern}
                type='textarea'
                rows={4}
                placeholder={t('例如  %{IPORHOST: client} %{HTTPVERB:verb} %{URIPATHPARAM:path}')}
                maxlength={100}
                show-word-limit
                on-change={(val: string) => (formData.value.pattern = val)}
              />
            </bk-form-item>
          </bk-form>
        </div>
      </bk-dialog>
    );
  },
});
