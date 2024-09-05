<script setup>
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
  const { modelValue } = useFocusInput(props, formatModelValueItem);
</script>
<template>
  <ul class="search-sql-query">
    <li
      v-for="(item, index) in modelValue"
      :key="`${item.field}-${index}`"
    >
      <template v-if="item.is_focus_input">
        <input type="text" />
      </template>
    </li>
  </ul>
</template>
<style scoped>
  .search-sql-query {
  }
</style>
