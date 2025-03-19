<script setup>
  import { defineEmits, defineProps, computed, watch, ref } from 'vue';
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
  const isUserAction = ref(false);

  const indexSetId = computed(() => store.state.indexId);

  const indexSetItem = computed(() =>
    store.state.retrieve.indexSetList?.find(item => `${item.index_set_id}` === `${indexSetId.value}`),
  );

  const retrieveParams = computed(() => store.getters.retrieveParams);

  const chartParams = computed(() => store.state.indexItem.chart_params);

  const isAiopsToggle = computed(() => {
    return (
      (indexSetItem.value?.scenario_id === 'log' && indexSetItem.value.collector_config_id !== null) ||
      indexSetItem.value?.scenario_id === 'bkdata'
    );
  });

  const isChartEnable = computed(() => indexSetItem.value?.support_doris && !store.getters.isUnionSearch);

  // 可切换Tab数组
  const panelList = computed(() => {
    return [
      { name: 'origin', label: $t('原始日志'), disabled: false },
      { name: 'clustering', label: $t('日志聚类'), disabled: !isAiopsToggle.value },
      { name: 'graphAnalysis', label: $t('图表分析'), disabled: !isChartEnable.value },
    ];
  });

  const renderPanelList = computed(() => panelList.value.filter(item => !item.disabled));

  watch(
    () => indexSetId,
    () => {
      isUserAction.value = false;
    },
  );

  watch(
    () => isAiopsToggle.value,
    () => {
      if (!isAiopsToggle.value && props.value === 'clustering') {
        emit('input', 'origin');
      }
    },
    { immediate: true },
  );

  watch(
    () => isChartEnable.value,
    () => {
      if (!isChartEnable.value && props.value === 'graphAnalysis') {
        emit('input', 'origin');
      }
    },
    {
      immediate: true,
    },
  );

  watch(
    () => chartParams.value,
    () => {
      if (chartParams.value.fromCollectionActiveTab === 'unused') {
        isUserAction.value = false;
        store.commit('updateChartParams', { fromCollectionActiveTab: 'used' });
      }

      if (
        // isUserAction 判定用于避免图表分析页面延迟更新 chartParams 导致触发这里的Tab切换
        !isUserAction.value &&
        isChartEnable.value &&
        props.value !== 'graphAnalysis' &&
        chartParams.value.sql?.length > 0
      ) {
        emit('input', 'graphAnalysis');
      }
    },
    { deep: true, immediate: true },
  );

  const tabClassList = computed(() => {
    return renderPanelList.value.map((item, index) => {
      const isActive = props.value === item.name;
      const isPreItemActive = renderPanelList.value[index - 1]?.name === props.value;

      if (isActive || index === 0 || isPreItemActive) {
        return [];
      }

      return ['border-left'];
    });
  });

  const handleAddAlertPolicy = () => {
    const params = {
      bizId: store.state.bkBizId,
      indexSetId: indexSetId.value,
      scenarioId: '',
      indexStatement: retrieveParams.value.keyword, // 查询语句
      dimension: [], // 监控维度
      condition: [], // 监控条件
    };
    const indexSet = (store.state.retrieve.indexSetList ?? []).find(item => item.index_set_id === indexSetId);
    if (indexSet) {
      params.scenarioId = indexSet.category_id;
    }
    retrieveParams.value.addition.forEach(item => {
      params.condition.push({
        condition: 'and',
        key: item.field,
        method: item.operator === 'eq' ? 'is' : item.operator,
        value: item.value,
      });
    });
    const urlArr = [];
    for (const key in params) {
      if (key === 'dimension' || key === 'condition') {
        urlArr.push(`${key}=${encodeURI(JSON.stringify(params[key]))}`);
      } else {
        urlArr.push(`${key}=${params[key]}`);
      }
    }
    window.open(`${window.MONITOR_URL}/?${urlArr.join('&')}#/strategy-config/add`, '_blank');
  };

  const handleActive = panel => {
    isUserAction.value = true;
    emit('input', panel);
  };
</script>
<template>
  <div
    class="retrieve-tab"
    style="position: relative"
  >
    <span
      v-for="(item, index) in renderPanelList"
      :key="item.label"
      :class="['retrieve-panel', { active: value === item.name }, ...tabClassList[index]]"
      @click="handleActive(item.name)"
      >{{ item.label }}</span
    >
    <div
      class="btn-alert-policy"
      @click="handleAddAlertPolicy"
    >
      <span
        class="bklog-icon bklog--celve"
        style="font-size: 16px"
      ></span>
      <span>{{ $t('添加告警策略') }}</span>
    </div>
  </div>
</template>
<style lang="scss">
  @import './index.scss';
</style>
