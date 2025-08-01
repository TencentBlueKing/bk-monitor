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
  <div class="alarm-detail">
    <!-- 趋势图 -->
    <monitor-echarts
      v-if="eventDetail.dataTypeLabel === 'time_series'"
      :style="{ backgroundColor: '#f0f1f5' }"
      class="alarm-detail-chart"
      :height="210"
      :options="options"
      :series="series"
      @click="handleGoChart"
    />
    <!-- tag -->
    <van-row
      class="alarm-detail-tag"
      gutter="3"
      justify="space-around"
      type="flex"
    >
      <van-col span="8">
        <span class="tag-label">
          <icon
            :status="eventDetail.level"
            type="level"
          />
          {{ levelNameMap[eventDetail.level] }}
        </span>
      </van-col>
      <van-col span="8">
        <span class="tag-label">
          <icon
            :status="eventDetail.noticeStatus"
            type="notice"
          />
          {{ eventDetail.noticeStatus === 'SUCCESS' ? $t('已告警') : $t('未告警') }}
        </span>
      </van-col>
      <van-col span="8">
        <span class="tag-label">
          <icon
            :status="eventDetail.status"
            type="status"
          />
          {{ statusMap[eventDetail.status] }}
        </span>
      </van-col>
    </van-row>
    <!-- 事件详情 -->
    <van-collapse
      v-model="active"
      class="alarm-detail-group"
    >
      <van-collapse-item
        v-for="(val, key) in detailFieldMap"
        :key="key"
        :border="!expand.includes(key)"
        :disabled="!expand.includes(key)"
        :is-link="expand.includes(key)"
        :name="key"
        :title="val"
      >
        <template
          v-if="!expand.includes(key)"
          #value
        >
          {{ eventDetail[key] || '--' }}
        </template>
        <template v-else>
          {{ eventDetail[key] || '--' }}
        </template>
      </van-collapse-item>
    </van-collapse>
    <!-- 快捷屏蔽 -->
    <footer-button
      v-if="!eventDetail.isShield"
      type="default"
      @click="handleToQuickShield"
    >
      <span class="default-text">{{ $t('快捷屏蔽') }}</span>
    </footer-button>
  </div>
</template>
<script lang="ts">
// eslint-disable
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { Cell, CellGroup, Col, Collapse, CollapseItem, Row } from 'vant';

import MonitorEcharts from '../../../monitor-ui/monitor-echarts/monitor-mobile-echarts.vue';
import FooterButton from '../../components/footer-button/footer-button.vue';
import AlarmModule from '../../store/modules/alarm-info';
import EventModule from '../../store/modules/event-detail';
import Icon from './icon.vue';

type AlarmStatus = 'ABNORMAL' | 'CLOSED' | 'RECOVERED';

interface IEventDetail {
  anomalyMessage: string;
  createTime: string;
  currentValue: number | string;
  dataTypeLabel?: string;
  dimensionMessage: string;
  duration: string;
  firstAnomalyTime: string;
  id: number | string;
  isShield?: boolean;
  latestAnomalyTime: string;
  level?: Level;
  noticeStatus?: number | string;
  status?: AlarmStatus;
  strategyName: string;
}

type Level = 1 | 2 | 3;

type LevelMap = {
  [k in Level]: string;
};

type StatusMap = {
  [k in AlarmStatus]: string;
};

@Component({
  name: 'alarm-detail',
  components: {
    FooterButton,
    [CellGroup.name]: CellGroup,
    [Cell.name]: Cell,
    [Collapse.name]: Collapse,
    [CollapseItem.name]: CollapseItem,
    [Row.name]: Row,
    [Col.name]: Col,
    Icon,
    MonitorEcharts,
  },
})
export default class AlarmDetail extends Vue {
  // 事件ID
  @Prop({ default: 0 }) readonly id!: number | string;
  @Prop() readonly routeKey: string;

  // 事件详情数据
  private eventDetail: IEventDetail = {
    strategyName: '',
    firstAnomalyTime: '',
    latestAnomalyTime: '',
    createTime: '',
    duration: '',
    anomalyMessage: '',
    currentValue: '',
    id: '',
    dimensionMessage: '',
    level: 1,
    status: 'ABNORMAL',
    noticeStatus: '',
    isShield: false,
    dataTypeLabel: 'time_series',
  };

  // 事件详情展示字段Map
  private detailFieldMap: IEventDetail = null;
  // 图表series
  private series: any[] = null;
  // 折叠面板当前激活项
  private active: Array<number | string> = ['anomalyMessage', 'dimensionMessage'];
  // 可以折叠的字段
  private expand: Array<number | string> = ['anomalyMessage', 'dimensionMessage'];
  // 事件级别Map
  private levelNameMap: LevelMap = null;
  // 事件状态Map
  private statusMap: StatusMap = null;
  // 图表默认options
  private options = {
    legend: {
      show: false,
    },
    tooltip: {
      show: false,
    },
    toolbox: {
      show: false,
    },
  };

  @Watch('id')
  handleOnIdChanged() {
    this.handleGetData();
  }

  @Watch('routeKey')
  onRouteKeyChange() {
    this.handleGetData();
  }

  created() {
    this.detailFieldMap = {
      strategyName: this.$tc('策略名称'),
      firstAnomalyTime: this.$tc('首次异常时间'),
      latestAnomalyTime: this.$tc('最近异常时间'),
      createTime: this.$tc('产生时间'),
      duration: this.$tc('持续时长'),
      anomalyMessage: this.$tc('检测算法'),
      dimensionMessage: this.$tc('维度信息'),
      currentValue: this.$tc('当前值'),
      id: this.$tc('事件ID'),
    };
    this.levelNameMap = {
      1: this.$tc('致命'),
      2: this.$tc('预警'),
      3: this.$tc('提醒'),
    };
    this.statusMap = {
      ABNORMAL: this.$tc('未恢复'),
      CLOSED: this.$tc('已失效'),
      RECOVERED: this.$tc('已恢复'),
    };
    this.handleGetData();
  }

  // 获取事件详情和图表数据
  handleGetData() {
    this.$store.commit('app/setPageLoading', true);
    Promise.all([this.handleGetEventDetail(), this.handleGetSeriesData(), AlarmModule.getEventNum()]).finally(() => {
      this.$store.commit('app/setPageLoading', false);
    });
  }

  async handleGetEventDetail() {
    const {
      strategyName,
      firstAnomalyTime,
      latestAnomalyTime,
      createTime,
      duration,
      anomalyMessage,
      currentValue,
      id,
      level,
      status,
      noticeStatus,
      isShield,
      dataTypeLabel,
      dimensionMessage,
    } = await EventModule.getEventDetail({ id: this.id });

    this.eventDetail = {
      strategyName,
      firstAnomalyTime,
      latestAnomalyTime,
      createTime,
      duration,
      anomalyMessage,
      currentValue,
      id,
      level,
      status,
      noticeStatus,
      isShield,
      dataTypeLabel,
      dimensionMessage,
    };
  }

  async handleGetSeriesData() {
    const data = await EventModule.getChartData({
      event_id: this.id,
      start_time: dayjs().add(-1, 'h').unix(),
      end_time: dayjs().unix(),
    }).catch(() => []);
    let chartData = [];
    const chartSeries = data?.find(item => item?.metric?.metric_field === 'value');
    if (chartSeries) {
      const coverList = [];
      const upBoundary =
        data
          ?.find(item => item.metric.metric_field.includes('upper_bound'))
          ?.datapoints?.map(item => [item[1], item[0]]) || [];
      const lowBoundary =
        data
          ?.find(item => item.metric.metric_field.includes('lower_bound'))
          ?.datapoints?.map(item => [item[1], item[0]]) || [];
      const coverData = data.find(item => item.metric.metric_field.includes('is_anomaly'))?.datapoints || [];
      if (coverData.length) {
        coverList.push({
          data: coverData.map((item, index) => [
            chartSeries?.datapoints[index][1],
            item[0] > 0 ? chartSeries?.datapoints[index][0] : null,
          ]),
          color: '#ea3636',
          z: 11,
          name: '1-cover',
        });
      }
      chartData = data
        .filter(item => item?.metric?.metric_field === 'value')
        .map(({ target, datapoints, ...setData }) => ({
          datapoints,
          ...setData,
          target,
          boundary: [
            {
              upBoundary,
              lowBoundary,
              color: '#ccc',
              stack: `1-boundary-${target}`,
              z: 5,
            },
          ],
          coverSeries: coverList.map(set => ({ ...set, name: `${set.name}-${target}` })),
        }));
    } else if (data?.length) {
      chartData = data.filter(item => item?.metric?.metric_field === 'value');
      if (!chartData.length) {
        chartData = data;
      }
    }

    this.series = chartData.map(({ markTimeRange, markPoints, ...item }) => item);
  }

  //  跳转快捷屏蔽
  handleToQuickShield() {
    this.$store.commit('app/SET_EVENT_ID', this.eventDetail.id);
    this.$router.push({
      name: 'quick-alarm-shield',
      params: {
        eventId: this.id as string,
      },
    });
  }

  // 跳转趋势图
  handleGoChart() {
    this.$router.push({
      name: 'tendency-chart',
      params: {
        id: this.id as string,
      },
    });
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate';

.alarm-detail {
  min-height: 100vh;
  font-size: 14px;
  color: $defaultFontColor;
  background: #f4f7fa;

  &-chart {
    padding-top: 1.5rem;
  }

  &-tag {
    padding: 15px 16px 12px;
    background-color: #fff;

    .tag-label {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 32px;
      color: #63656e;
      background-color: rgb(240 241 245 / 60%);
      border-radius: 2px;
    }
  }

  :deep(.alarm-detail-group) {
    .van-cell__title {
      color: #313238;
    }

    .van-cell__value,
    .van-collapse-item__content {
      color: #63656e;
    }
  }

  &-group {
    margin-bottom: 70px;
  }

  .default-text {
    color: #ff9c01;
  }
}
</style>
