<script setup>
  import FieldFilter from './field-filter';
  import useStore from '@/hooks/use-store';
  import { computed } from 'vue';

  const props = defineProps({
    activeTab: { type: String, default: '' },
  });

  const store = useStore();
  const isContentLoading = computed(() => store.state.indexSetQueryResult.is_loading);
  const isFilterLoading = computed(() => store.state.indexFieldInfo.is_loading);
</script>

<template>
  <div class="search-result-panel">
    <FieldFilter v-bkloading="{ isLoading: isFilterLoading }"></FieldFilter>
    <div class="search-result-content" v-bkloading="{ isLoading: isContentLoading }">
      <div
        class="result-table-panel-item"

      ></div>
    </div>
  </div>
</template>

<style scoped>
  @import './index.scss';
</style>
