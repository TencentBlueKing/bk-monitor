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
  <div class="tendency-chart">
    <!-- 按钮组 -->
    <div class="select-btn-group">
      <div class="select-btn">
        <select-button
          v-for="(item, index) in selectGroup.list"
          :key="index"
          class="select-btn-item"
          :active="item.value === selectGroup.active"
          :class="orientation"
          :text="item.text"
          @click="changeTime(item.value)"
        />
      </div>
      <select-button
        v-if="isLandscape"
        class="compare-btn"
        :text="$t('数据对比')"
        @click="handleCompareClick"
      />
    </div>
    <!-- 趋势图 -->
    <monitor-echarts
      v-if="series.length"
      :key="chartKey"
      :style="{ backgroundColor: '#f0f1f5' }"
      :colors="['#7EB26D', '#EAB839']"
      :height="isLandscape ? 311 : 247"
      :series="series"
      :show-legend="true"
      :unit="unit"
    />
    <div
      v-else
      class="no-data"
    >
      {{ loading ? $t('加载中...') : $t('查无数据') }}
    </div>
    <!-- 时间选择器 -->
    <datetime-picker
      :max-date="maxDate"
      :min-date="minDate"
      :show.sync="showDP"
      :title="pickerTitle"
      @confirm="getDatetime"
    />
    <!-- 数据对比 -->
    <van-popup
      v-if="isLandscape"
      v-model="showPopup"
      :style="popupStyle"
      :overlay="false"
      position="right"
    >
      <span
        class="popup-icon"
        @click="handleHidePopup"
      >
        <i class="icon-monitor icon-arrow-right" />
      </span>
      <data-compare
        :colors="['#7EB26D', '#EAB839']"
        :data="compareData"
        @change="handleCompareChange"
      />
    </van-popup>
    <data-compare
      v-else
      :colors="['#7EB26D', '#EAB839']"
      :data="compareData"
      @change="handleCompareChange"
    />
    <!-- 横屏和竖屏 -->
    <screen-orientation
      v-show="showOrienBtn"
      v-model="orientation"
    />
  </div>
</template>
<script lang="ts">
import { Component, Mixins, Prop, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { Popup } from 'vant';

import MonitorEcharts from '../../../monitor-ui/monitor-echarts/monitor-mobile-echarts.vue';
import DatetimePicker, { type ITimeObj } from '../../components/datetime-picker/datetime-picker.vue';
import ScreenOrientation, { Screen } from '../../components/screen-orientation/screen-orientation.vue';
import SelectButton from '../../components/select-button/select-button.vue';
import HideChartTooltipMixin from '../../mixins/hideChartTooltipMixin';
import EventModule from '../../store/modules/event-detail';
import DataCompare from './data-compare.vue';

import type { ICompare, ICompareData, ISelectGroup, ISeriesData } from '../../types/tendency-chart';
import type { Route } from 'vue-router';

Component.registerHooks(['beforeRouteLeave']);

@Component({
  name: 'tendency-chart',
  components: {
    MonitorEcharts,
    SelectButton,
    DatetimePicker,
    ScreenOrientation,
    DataCompare,
    [Popup.name]: Popup,
  },
})
export default class TendencyChart extends Mixins(HideChartTooltipMixin) {
  // 事件ID
  @Prop({ default: -1 }) readonly id!: number | string;
  @Prop() readonly routeKey: string;
  orientation = Math.abs(window.orientation as number) === 90 ? Screen.LANDSCAPE : Screen.PORTRAIT;
  // 图表数据
  series: ISeriesData[] = [];
  unit = '';

  // 选择按钮配置
  selectGroup: ISelectGroup = {
    list: [],
    active: 1,
  };

  // 时间范围
  minDate: Date = new Date(new Date().getTime() - 7 * 24 * 60 * 60 * 1000);
  maxDate: Date = new Date();
  customDate: Date = null;
  // datetime-picker 显示状态
  showDP = false;
  // 数据对比弹窗（横屏有效）
  showPopup = false;
  // 对比时间（24h：一天前）
  timeCompare = 24;
  typeCompare = 1;
  // 表格对比数据
  compareData: ICompareData[] = [];
  // 时间组件标题
  pickerTitle: string;
  // 手动切换横屏按钮
  showOrienBtn = false;

  get loading() {
    return this.$store.state.app.loading;
  }
  @Watch('id')
  handleIdChange() {
    this.handleGetChartData();
  }

  @Watch('selectGroup.active')
  handleActiveChange(v) {
    if (v !== 0) {
      const item = this.selectGroup.list.find(item => item.value === 0);
      item.text = this.$t('自定义');
      this.handleGetChartData();
    }
  }

  @Watch('routeKey')
  onRouteKeyChange() {
    this.handleGetChartData();
  }

  // 图表key
  get chartKey() {
    return this.orientation + this.selectGroup.active;
  }

  // 数据对比表格弹窗样式（横屏有效）
  get popupStyle() {
    return {
      width: '50%',
      height: '100%',
      overflow: 'visible',
      boxShadow: '0px 3px 6px 0px rgba(79,85,96,0.3)',
    };
  }

  // 是否为横屏
  get isLandscape() {
    return this.orientation === 'landscape';
  }

  created() {
    this.selectGroup.list = [
      {
        text: this.$t('小时', { num: 1 }),
        value: 1,
      },
      {
        text: this.$t('小时', { num: 2 }),
        value: 2,
      },
      {
        text: this.$t('小时', { num: 24 }),
        value: 24,
      },
      {
        text: this.$t('自定义'),
        value: 0,
      },
    ];
    this.pickerTitle = this.$tc('选择开始时间');
    this.handleGetChartData();
  }

  // 路由离开时清空旋转状态，防止对其他界面造成影响
  beforeRouteLeave(to: Route, from: Route, next: () => void) {
    const htmlEle = this.$root.$el as HTMLElement;
    htmlEle.className = '';
    htmlEle.style.transform = 'unset';
    next();
  }

  // 时间按钮组change事件
  changeTime(value: number) {
    if (value !== 0) {
      this.selectGroup.active = value;
    } else {
      this.showDP = true;
    }
  }

  // 获取自定义时间
  getDatetime(timeObj: ITimeObj) {
    const obj = this.selectGroup.list.find(item => item.value === 0);
    if (obj.text === timeObj.datetime) return;
    this.customDate = timeObj.dateObj;
    obj.text = dayjs.tz(this.customDate).format('MM/DD HH:mm');
    this.selectGroup.active = 0;
    this.handleGetChartData();
  }

  // 显示数据对比表格（横屏有效）
  handleCompareClick() {
    this.showPopup = true;
  }

  handleHidePopup() {
    this.showPopup = false;
  }

  // 获取趋势图数据
  async handleGetChartData() {
    this.series = [];
    this.$store.commit('app/setPageLoading', true);
    const startTime =
      this.selectGroup.active === 0 ? dayjs(this.customDate).unix() : dayjs().add(-this.selectGroup.active, 'h').unix();
    const params: any = {
      event_id: this.id,
      start_time: startTime,
      end_time: dayjs().unix(),
    };
    if (this.typeCompare > 0) {
      params.time_compare = this.timeCompare;
    }
    const data = await EventModule.getChartData(params);
    let chartData = [];
    const chartSeries = data?.find(item => item?.metric?.metric_field === 'value' && item.time_offset === 'current');
    if (chartSeries) {
      // 智能异常检测算法 边界画图设置
      const { dimensions } = chartSeries;
      const coverList = [];
      const upBoundary =
        data
          .find(
            item =>
              item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
              item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
              item.metric.metric_field.includes('upper_bound')
          )
          ?.datapoints?.map(item => [item[1], item[0]]) || [];
      const lowBoundary =
        data
          .find(
            item =>
              item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
              item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
              item.metric.metric_field.includes('lower_bound')
          )
          ?.datapoints?.map(item => [item[1], item[0]]) || [];
      const coverData =
        data.find(
          item =>
            item?.dimensions?.bk_target_ip === dimensions.bk_target_ip &&
            item?.dimensions?.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
            item?.metric?.metric_field?.includes('is_anomaly')
        )?.datapoints || [];
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
        .map(({ target, datapoints, ...setData }) => {
          const item = {
            datapoints,
            ...setData,
            target,
          };
          if (setData.time_offset === 'current') {
            return {
              ...item,
              boundary: [
                {
                  upBoundary,
                  lowBoundary,
                  color: '#ccc',
                  stack: `1-boundary-${item.target}`,
                  z: 5,
                },
              ],
              coverSeries: coverList.map(set => ({ ...set, name: `${set.name}-${item.target}` })),
            };
          }
          return item;
        });
    } else if (data?.length) {
      chartData = data.filter(item => item?.metric?.metric_field === 'value');
      if (!chartData.length) {
        chartData = data;
      }
    }

    this.series = chartData.map(({ markTimeRange, markPoints, ...item }) => {
      item.target = this.getSemanticsTime(item.target);
      return item;
    });
    this.unit = data?.unit || '';
    this.handleSetCompareData(this.series);
    setTimeout(() => {
      this.$store.commit('app/setPageLoading', false);
    }, 100);
  }
  // 获取当前对比数据
  handleSetCompareData(series = []) {
    this.compareData = series.map(item => ({
      ...item.statistics,
      name: item.name || item.target.split('-')[0],
    }));
  }

  // 对比条件change事件
  handleCompareChange(data: ICompare) {
    if (data.type === 'compareType') {
      this.typeCompare = data.value;
    } else {
      this.timeCompare = data.value;
    }
    this.handleGetChartData();
  }

  getSemanticsTime(semantics: string) {
    if (!semantics?.endsWith('d')) {
      return semantics;
    }
    const dayNum = Number(semantics.substring(0, semantics.length - 1));
    if (dayNum < 7) {
      return this.$t('天前', { num: dayNum });
    }
    if (dayNum < 30) {
      return this.$t('周前', { num: Math.floor(dayNum / 7) });
    }
    return this.$t('月前', { num: Math.floor(dayNum / 30) });
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate';

.tendency-chart {
  box-sizing: border-box;
  max-height: 100vh;
  padding: 1rem 0 0;
  background-color: #f0f1f5;

  .select-btn-group {
    display: flex;
    justify-content: space-between;
    padding: 0 1.5rem 1rem;

    .select-btn {
      display: flex;
      flex: 1;
      color: $defaultFontColor;

      :deep(.text) {
        font-size: 0.8rem;
      }

      .select-btn-item {
        flex: 0 4rem;
        height: 2rem;
        margin-right: 10px;

        &.portrait {
          &:last-child {
            flex: 1;
            margin-right: 0;
          }
        }

        &.landscape {
          &:last-child {
            flex: 0 9rem;
          }
        }
      }
    }

    .compare-btn {
      flex: 0 5rem;
      height: 2rem;

      :deep(.text) {
        font-size: 0.8rem;
      }
    }
  }

  .popup-icon {
    position: absolute;
    top: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.2rem;
    height: 3rem;
    background: #fff;
    border-radius: 4px 0 0 4px;
    box-shadow: -1px 1px 2px 0 rgb(79 85 96 / 30%);
    transform: translate(-1.2rem, -50%);

    i {
      font-size: 1.5rem;
      color: #979ba5;
    }
  }

  .no-data {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 247px;
    font-weight: bold;
    color: #63656e;
  }
}
</style>
