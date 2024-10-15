<script setup>
  import { defineEmits, defineProps, computed } from 'vue';
  import useStore from '@/hooks/use-store';
  import useLocale from '@/hooks/use-locale';
  const { $t } = useLocale();
  const store = useStore();
  const props = defineProps({
    value: {
      type: String,
      required: true,
    },
  });
  const emit = defineEmits(['input']);
  const indexSetItem = computed(() =>
    store.state.retrieve.indexSetList?.find(item => item.index_set_id === store.state.indexId),
  );

  const isAiopsToggle = computed(() => {
    return (
      (indexSetItem.value?.scenario_id === 'log' && indexSetItem.value.collector_config_id !== null) ||
      indexSetItem.value?.scenario_id === 'bkdata'
    );
  });

  // 可切换Tab数组
  const panelList = computed(() => {
    return  [
      { name: 'origin', label: $t('原始日志'), disabled: false },
      { name: 'clustering', label: $t('日志聚类'), disabled: !isAiopsToggle.value },
      // { name: 'chartAnalysis', label: $t('图表分析') },
    ];
  });

  const renderPanelList = computed(() => panelList.value.filter(item => !item.disabled));

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

  const handleActive = panel => {
    emit('input', panel);
  };
</script>
<template>
  <div class="retrieve-tab">
    <span
      v-for="item in renderPanelList"
      :key="item.label"
      :class="['retrieve-panel', { 'retrieve-after': isAfter(item) }, { activeClass: value === item.name }]"
      @click="handleActive(item.name)"
      >{{ item.label }}</span
    >
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
