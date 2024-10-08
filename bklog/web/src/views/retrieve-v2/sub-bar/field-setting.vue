<script setup>
  import { computed, ref } from 'vue';
  import FieldsSetting from '../result-comp/fields-setting';
  import useStore from '@/hooks/use-store';

  const store = useStore();
  const isShowFieldsSetting = ref(false);
  const retrieveParams = computed(() => store.getters.retrieveParams);

  const emit = defineEmits(['update-log-fields', 'fields-updated', 'should-retrieve']);

  const handleDropdownHide = () => {
    isShowFieldsSetting.value = false;
    requestFiledConfig();
  };
  const requestFiledConfig = () => {
    // !!TODO 用store监听去更新原始日志旁边的快速选中下拉框
  };
  const handleDropdownShow = () => {
    isShowFieldsSetting.value = true;
  };

  const closeDropdown = () => {
    isShowFieldsSetting.value = false;
    fieldsSettingPopper.value?.instance.hide();
  };
  const modifyFields = (displayFieldNames, showFieldAlias) => {
    emit('fields-updated', displayFieldNames, showFieldAlias);
    emit('should-retrieve');
  };

  const confirmModifyFields = (displayFieldNames, showFieldAlias) => {
    modifyFields(displayFieldNames, showFieldAlias);
    closeDropdown();
  };

  const cancelModifyFields = () => {
    closeDropdown();
  };

  const setPopperInstance = (status = true) => {
    fieldsSettingPopper.value?.instance.set({
      hideOnClick: status,
    });
  };
</script>
<template>
  <bk-popover
    ref="fieldsSettingPopper"
    animation="slide-toggle"
    placement="bottom-end"
    theme="light bk-select-dropdown"
    trigger="click"
    :distance="15"
    :offset="0"
    :on-hide="handleDropdownHide"
    :on-show="handleDropdownShow"
  >
    <slot name="trigger">
      <div class="field-setting">
        <i class="bklog-icon bklog-setting"></i>
        {{ $t('字段配置') }}
      </div>
    </slot>
    <template #content>
      <div class="fields-setting-container">
        <FieldsSetting
          v-if="isShowFieldsSetting"
          :retrieve-params="retrieveParams"
          @cancel="cancelModifyFields"
          @confirm="confirmModifyFields"
          @modify-fields="modifyFields"
          @set-popper-instance="setPopperInstance"
        />
      </div>
    </template>
  </bk-popover>
</template>
