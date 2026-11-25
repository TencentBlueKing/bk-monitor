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
  <div class="usage-details-container">
    <section class="partial-content">
      <div class="main-title">
        {{ $t('使用统计') }}
        <!-- :disabled="timesChartLoading || frequencyChartLoading || spentChartLoading" -->
        <time-range
          :need-timezone="false"
          :value="chartDateValue"
          @change="handleDateValueChange"
        />
      </div>
      <div class="charts-container collection-detail-chart-grid">
        <chart-component
          :chart-data="timesChartData"
          :loading="timesChartLoading"
          :failed="timesChartFailed"
          @retry="fetchUsageChart('times', 'getIndexTimes')"
          :type="$t('使用次数趋势')"
        />
        <chart-component
          :chart-data="frequencyChartData"
          skeleton-type="bar"
          :loading="frequencyChartLoading"
          :failed="frequencyChartFailed"
          @retry="fetchUsageChart('frequency', 'getIndexFrequency')"
          :type="$t('用户使用频次')"
        />
        <chart-component
          :chart-data="spentChartData"
          skeleton-type="pie"
          :loading="spentChartLoading"
          :failed="spentChartFailed"
          @retry="fetchUsageChart('spent', 'getIndexSpent')"
          :type="$t('检索耗时统计')"
        />
      </div>
    </section>

    <section class="partial-content">
      <div class="main-title">
        {{ $t('检索记录') }}
        <div class="usage-record-actions">
          <time-range
            :timezone="timezone"
            :value="tableDateValue"
            @change="handleTableDateValueChange"
            @timezone-change="handleTimezoneChange"
          />
          <TButton theme="primary" variant="text" :loading="tableLoading" @click="fetchTableData">
            <template #icon><span class="bk-icon icon-refresh" aria-hidden="true"></span></template>
            {{ $t('刷新') }}
          </TButton>
        </div>
      </div>
      <bk-table
        :loading="tableLoading"
        :data="tableData"
        :max-height="526"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-limit-change="handlePageLimitChange"
      >
        <bk-table-column
          native-cell-slot
          :label="$t('时间')"
          min-width="10"
        >
          <template #default="{ row }">
            {{ utcFormatDate(row.created_at, true) }}
          </template>
        </bk-table-column>
        <bk-table-column
          native-cell-slot
          :label="$t('执行人')"
          min-width="10"
          prop="created_by"
        >
          <template #default="{ row }">
            <bk-user-display-name :user-id="row.created_by"></bk-user-display-name>
          </template>
        </bk-table-column>
        <bk-table-column
          native-cell-slot
          :label="$t('查询语句')"
          min-width="20"
        >
          <template #default="{ row }">
            <div class="table-ceil-container">
              <span
                v-log-overflow-tips
                class="table-view-span-detail"
                >{{ row.query_string }}</span
              >
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          native-cell-slot
          :label="$t('耗时(s)')"
          min-width="6"
          prop="duration"
        >
          <template #default="{ row }">
            {{ (row.duration / 1000).toFixed(3) }}
          </template>
        </bk-table-column>
        <template #empty>
          <div class="bklog-table-empty-region">
            <empty-status
              v-if="!tableLoading"
              :empty-type="tableFailed ? '500' : 'empty'"
              @operation="fetchTableData"
            />
          </div>
        </template>
      </bk-table>
    </section>
  </div>
</template>

<script>
import { Button as TButton } from 'tdesign-vue-next';
import { useApplicationStore } from '@/app/state/domains/application-store';
import { ServicesInstance } from '@/platform/services';

  import EmptyStatus from '@/shared/ui/empty-status/index';
  import TimeRange from '@/shared/ui/time-range/time-range';
  import { handleTransformToTimestamp } from '@/shared/ui/time-range/utils';
  import dayjs from 'dayjs';

  import { utcFormatDate } from '../../../../shared/lib/util';
  import { updateTimezone } from '../../../../platform/i18n/dayjs';
  import useUtils from '@/shared/composables/use-utils';
  import ChartComponent from './chart-component';

  export default {
    components: {
      TButton,
      ChartComponent,
      TimeRange,
      EmptyStatus,
    },
    props: {
      indexSetId: {
        type: [String, Number],
        required: true,
      },
    },
    data() {
      return {
        utcFormatDate,
        timesChartLoading: true,
        timesChartFailed: false,
        timesChartRequest: 0,
        timesChartData: null,
        frequencyChartLoading: true,
        frequencyChartFailed: false,
        frequencyChartRequest: 0,
        frequencyChartData: null,
        spentChartLoading: true,
        spentChartFailed: false,
        spentChartRequest: 0,
        spentChartData: null,
        chartDateValue: ['now-7d', 'now'],
        tableLoading: true,
        tableFailed: false,
        tableRequest: 0,
        tableData: [],
        pagination: {
          current: 1,
          count: 0,
          limit: 10,
        },
        tableDateValue: ['now-2d', 'now'],
        timezone: dayjs.tz.guess(),
      };
    },
    created() {
      this.initPage();
    },
    beforeUnmount() {
      updateTimezone();
    },
    methods: {
      initPage() {
        this.fetchChartData();
        this.fetchTableData();
      },
      fetchChartData() {
        this.fetchUsageChart('times', 'getIndexTimes');
        this.fetchUsageChart('frequency', 'getIndexFrequency');
        this.fetchUsageChart('spent', 'getIndexSpent');
      },
      async fetchUsageChart(kind, endpoint) {
        const requestKey = `${kind}ChartRequest`;
        const loadingKey = `${kind}ChartLoading`;
        const failedKey = `${kind}ChartFailed`;
        const dataKey = `${kind}ChartData`;
        const request = ++this[requestKey];
        this[loadingKey] = true;
        this[failedKey] = false;
        try {
          const tempList = handleTransformToTimestamp(this.chartDateValue, useApplicationStore().retrieveParams.format);
          const payload = {
            params: {
              index_set_id: this.indexSetId,
            },
            query: {
              start_time: tempList[0],
              end_time: tempList[1],
            },
          };
          const response = await ServicesInstance.indexSet[endpoint](payload);
          if (request === this[requestKey]) this[dataKey] = response.data;
        } catch (error) {
          if (request !== this[requestKey]) return;
          console.warn(error);
          this[dataKey] = null;
          this[failedKey] = true;
        } finally {
          if (request === this[requestKey]) this[loadingKey] = false;
        }
      },
      /**
       * @desc 使用统计时间筛选
       * @param { Array } val
       */
      handleDateValueChange(val) {
        this.chartDateValue = val;
        this.fetchChartData();
      },
      /**
       * @desc 检索记录时间筛选
       * @param { Array } val
       */
      handleTableDateValueChange(val) {
        this.tableDateValue = val;
        this.fetchTableData();
      },
      handleTimezoneChange(timezone) {
        this.timezone = timezone;
        updateTimezone(timezone);
        this.fetchTableData();
      },
      async fetchTableData() {
        const request = ++this.tableRequest;
        this.tableLoading = true;
        this.tableFailed = false;
        try {
          const tempList = handleTransformToTimestamp(this.tableDateValue, useApplicationStore().retrieveParams.format);
          const res = await ServicesInstance.indexSet.getIndexHistory({
            params: {
              index_set_id: this.indexSetId,
            },
            query: {
              start_time: tempList[0],
              end_time: tempList[1],
              page: this.pagination.current,
              pagesize: this.pagination.limit,
            },
          });
          if (request !== this.tableRequest) return;
          const { formatResponseListTimeZoneString } = useUtils();
          this.pagination.count = res.data.total;
          this.tableData = formatResponseListTimeZoneString(res.data.list || [], {}, ['created_at', 'updated_at']);
        } catch (e) {
          if (request !== this.tableRequest) return;
          console.warn(e);
          this.tableFailed = true;
          this.pagination.count = 0;
          this.tableData.splice(0);
        } finally {
          if (request === this.tableRequest) this.tableLoading = false;
        }
      },
      handlePageChange(page) {
        if (this.pagination.current !== page) {
          this.pagination.current = page;
          this.fetchTableData();
        }
      },
      handlePageLimitChange(limit) {
        this.pagination.current = 1;
        this.pagination.limit = limit;
        this.fetchTableData();
      },
    },
  };
</script>

<style lang="scss" scoped>
  .usage-details-container {
    .usage-record-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      min-width: 0;
      gap: var(--bklog-space-8);
    }

    .time-range-wrap {
      font-size: 12px;
      font-weight: normal;
    }
  }
</style>
