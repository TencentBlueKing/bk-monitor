<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->

<template>
  <div
    ref="chartContainer"
    :class="['monitor-echarts-container', { 'is-fold': isFold }]"
    data-test-id="retrieve_div_generalTrendEcharts"
  >
    <chart-title-v2
      class="monitor-echarts-title"
      ref="chartTitle"
      :is-fold="isFold"
      :title="$t('总趋势')"
      :total-count="searchTotal"
      :loading="isLoading"
      @interval-change="handleChangeInterval"
      @toggle-expand="toggleExpand"
    >
    </chart-title-v2>
    <TrendChart
      ref="chartRef"
      v-show="!isFold"
      :is-fold="isFold"
    />
  </div>
</template>

<script setup>
import ChartTitleV2 from '@/components/monitor-echarts/components/chart-title-v2.vue';
import TrendChart from '@/components/monitor-echarts/trend-chart';
import { ref, watch, onMounted, computed, nextTick } from 'vue';
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';

const emit = defineEmits(['toggle-change', 'change-queue-res']);

const store = useStore();
const route = useRoute();
const router = useRouter();

const chartKey = computed(() => store.state.retrieve.chartKey);

const searchTotal = computed(() => {
  if (store.state.searchTotal > 0) {
    return store.state.searchTotal;
  }

  return store.state.retrieve.trendDataCount;
});
const isResultLoading = computed(
  () => store.state.indexSetQueryResult.is_loading || store.state.indexFieldInfo.is_loading
);
const getOffsetHeight = () => chartContainer.value?.offsetHeight ?? 26;

const isFold = ref(false);
const chartContainer = ref(null);
const chartInterval = ref('auto');
const isLoading = computed(() => store.state.retrieve.isTrendDataLoading);

const toggleExpand = val => {
  isFold.value = val;
  localStorage.setItem('chartIsFold', val);
  nextTick(() => {
    emit('toggle-change', !isFold.value, getOffsetHeight());
  });
};

const handleChangeInterval = v => {
  chartInterval.value = v;
  store.commit('updateIndexItem', { interval: v });
  store.commit('retrieve/updateChartKey', { prefix: 'chart_interval_' });
  router.replace({
    query: {
      ...route.query,
      interval: v,
    },
  });
};

onMounted(() => {
  isFold.value = JSON.parse(localStorage.getItem('chartIsFold') || 'true');
  nextTick(() => {
    emit('toggle-change', !isFold.value, getOffsetHeight());
  });
});
</script>

<style scoped lang="scss">
  @import './index.scss';
</style>
