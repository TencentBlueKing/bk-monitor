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
    <chart-title
      ref="chartTitle"
      :is-fold="isFold"
      :title="$t('总趋势')"
      :total-count="totalNumShow"
      @interval-change="handleChangeInterval"
      @toggle-expand="toggleExpand"
    >
    </chart-title>
    <MonitorEcharts
      ref="chartRef"
      v-show="!isFold"
      :is-fold="isFold"
    />
  </div>
</template>

<script setup>
  import ChartTitle from '@/components/monitor-echarts/components/chart-title-new.vue';
  import MonitorEcharts from '@/components/monitor-echarts/monitor-echarts-new';
  import { ref, nextTick, emit } from 'vue';

  const isFold = ref(false);
  const chartContainer = ref(null);
  const chartInterval = ref('auto');
  const totalNumShow = ref(0);

  const toggleExpand = isFold => {
    isFold.value = isFold;
    localStorage.setItem('chartIsFold', isFold);
    nextTick(() => {
      $emit('toggle-change', !isFold.value, chartContainer.value?.offsetHeight);
    });
  };

  const handleChangeInterval = v => {
    chartInterval.value = v;
  };
</script>

<style scoped lang="scss">
  @import './index.scss';
</style>
