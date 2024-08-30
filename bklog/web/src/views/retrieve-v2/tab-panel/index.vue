<script setup>
  import { defineEmits, defineProps } from 'vue';
  const props = defineProps({
    value: {
      type: String,
      required: true,
    },
  });
  const emit = defineEmits(['input']);
  //切换Tab
  //是否显示对应的边框
  const handleActive = panel => {
    emit('input', panel);
  };
</script>
<template>
  <div class="retrieve-tab">
    <span
      :class="[
        'retrieve-panel',
        { 'retrieve-after': ['chartAnalysis'].includes(value) },
        { activeClass: value === 'originalLog' },
      ]"
      @click="handleActive('originalLog')"
      >原始日志</span
    >
    <span
      :class="[
        'retrieve-panel',
        { 'retrieve-after': ['originalLog'].includes(value) },
        { activeClass: value === 'logClustering' },
      ]"
      @click="handleActive('logClustering')"
      >日志聚类</span
    >
    <span
      :class="[
        'retrieve-panel',
        { 'retrieve-after': ['originalLog', 'logClustering'].includes(value) },
        { activeClass: value === 'chartAnalysis' },
      ]"
      @click="handleActive('chartAnalysis')"
      >图表分析</span
    >
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
