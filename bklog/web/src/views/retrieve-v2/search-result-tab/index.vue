<script setup>
import { defineEmits, defineProps, computed, watch, ref, onMounted } from 'vue';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';
import { useRoute } from 'vue-router/composables';
import $http from '@/api';
import DashboardDialog from './components/dashboard-dialog.vue';
const props = defineProps({
  value: {
    type: String,
    required: true,
  },
});


const showDialog = ref(false); // 控制弹窗显示状态
const { $t } = useLocale();
const store = useStore();
const route = useRoute();

const emit = defineEmits(['input']);

const indexSetIds = computed(() => store.state.indexItem.ids);
const bkBizId = computed(() => store.state.bkBizId);

const indexSetItems = computed(() =>
  store.state.retrieve.flatIndexSetList?.filter(item => indexSetIds.value.includes(`${item.index_set_id}`)),
);

const retrieveParams = computed(() => store.getters.retrieveParams);
const requestAddition = computed(() => store.getters.requestAddition);

const isAiopsToggle = computed(() => {
  if (store.getters.isUnionSearch) {
    return false;
  }

  // 日志聚类总开关
  const { bkdata_aiops_toggle: bkdataAiopsToggle } = window.FEATURE_TOGGLE;
  const aiopsBizList = window.FEATURE_TOGGLE_WHITE_LIST?.bkdata_aiops_toggle;
  const isLocalToggle = (indexSetItems.value?.some(i => i.scenario_id === 'log' && i.collector_config_id !== null)) ||
    indexSetItems.value?.some(i => i.scenario_id === 'bkdata');

  switch (bkdataAiopsToggle) {
    case 'on':
      return isLocalToggle;
    case 'off':
      return false;
    default:
      return aiopsBizList ? aiopsBizList.some(item => item.toString() === bkBizId.value) : isLocalToggle;
  }
});

const isChartEnable = computed(() => !store.getters.isUnionSearch && indexSetItems.value?.[0]?.support_doris);
const isGrepEnable = computed(() => !store.getters.isUnionSearch && indexSetItems.value?.[0]?.support_doris);

const isExternal = computed(() => window.IS_EXTERNAL === true);
// 可切换Tab数组
const panelList = computed(() => {
  return [
    { name: 'origin', label: $t('原始日志'), disabled: false },
    { name: 'clustering', label: $t('日志聚类'), disabled: !isAiopsToggle.value },
    { name: 'graphAnalysis', label: $t('图表分析'), disabled: !isChartEnable.value },
    { name: 'grep', label: $t('Grep模式'), disabled:  !isGrepEnable.value },
  ];
});

const renderPanelList = computed(() => panelList.value.filter(item => !item.disabled));

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
const handleDialogUpdate = (newVal) => {
  console.log('handleDialogUpdate', newVal);
  showDialog.value = newVal;
};

const handleCollectionSuccess = () => {
  console.log('收藏成功');
};
const handleAddAlertPolicy = async () => {
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

  if (requestAddition.value.length) {
    const resp = await $http.request('retrieve/generateQueryString', {
      data: {
        addition: requestAddition.value,
      },
    });

    if (resp.result) {
      params.indexStatement = [retrieveParams.value.keyword, resp.data?.querystring]
        .filter(item => item.length > 0 && item !== '*')
        .join(' AND ');
    }
  }

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
const handleAddAlertDashboard = async () => { 
  showDialog.value = true;
};
const handleActive = panel => {
  if (props.value === panel) return;

  emit('input', panel, panel === 'origin');
};

watch(
  () => [isGrepEnable.value, isChartEnable.value, isAiopsToggle.value],
  ([grepEnable, graphEnable, aiopsEnable]) => {
    if (['clustering', 'graphAnalysis', 'grep'].includes(route.query.tab)) {
      if (
        (!grepEnable && route.query.tab === 'grep') ||
        (!graphEnable && route.query.tab === 'graphAnalysis') ||
        (!aiopsEnable && route.query.tab === 'clustering')
      ) {
        handleActive('origin');
      }
    }
  },
);

onMounted(() => {
  const tabName = route.query.tab ?? 'origin';
  if (panelList.value.find(item => item.name === tabName)?.disabled ?? true) {
    handleActive(panelList.value[0].name);
  }
});
</script>
<template>
  <div class="retrieve2-tab">
    <span
      v-for="(item, index) in renderPanelList"
      :key="item.label"
      :class="['retrieve-panel', { active: value === item.name }, ...tabClassList[index]]"
      @click="handleActive(item.name)"
      >{{ item.label }}</span
    >
    <!-- <div class="btn-alert-dashboard" @click="handleAddAlertDashboard">
      <span class="bklog-icon bklog-yibiaopan" style="font-size: 16px"></span>
      <span>{{ $t('添加到仪表盘') }}</span>
    </div> -->
    <div
      class="btn-alert-policy"
      @click="handleAddAlertPolicy"
      v-if="!isExternal"
    >
      <span
        class="bklog-icon bklog--celve"
        style="font-size: 16px"
      ></span>
      <span>{{ $t('添加告警策略') }}</span>
    </div>
  
     <DashboardDialog
      :is-show="showDialog"
      @update:isShow="handleDialogUpdate"
      @on-collection-success="handleCollectionSuccess"
    />
  </div>
</template>
<style lang="scss">
@import './index.scss';
</style>
