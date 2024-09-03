<script setup>
  import PanelFilter from './panel-filter.vue';
  const props = defineProps({
    activeTab: { type: String, default: '' },
  });
</script>

<template>
  <div class="result-table-panel">
    <PanelFilter></PanelFilter>
    <div class="result-table-panel-content"></div>
  </div>
</template>

<style scoped>
  @import './index.scss';
</style>
