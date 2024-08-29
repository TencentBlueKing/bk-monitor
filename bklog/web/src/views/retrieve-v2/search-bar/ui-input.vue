<script setup>
  import { ref } from 'vue';

  const props = defineProps({
    modelValue: {},
  });

  const emit = defineEmits(['update:modelValue']);

  const emitChange = event => {
    if (event?.target?.value) {
      emit('update:modelValue', event.target.value);
    }
  };

  const searchItemList = ref([
    { fieldName: 'log-a', fieldValue: 'natural Home', disabled: false },
    { fieldName: 'log-b', fieldValue: 'natural Home', disabled: false },
    { fieldName: 'log-c', fieldValue: 'natural Home natural Home', disabled: false },
    { fieldName: 'log-d', fieldValue: 'natural Home', disabled: false },
    { fieldName: 'log-e', fieldValue: 'natural Home natural Home', disabled: false },
  ]);

  const handleAddItem = () => {
    const index = Math.ceil(Math.random() * 10);
    searchItemList.value.push({ fieldName: `log-${index}`, fieldValue: 'natural Home', disabled: false });
  };

  const handleDisabledTagItem = item => {
    item.disabled = !item.disabled;
  };

  const handleDeleteTagItem = index => {
    searchItemList.value.splice(index, 1);
  };
</script>
<template>
  <ul class="search-items">
    <li
      class="search-item btn-add"
      @click="handleAddItem"
    >
      <div class="tag-add"><i class="log-icon icon-plus"></i></div>
      <div class="tag-text">{{ $t('添加条件') }}</div>
    </li>
    <li
      :class="['search-item tag-item', { disabled: item.disabled }]"
      v-for="(item, index) in searchItemList"
    >
      <div class="tag-row match-name">{{ item.fieldName }}<span class="symbol">=</span></div>
      <div class="tag-row match-value">{{ item.fieldValue }}</div>
      <div class="tag-options">
        <span
          :class="['log-icon', { 'icon-eye': !item.disabled, 'icon-eye-slash': item.disabled }]"
          @click="() => handleDisabledTagItem(item)"
        ></span>
        <span
          class="log-icon icon-close"
          @click="() => handleDeleteTagItem(index)"
        ></span>
      </div>
    </li>
  </ul>
</template>
<style scoped>
  @import './ui-input.scss';
</style>
