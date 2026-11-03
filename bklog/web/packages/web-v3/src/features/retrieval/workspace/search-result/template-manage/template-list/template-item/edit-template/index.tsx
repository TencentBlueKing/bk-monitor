
import { MessagePlugin as TDesignMessage, Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
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

import { defineComponent, ref, watch, PropType } from 'vue';
import useLocale from '@/shared/composables/use-locale';


import { type TemplateItem } from '../../../index';

import './index.scss';

export default defineComponent({
  emits: ["cancel","success"],

  name: 'CreateTemplate',
  props: {
    data: {
      type: Object as PropType<TemplateItem>,
      default: () => ({}),
    },
    active: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { expose, emit }) {
    const { t } = useLocale();

    const formRef = ref<any>(null);
    const confirmLoading = ref(false);
    const formData = ref({
      name: '',
    });

    const rules = {
      name: [
        {
          required: true,
          trigger: 'blur',
          validator: (value: string) => !!value,
          message: t('请输入模板名称'),
        },
      ],
    };

    watch(
      () => props.data.template_name,
      name => {
        formData.value.name = name;
      },
      { immediate: true },
    );

    const handleCancel = () => {
      emit('cancel');
    };

    const updateTemplateName = () => {
      confirmLoading.value = true;
      ServicesInstance.logClustering.updateTemplateName({
          params: {
            regex_template_id: props.data.id,
          },
          data: {
            template_name: formData.value.name,
          },
        })
        .then(res => {
          if (res.code === 0) {
            TDesignMessage("success", { content: t('操作成功') });
            emit('success');
          }
        })
        .catch(err => {
          console.error(err);
        })
        .finally(() => {
          confirmLoading.value = false;
        });
    };

    const handleConfirm = () => {
      formRef.value
        .validate()
        .then(() => {
          updateTemplateName();
        })
        .catch((e: unknown) => console.error(e));
    };

    expose({
      data: formData.value.name,
    });

    return () => (
      <div class='edit-template-main'>
        <bk-form
          class='setting-form'
          ref={formRef}
          {...{
            ...{
              model: formData.value,
              rules,
            },
          }}
          form-type='vertical'
        >
          <bk-form-item
            label={t('模板名称')}
            property='name'
            required
            error-display-type='normal'
          >
            <bk-input
              value={formData.value.name}
              onChange={(value: string) => (formData.value.name = value)}
            />
          </bk-form-item>
        </bk-form>
        <div class='operate-btns'>
          <TButton
            theme='primary'
            class='confirm-btn'
            size='small'
            loading={confirmLoading.value}
            onClick={handleConfirm}
          >
            {t('确定')}
          </TButton>
          <TButton
            size='small'
            class='cancel-btn'
            onClick={handleCancel}
          >
            {t('取消')}
          </TButton>
        </div>
      </div>
    );
  },
});
