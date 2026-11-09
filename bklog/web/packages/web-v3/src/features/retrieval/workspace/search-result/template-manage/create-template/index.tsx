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

import { Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { defineComponent, ref } from 'vue';
import useStore from '@/shared/composables/use-store';
import useLocale from '@/shared/composables/use-locale';


import './index.scss';

export default defineComponent({
  emits: ["success"],

  name: 'CreateTemplate',
  setup(props, { slots, emit }) {
    const { t } = useLocale();
    const store = useStore();

    const popoverRef = ref<any>(null);
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

    const handleClickTrigger = () => {
      popoverRef.value.showHandler();
    };

    const handleCancel = () => {
      popoverRef.value.hideHandler();
    };

    const handleShow = () => {
      formRef.value?.clearError();
    };

    const handleHide = () => {
      formData.value.name = '';
    };

    const createTemplate = () => {
      confirmLoading.value = true;
      ServicesInstance.logClustering.createTemplate({
          data: {
            space_uid: store.state.spaceUid,
            template_name: formData.value.name,
          },
        })
        .then(res => {
          if (res.code === 0) {
            emit('success');
            handleCancel();
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
          createTemplate();
        })
        .catch((e: unknown) => console.error(e));
    };

    return () => (
      <bk-popover
        v-slots={{
          content: () => (
            <div>
              <div class='create-template-main'>
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
                    loading={confirmLoading.value}
                    size='small'
                    onClick={handleConfirm}
                  >
                    {t('确定')}
                  </TButton>
                  <TButton
                    size='small'
                    onClick={handleCancel}
                  >
                    {t('取消')}
                  </TButton>
                </div>
              </div>
            </div>
          ),
        }}
        ref={popoverRef}
        width={320}
        ext-cls='create-template-popover'
        trigger='manual'
        tippy-options={{
          placement: 'bottom',
          theme: 'light',
          interactive: true,
        }}
        onHide={handleHide}
        onShow={handleShow}
      >
        <div onClick={handleClickTrigger}>
          {slots.default ? (
            slots.default?.()
          ) : (
            <div class='add-template-btn'>
              <log-icon
                type='plus'
                class='add-icon'
              />
            </div>
          )}
        </div>
      </bk-popover>
    );
  },
});
