<template>
  <bk-popover
    ref="popoverRef"
    :tippy-options="{ appendTo: 'parent' }"
    placement="bottom-end"
    theme="light"
    trigger="click"
  >
    <span style="color: #3a84ff; cursor: pointer">
      <span
        style="font-size: 14px"
        class="bklog-icon bklog-save"
      ></span>
      {{ $t('另存为模板') }}
    </span>
    <template #content>
      <bk-form
        ref="formRef"
        class="save-as-form"
        :model="formModel"
        :rules="rules"
        form-type="vertical"
      >
        <bk-form-item
          :property="'editStr'"
          :required="true"
          :rules="rules.name"
          label="模板名称"
        >
          <bk-input
            class="template-name-input"
            v-model="formModel.editStr"
          />
        </bk-form-item>
        <div class="button-wrap">
          <bk-button
            theme="primary"
            text
            @click="handleConfirm"
          >
            确定
          </bk-button>
          <bk-button
            theme="primary"
            text
            @click="handleCancel"
          >
            取消
          </bk-button>
        </div>
      </bk-form>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  import { reactive, ref } from 'vue';

  const props = defineProps<{
    confirmHandler: (
      updateItem: { editStr: string; sort_list: any[]; display_fields: any[] },
      isCreate: boolean,
      successMsg: string,
    ) => Promise<void>;
    sortList: any[];
    displayFields: any[];
  }>();

  const formRef = ref(null);
  const popoverRef = ref(null);
  const formModel = reactive({ editStr: '' });
  const rules = reactive({
    name: [{ required: true, message: '必填项' }],
  });

  const handleConfirm = async () => {
    await formRef.value.validate();

    await props.confirmHandler(
      { editStr: formModel.editStr, display_fields: props.displayFields, sort_list: props.sortList },
      true,
      '模板保存成功，请在字段模板中查看。',
    );
    handleCancel();
  };
  const handleCancel = () => {
    popoverRef.value.hideHandler();
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

      button{
        font-size: 12px;
      }
    }
  }
</style>
