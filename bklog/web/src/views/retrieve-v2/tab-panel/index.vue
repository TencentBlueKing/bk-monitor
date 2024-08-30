<script setup>
  import { defineEmits, defineProps, computed } from 'vue';
  import useLocale from '@/hooks/use-locale';
  const { $t } = useLocale();
  const props = defineProps({
    value: {
      type: String,
      required: true,
    },
  });
  const emit = defineEmits(['input']);
  //可切换Tab数组
  const panelList = computed(() => {
    const list = [
      { name: 'origin', label: $t('原始日志') },
      { name: 'clustering', label: $t('日志聚类') },
      { name: 'chartAnalysis', label: $t('图表分析') },
    ];
    return list;
  });
  // after边框
  const isAfter = item => {
    const afterListMap = {
      origin: ['chartAnalysis'],
      clustering: ['origin'],
      chartAnalysis: ['origin', 'clustering'],
    };

    const afterList = afterListMap[item.name] || ['chartAnalysis'];
    return afterList.includes(props.value);
  };
  //是否显示对应的边框
  const handleActive = panel => {
    emit('input', panel);
  };
</script>
<template>
  <div class="retrieve-tab">
    <span
      v-for="item in panelList"
      :class="['retrieve-panel', { 'retrieve-after': isAfter(item) }, { activeClass: value === item.name }]"
      @click="handleActive(item.name)"
      >{{ item.label }}</span
    >
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
