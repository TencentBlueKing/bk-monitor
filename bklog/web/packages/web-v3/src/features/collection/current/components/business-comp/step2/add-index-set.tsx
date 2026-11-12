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
import { Button as TButton, Form as TForm, FormItem as TFormItem, Input as TInput } from 'tdesign-vue-next';
import type { FormInstanceFunctions, FormRules } from 'tdesign-vue-next';
import type { ServiceOperation } from '@/platform/services/runtime/service-client';
import { ServicesInstance } from '@/platform/services';

import { defineComponent, type PropType, ref, nextTick, computed, onMounted } from 'vue';

import useLocale from '@/shared/composables/use-locale';


import { showMessage } from '../../../utils';

import type { IListItemData } from '../../../type';

import './add-index-set.scss';

interface IndexGroupResponse {
  result?: boolean;
  message?: string;
}

/** 日志采集 - 新建/修改索引集 */
export default defineComponent({
  name: 'AddIndexSet',
  props: {
    data: {
      type: Object as PropType<IListItemData>,
      default: () => ({}),
    },
    isFrom: {
      type: Boolean,
      default: true,
    },
    isAdd: { type: Boolean, default: false },
  },

  emits: ['submit', 'cancel'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useApplicationStore();
    const inputRef = ref<{ focus?: () => void } | null>(null);
    const editFormRef = ref<FormInstanceFunctions | null>(null);
    const loading = ref(false);
    const submitError = ref('');
    const editFormRules: FormRules<IListItemData> = {
      index_set_name: [
        {
          required: true,
          message: t('请输入索引集名称'),
          trigger: 'blur',
        },
        {
          min: 1,
          max: 50,
          message: t('索引集名称长度应在1-50个字符之间'),
          trigger: 'blur',
        },
      ],
    };
    const editData = ref<IListItemData>({
      index_set_name: '',
    });
    const spaceUid = computed(() => store.spaceUid);

    onMounted(() => {
      editData.value = { ...props.data };
    });

    const failureMessage = (error: unknown) => {
      if (typeof error === 'string' && error) return error;
      if (error instanceof Error && error.message) return error.message;
      if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
        return error.message;
      }
      return t('操作失败');
    };

    const handleRequest = async (config: { method: ServiceOperation; params?: Record<string, unknown>; data?: unknown; message: string }) => {
      loading.value = true;
      submitError.value = '';
      try {
        const res = await config.method({
          params: config.params,
          data: config.data,
        }) as IndexGroupResponse;

        if (res.result) {
          showMessage(config.message);
          emit('submit', editData.value);
          handleEditGroupCancel();
          return;
        }
        submitError.value = res.message || t('操作失败');
        showMessage(submitError.value, 'error');
      } catch (error) {
        submitError.value = failureMessage(error);
        console.log('操作失败:', error);
      } finally {
        loading.value = false;
      }
    };

    const handleEditGroupSubmit = async () => {
      if (loading.value) {
        return;
      }
      try {
        const valid = await editFormRef.value?.validate();
        if (valid !== true) return;
        const { index_set_id, index_set_name } = editData.value;
        const method = props.isAdd ? ServicesInstance.collect.addIndexGroup : ServicesInstance.collect.updateIndexGroup;
        const message = props.isAdd ? t('新增成功') : t('更新成功');
        const baseConfig = { message, method };
        const dataConfig = props.isAdd
          ? { data: { space_uid: spaceUid.value, index_set_name } }
          : { params: { index_set_id }, data: { index_set_name } };
        const config = { ...baseConfig, ...dataConfig };

        await handleRequest(config);
      } catch (error) {
        submitError.value = failureMessage(error);
        console.log('操作失败:', error);
      }
    };

    const handleEditGroupCancel = () => {
      if (loading.value) {
        return;
      }
      emit('cancel');
    };
    const autoFocus = () => {
      nextTick(() => {
        inputRef.value?.focus?.();
      });
    };
    expose({ autoFocus });

    const renderButtons = () => {
      if (props.isFrom) {
        return (
          <div class='add-btns'>
            <TButton
              class='mr8'
              size='small'
              theme='primary'
              loading={loading.value}
              onClick={handleEditGroupSubmit}
            >
              {t('确定')}
            </TButton>
            <TButton theme="default"
              size='small'
              loading={loading.value}
              onClick={handleEditGroupCancel}
            >
              {t('取消')}
            </TButton>
          </div>
        );
      }
      return (
        <span
          class={{
            'icon-btns': true,
            disabled: loading.value,
          }}
        >
          <span
            class='bk-icon icon-check-line submit-icon'
            onClick={handleEditGroupSubmit}
          />
          <span
            class='bk-icon icon-close-line-2 close-icon'
            onClick={handleEditGroupCancel}
          />
        </span>
      );
    };

    const renderAddIndexSet = () => (
      <div class={props.isFrom ? 'popover-add-index-set' : 'add-index-set-input-main'}>
        {props.isFrom && <div class='title'>{props.isAdd ? t('新建索引集') : t('重命名')}</div>}
        <TForm
          ref={editFormRef}
          class='add-index-set-form'
          data={editData.value}
          labelAlign={props.isFrom ? 'top' : 'left'}
          labelWidth={props.isFrom ? undefined : 0}
          rules={editFormRules}
        >
          <TFormItem
            label={props.isFrom ? t('索引集名称') : ''}
            name='index_set_name'
            requiredMark={props.isFrom}
          >
            <TInput
              ref={inputRef}
              maxlength={50}
              placeholder={props.isFrom ? t('请输入') : t('请输入索引集名称')}
              value={editData.value.index_set_name}
              clearable
              onChange={(val: string | number | undefined) => {
                editData.value.index_set_name = val == null ? '' : String(val);
                submitError.value = '';
              }}
              onEnter={(_value, { e }) => {
                e.stopPropagation();
                e.preventDefault();
                handleEditGroupSubmit();
              }}
            />
          </TFormItem>
        </TForm>
        {submitError.value ? <div class='add-index-set-error'>{submitError.value}</div> : null}
        {renderButtons()}
      </div>
    );

    return () => <div class='add-index-set-box'>{renderAddIndexSet()}</div>;
  },
});
