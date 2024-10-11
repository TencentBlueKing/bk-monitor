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
  const isExternal = computed(() => store.state.isExternal);
  const indexItem = computed(() => store.state.indexItem);
  const isAiopsToggle = computed(() => {
    // 日志聚类总开关
    if (isExternal.value || indexItem.value.isUnionIndex) return false; // 外部版或联合查询时不包含日志聚类
    const { bkdata_aiops_toggle: bkdataAiopsToggle } = window.FEATURE_TOGGLE;
    const aiopsBizList = window.FEATURE_TOGGLE_WHITE_LIST?.bkdata_aiops_toggle;
    switch (bkdataAiopsToggle) {
      case 'on':
        return true;
      case 'off':
        return false;
      default:
        return aiopsBizList ? aiopsBizList.some(item => item.toString() === this.bkBizId) : false;
    }
  });
  // 可切换Tab数组
  const panelList = computed(() => {
    const list = [
      { name: 'origin', label: $t('原始日志') },
      // { name: 'clustering', label: $t('日志聚类') },
      // { name: 'chartAnalysis', label: $t('图表分析') },
    ];
    if (isAiopsToggle.value) {
      list.push({ name: 'clustering', label: $t('日志聚类') });
    }
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

  const handleActive = panel => {
    emit('input', panel);
  };
</script>
<template>
  <div class="retrieve-tab">
    <span
      v-for="item in panelList"
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
