<script setup>
  import useFocusInput from './use-focus-input';
  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  const formatModelValueItem = item => {
    return item;
  };
  const { modelValue, inputValue, handleInputBlur } = useFocusInput(props, formatModelValueItem);

  const handleTextInputBlur = e => {
    inputValue.value = '';
    handleInputBlur(e);
  };
</script>
<template>
  <ul class="search-sql-query">
    <li
      class="search-result-item"
      v-for="(item, index) in modelValue"
      :key="`${item.field}-${index}`"
    >
      <template v-if="item.is_focus_input">
        <input
          class="tag-option-focus-input"
          type="text"
          v-model="inputValue"
          @blur="handleTextInputBlur"
        />
      </template>
    </li>
  </ul>
</template>
<style scoped>
  .search-sql-query {
    display: inline-flex;
    flex-wrap: wrap;
    width: 100%;
    max-height: 135px;
    padding: 4px;
    padding-bottom: 0;
    margin: 0;
    overflow: auto;

    li {
      input.tag-option-focus-input {
        width: 8px;
        height: 38px;
        font-size: 12px;
        color: #63656e;
        border: none;
      }
    }
  }
</style>
