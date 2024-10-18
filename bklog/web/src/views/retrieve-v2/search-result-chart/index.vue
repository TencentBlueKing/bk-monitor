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
  import { ref, watch, onMounted, computed } from 'vue';
  import useStore from '@/hooks/use-store';

  const emit = defineEmits(['toggle-change', 'change-queue-res']);

  const store = useStore();
  const chartKey = computed(() => store.state.retrieve.chartKey);
  const searchTotal = computed(() => store.state.searchTotal);
  const isResultLoading = computed(() => store.state.indexSetQueryResult.is_loading || store.state.indexFieldInfo.is_loading);
  const getOffsetHeight = computed(() => (chartContainer.value?.offsetHeight || 32) - (!isFold.value ? 0 : 110));

  const isFold = ref(false);
  const chartContainer = ref(null);
  const chartInterval = ref('auto');
  const isLoading = computed(() => store.state.retrieve.isTrendDataLoading)


  const toggleExpand = val => {
    isFold.value = val;
    localStorage.setItem('chartIsFold', val);
    emit('toggle-change', !isFold.value, getOffsetHeight.value);
  };

  const handleChangeInterval = v => {
    chartInterval.value = v;
    store.commit('updateIndexItem', { interval: v });
    store.commit('retrieve/updateChartKey', { prefix: 'chart_interval_' });
  };

  onMounted(() => {
    isFold.value = JSON.parse(localStorage.getItem('chartIsFold') || 'false');
    emit('toggle-change', !isFold.value, getOffsetHeight.value);
  });

  watch(() => chartKey.value, () => {
    if (isResultLoading.value) {
      return;
    }

    store.commit('updateIsSetDefaultTableColumn', false);
    store.dispatch('requestIndexSetFieldInfo').then(() => {
      store.dispatch('requestIndexSetQuery', { formChartChange: false });
    });
  }, {
    immediate: true
  });
</script>

<style scoped lang="scss">
  @import './index.scss';
</style>
