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
  <div class="data-status-container">
    <section class="partial-content">
      <div class="main-title">
        {{ $t('数据趋势') }}
      </div>
      <div class="charts-container">
        <minute-chart />
        <daily-chart />
      </div>
    </section>
    <section
      v-if="!isMasking"
      class="partial-content"
    >
      <div class="main-title">
        {{ $t('数据采样') }}
        <div
          class="refresh-button"
          @click="fetchDataSampling"
        >
          <span class="bk-icon icon-refresh"></span>
          <span>{{ $t('刷新') }}</span>
        </div>
      </div>
      <data-sampling
        :data="dataSamplingList"
        :loading="dataSamplingLoading"
      />
    </section>
  </div>
</template>

<script>
  import DailyChart from './daily-chart';
  import DataSampling from './data-sampling';
  import MinuteChart from './minute-chart';

  export default {
    components: {
      DataSampling,
      MinuteChart,
      DailyChart,
    },
    props: {
      collectorData: {
        type: Object,
        require: true,
      },
    },
    data() {
      return {
        dataSamplingLoading: true,
        dataSamplingList: [],
        isMasking: false,
      };
    },
    async created() {
      try {
        this.dataSamplingLoading = true;
        this.isMasking = await this.getMaskingConfig(); // 获取脱敏配置信息
        if (!this.isMasking) this.fetchDataSampling(); // 未脱敏才能查看是否采样
      } catch (error) {
        this.dataSamplingLoading = false;
      }
    },
    methods: {
      /**
       * @desc: 判断当前是采集项是否有脱敏
       * @returns {Array}
       */
      async getMaskingConfig() {
        try {
          await this.$http.request(
            'masking/getMaskingConfig',
            {
              params: { index_set_id: this.collectorData?.index_set_id },
            },
            { catchIsShowMessage: false },
          );
          return true;
        } catch (err) {
          return false;
        }
      },
      // 数据采样
      async fetchDataSampling() {
        try {
          this.dataSamplingLoading = true;
          const dataSamplingRes = await this.$http.request('source/dataList', {
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
          });
          this.dataSamplingList = dataSamplingRes.data;
        } catch (e) {
          console.warn(e);
          this.dataSamplingList = [];
        } finally {
          this.dataSamplingLoading = false;
        }
      },
    },
  };
</script>
