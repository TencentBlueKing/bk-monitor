<script setup>
  import PanelFilter from './panel-filter.vue';
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
  <div class="result-table-panel">
    <PanelFilter  v-bkloading="{isLoading: isFilterLoading, size: 'mini', zIndex: 10}"></PanelFilter>
    <div class="result-table-panel-content">
      <div class="result-table-panel-item" v-bkloading="{isLoading: isContentLoading, size: 'mini', zIndex: 10}"></div>
    </div>
  </div>
</template>

<style scoped>
  @import './index.scss';
</style>
