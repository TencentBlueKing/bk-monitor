<template>
  <TPopup
    v-model:visible="visible"
    overlay-class-name="bklog-v3-popover-tag save-as-template-popup"
    placement="bottom-right"
    trigger="click"
  >
    <span style="color: #3a84ff; cursor: pointer">
      <span style="font-size: 14px" class="bklog-icon bklog-save"></span>
      {{ $t('另存为模板') }}
    </span>
    <template #content>
      <TForm ref="formRef" class="save-as-form" :data="formModel" :rules="rules" layout="vertical">
        <TFormItem name="editStr" :required="true" :rules="rules.editStr" :label="$t('模板名称')">
          <TInput v-model="formModel.editStr" class="template-name-input" />
        </TFormItem>
        <div class="button-wrap">
          <TButton variant="text" theme="primary" @click="handleConfirm">
            {{ $t('确定') }}
          </TButton>
          <TButton variant="text" theme="primary" @click="handleCancel">
            {{ $t('取消') }}
          </TButton>
        </div>
      </TForm>
    </template>
  </TPopup>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import {
  Popup as TPopup,
  Form as TForm,
  FormItem as TFormItem,
  Input as TInput,
  Button as TButton,
} from 'tdesign-vue-next';
import type { FormInstanceFunctions } from 'tdesign-vue-next';
import type { SortPair } from '../field-settings.types';

import useStore from '@/shared/composables/use-store';

const store = useStore();

const props = defineProps<{
  confirmHandler: (
    updateItem: { editStr: string; sort_list: SortPair[]; display_fields: string[] },
    isCreate: boolean,
    successMsg: string,
  ) => Promise<void>;
  sortList: SortPair[];
  displayFields: string[];
}>();

const defaultSortFields = computed<SortPair[]>(() =>
  (store.state.indexFieldInfo?.default_sort_list ?? []).map(([field, order]: SortPair) => [field, order ?? 'desc']),
);

const formRef = ref<FormInstanceFunctions>();
const visible = ref(false);
const formModel = reactive({ editStr: '' });
const rules = reactive({
  editStr: [{ required: true, message: '必填项' }],
});

const handleConfirm = async () => {
  const result = await formRef.value?.validate();
  if (result !== true) return;

  const sortList = props.sortList?.length ? props.sortList : defaultSortFields.value;
  await props.confirmHandler(
    { editStr: formModel.editStr, display_fields: props.displayFields, sort_list: sortList },
    true,
    '模板保存成功，请在字段模板中查看。',
  );
  handleCancel();
};
const handleCancel = () => {
  visible.value = false;
  formRef.value?.clearValidate();
  Object.assign(formModel, { editStr: '' });
};
</script>

<style lang="scss" scoped>
.save-as-form {
  .template-name-input {
    width: 240px;
  }

  .button-wrap {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 8px;

    button {
      font-size: 12px;
    }
  }
}
</style>
