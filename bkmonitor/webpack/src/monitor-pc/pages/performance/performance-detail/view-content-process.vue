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
  <div class="content-process">
    <ul class="process-list">
      <li
        v-for="(item, index) in processList"
        :key="index"
        class="process-list-item"
        :class="{ 'is-active': item.displayName === process }"
        @click="handleProcessChange(item)"
      >
        <span :class="`item-status-${item.status}`" />
        <abnormal-tips
          :tips-text="handleComponentStatusData(item.status).tipsText"
          :link-text="handleComponentStatusData(item.status).linkText"
          :link-url="handleComponentStatusData(item.status).linkUrl"
          :doc-link="handleComponentStatusData(item.status).docLink"
          placement="top"
          :delay="200"
          ext-cls="abnormal-tips-wrap"
          :disabled="![2, 1].includes(transformStatus(item.status))"
        >
          {{ item.displayName }}
        </abnormal-tips>
      </li>
    </ul>
    <ul
      v-if="false"
      class="chart-list"
    >
      <li class="chart-list-item special-item">
        <monitor-echarts
          :key="process + '-text'"
          chart-type="text"
          class="chart-item"
          :title="`${process}${$t('运行时长')}`"
          style="margin-right: 10px"
          height="100"
          :get-series-data="handleGetTextSeries"
        />
        <monitor-echarts
          :key="process + '-status'"
          class="chart-item"
          chart-type="status"
          :title="$t('端口运行状态')"
          height="100"
          :get-series-data="handleGetPortSeries"
        />
      </li>
    </ul>
    <dashboard-panels
      :keyword="keyword"
      :chart-option="chartOption"
      :groups-data="groupsData"
      :variable-data="variableData"
      :compare-value="compareValue"
      :chart-type="chartType"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import AbnormalTips from '../../../components/abnormal-tips/abnormal-tips.vue';
import PerformanceModule from '../../../store/modules/performance';
import DashboardPanels from './dashboard-panels.vue';

@Component({
  name: 'view-content-process',
  components: {
    MonitorEcharts,
    DashboardPanels,
    AbnormalTips,
  },
})
export default class ViewContentProcess extends Vue {
  @Prop({ default: () => [], type: Array }) readonly groupsData: IHostGroup[];
  @Prop({ default: 1 }) readonly chartType: ChartType;
  @Prop() readonly variableData: {};
  @Prop({ required: true }) readonly compareValue: IQueryOption;
  @Prop({ default: '' }) readonly keyword: string;

  // 图表配置设置
  @Prop() readonly chartOption: object;
  private portList: { port: string; status: string }[] = [];

  private componentStatusMap: any = {
    1: {
      // 异常
      tipsText: window.i18n.t('原因:查看进程本身问题或者检查进程配置是否正常'),
      docLink: 'processMonitor',
    },
    2: {
      // 无数据
      tipsText: window.i18n.t('原因:bkmonitorbeat进程采集器未安装或者状态异常'),
      linkText: window.i18n.t('前往节点管理处理'),
      linkUrl: `${this.$store.getters.bkNodeManHost}#/plugin-manager/list`,
    },
    3: {},
  };
  get processList() {
    return PerformanceModule.curProcessList;
  }
  get process() {
    return PerformanceModule.curProcess;
  }
  @Emit('process-change')
  handleProcessChange(item) {
    PerformanceModule.setProcessId(item.displayName);
  }

  handleComponentStatusData(status: number) {
    const resStatus = this.transformStatus(status);
    return this.componentStatusMap[resStatus];
  }
  transformStatus(status: number) {
    let resStatus = 1;
    switch (status) {
      case -1:
        resStatus = 2;
        break;
      case 0:
        resStatus = 3;
        break;
      default:
        resStatus = 1;
        break;
    }
    return resStatus;
  }
  handleGetTextSeries() {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({
          value: 56.78,
          unit: this.$t('小时'),
        });
      }, 1000);
    });
  }
  async handleGetPortSeries() {
    const data = await PerformanceModule.getHostProcessPortDetail();
    return data;
  }
}
</script>
<style lang="scss" scoped>
$statusColors: #dcdee5 #10c178 #fd9c9c #ffeb00;
$statusBgColors: #f0f1f5 #85dcb8 #ea3636 #ffeb00;

.content-process {
  font-size: 12px;
  color: #63656e;

  .process-list {
    display: flex;
    flex-wrap: wrap;
    margin-bottom: 10px;

    &-item {
      display: flex;
      align-items: center;
      height: 24px;
      padding: 3px 10px 3px 6px;
      margin: 0 6px 6px 0;
      line-height: 16px;
      background-color: #fafbfd;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      @for $i from -1 through 1 {
        .item-status-#{$i} {
          width: 6px;
          height: 6px;
          margin-right: 5px;

          /* stylelint-disable-next-line function-no-unknown */
          background-color: nth($statusBgColors, $i + 2);

          /* stylelint-disable-next-line function-no-unknown */
          border: 1px solid nth($statusColors, $i + 2);
          border-radius: 6px;
        }
      }

      &:hover {
        cursor: pointer;
      }

      &.is-active {
        color: #3a84ff;
        border-color: #3a84ff;
      }
    }
  }

  .chart-list {
    display: flex;
    flex-wrap: wrap;
    margin-top: 10px;
    margin-right: -10px;

    &-item {
      display: flex;
      margin: 0 10px 10px 0;

      &.special-item {
        width: 100%;

        .chart-item {
          height: 100px;
          border-radius: 2px;
          box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.1);
        }
      }
    }
  }
}
</style>
