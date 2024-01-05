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
  <monitor-dialog
    class="view-detail-modal"
    :value.sync="showModal"
    :append-to-body="true"
    :full-screen="true"
    :need-footer="false"
    need-header
    :header-theme="'header-bar'"
    :title="$t('查看大图')"
    :before-close="handleBackStep"
  >
    <div class="view-detail">
      <div
        :class="['view-box', { 'reduce-box': navToggle }]"
        v-bkloading="{ isLoading: loading }"
      >
        <!-- 头部选项栏 -->
        <header class="view-box-header">
          <div :class="['view-box-header-left', { 'show-right': isRightBoxShow }]">
            <compare-panel
              class="compare-panel"
              :need-split="false"
              :has-view-change-icon="false"
              :compare-list="compareList"
              :compare-hide="compareList.length < 2"
              :value="compareValue"
              :reflesh-list="refleshList"
              :timeshift-list="timeshiftList"
              :timerange-list="timerangeList"
              @change="handleComparePanelChange"
              @add-timeshift-option="handleAddTimeshifOption"
              @on-immediate-reflesh="handleImmediateReflesh"
            />
          </div>
          <div
            class="right-title"
            :class="{ 'right-title-active': !isRightBoxShow }"
          >
            <i
              class="icon-monitor icon-double-up"
              :class="{ 'icon-active': !isRightBoxShow }"
              @click="handleHideRightBox"
            />
            <span v-show="isRightBoxShow">{{ $t('设置') }}</span>
          </div>
        </header>
        <!-- content -->
        <section class="view-box-content">
          <!-- 左边部分 视图展示部分 -->
          <div
            class="box-left"
            :class="{ 'box-left-active': !isRightBoxShow }"
          >
            <!-- 图表组件 -->
            <div
              class="section-chart"
              data-tag="resizeTarget"
              :style="{ height: drag.height + 'px' }"
            >
              <monitor-echarts
                v-if="queryConfigKey"
                :chart-type="['graph', 'aiops-dimension-lint', 'performance-chart'].includes(type) ? 'line' : type"
                :key="renderKey + '_' + queryConfigKey"
                :height="drag.height - 20"
                :reflesh-interval="compareValue.tools.refleshInterval"
                :title="title"
                :subtitle="subtitle"
                :options="chartOptions"
                :need-full-screen="false"
                :get-alarm-status="getAlarmStatus"
                :get-series-data="getSeriesData(queryconfig)"
                @add-strategy="handleAddStrategy(queryconfig)"
              />
              <div
                class="chart-drag"
                @mousedown="handleMouseDown"
                @mousemove="handleMouseMove"
              />
            </div>
            <!-- 原始数据 -->
            <div class="section-box">
              <div class="section-box-title">
                <span>{{ $t('原始数据') }}</span>
                <span class="title-count">{{ $t('共 {num} 条', { num: dataListLength }) }}</span>
                <bk-button
                  class="export-csv-btn"
                  size="small"
                  @click="handleExportCsv"
                >{{ $t('导出CSV') }}</bk-button>
              </div>
              <div class="section-box-content">
                <table
                  cellspacing="0"
                  cellpadding="0"
                  border="0"
                  style="width: 100%"
                >
                  <thead>
                    <tr class="table-head">
                      <th
                        class="table-content"
                        v-for="(item, index) in tableThArr"
                        :key="index"
                      >
                        <div
                          class="table-item sort-handle"
                          :style="index === 0 ? 'text-align: left' : ''"
                          @click="() => handleTableSortAuto(item, index)"
                        >
                          <span class="table-header">
                            {{ item.name }}
                            <sort-button
                              class="sort-btn"
                              v-model="item.sort"
                              @change="() => handleTableSort(item.sort, index)"
                            />
                          </span>
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, index) in tableData"
                      :key="index"
                    >
                      <td
                        class="table-content"
                        v-for="(item, tdIndex) in row"
                        :key="tdIndex"
                      >
                        <div
                          class="table-item"
                          :style="tdIndex === 0 ? 'text-align: left' : ''"
                        >
                          {{ item?.value === null ? '--' : item.value }}
                          <img
                            alt=''
                            v-if="tdIndex > 0 && (item?.max || item?.min)"
                            class="item-max-min"
                            :src="require(`../../static/images/svg/${item?.min ? 'min.svg' : 'max.svg'}`)"
                          >
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div
            class="box-right"
            v-show="isRightBoxShow"
          >
            <!-- 右边部分 设置部分 -->
            <query-criteria-item
              v-for="(item, index) in rightData"
              :key="index"
              :query-config="item"
              :group-index="index"
              :compare-value="compareValue"
              @change-status="handleChangeStatus"
              @query-change="handleQueryChange"
              @checked-change="handleCheckedChange"
              @change-loading="handleChangeLoading"
            />
          </div>
        </section>
      </div>
    </div>
  </monitor-dialog>
</template>
<script lang="ts">
/* eslint-disable @typescript-eslint/member-ordering */
import { Component, InjectReactive, Mixins, Prop, Provide, ProvideReactive, Vue } from 'vue-property-decorator';
import dayjs from 'dayjs';

import { graphUnifyQuery } from '../../../monitor-api/modules/grafana';
import { fetchItemStatus } from '../../../monitor-api/modules/strategies';
import { deepClone, random } from '../../../monitor-common/utils/utils';
import ComparePanel from '../../../monitor-pc/pages/performance/performance-detail/compare-panel.vue';
import MonitorDialog from '../../../monitor-ui/monitor-dialog/monitor-dialog.vue';
import MonitorEcharts from '../../../monitor-ui/monitor-echarts/monitor-echarts-new.vue';
import { DEFAULT_REFLESH_LIST, DEFAULT_TIME_RANGE_LIST, DEFAULT_TIMESHIFT_LIST } from '../../common/constant';
import SortButton from '../../components/sort-button/sort-button';
import type { TimeRangeType } from '../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../components/time-range/utils';
// import { handleTimeRange } from '../../utils/index';
import authorityMixinCreate from '../../mixins/authorityMixin';
import { NEW_DASHBOARD_AUTH as GRAFANA_MANAGE_AUTH } from '../grafana/authority-map';

import QueryCriteriaItem from './query-criteria-item.vue';
import { downCsvFile, transformSrcData, transformTableDataToCsvStr } from './utils';

const authorityMap = { GRAFANA_MANAGE_AUTH };
@Component({
  name: 'view-detail',
  components: {
    MonitorDialog,
    MonitorEcharts,
    ComparePanel,
    QueryCriteriaItem,
    SortButton
  }
})
export default class MigrateDashboard extends Mixins(authorityMixinCreate(authorityMap)) {
  @Prop({ required: true, type: Boolean, default: false }) showModal: boolean;
  @Prop({ required: true, type: Object, default: () => {} }) viewConfig: any;
  @InjectReactive('readonly') readonly: boolean;
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.compareValue.tools.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.compareValue.tools.timeRange));
      this.compareValue.tools.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.compareValue.tools.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }
  loading = true;
  drag = { height: 550, minHeight: 300, maxHeight: 550 };
  title = ''; // 图表名称
  subtitle = ''; // 图表名称
  type = ''; //  图表类型
  chartOptions = {
    legend: { asTable: true, maxHeight: 156 },
    tool: { list: ['screenshot', 'set', 'strategy', 'area'] },
    annotation: { show: true }
  }; //  图表类型
  refleshKey = 'refleshKey'; // 图表刷新控制
  isRightBoxShow = true; // 是否收起右侧指标栏
  rightData = []; // 右侧指标数据
  queryconfig: any = []; // 图表查询参数
  tableThArr = []; // 原始数据表头数据
  tableTdArr = []; // 原始数据表格数据
  tableData = []; // 原始数据表格渲染数据
  timeshiftList = []; // 时间对比候选值列表
  timerangeList = []; // 图表刷新列表
  compareValue = {
    // 图表顶部工具栏
    compare: {
      type: 'none', // 对比类型 目前只支持 时间对比
      value: '' // 对应对比类型的值
    },
    tools: {
      refleshInterval: -1, // 刷新间隔 -1是不刷新
      timeRange: ['now-1m', 'now'] // 图表横轴时间范围
    }
  };
  compareList: any = [
    // 对比类型列表
    {
      id: 'none',
      name: window.i18n.t('不对比')
    },
    {
      id: 'time',
      name: window.i18n.t('时间对比')
    },
    {
      id: 'metric',
      name: window.i18n.t('指标对比')
    }
  ];
  refleshList: { name: any; id: number }[] = DEFAULT_REFLESH_LIST;

  tableTdMaxMinMap = [];
  queryConfigKey = random(10);
  queryConfigUnwatch = null;
  cacheTimeRange = [];

  //  原始数据数目
  get dataListLength() {
    return this.tableTdArr.length;
  }

  //  渲染Key 查询参数 + 图表横轴时间范围 + 时间对比值
  get renderKey() {
    return (
      // JSON.stringify(this.queryconfig)
      JSON.stringify(this.compareValue.tools.timeRange)
      + JSON.stringify(this.compareValue.compare.value)
      + this.refleshKey
    );
  }

  // 是否展开导航
  get navToggle() {
    return this.$store.getters.navToggle;
  }

  created() {
    this.timerangeList =  DEFAULT_TIME_RANGE_LIST;
    this.timeshiftList = DEFAULT_TIMESHIFT_LIST;
    this.compareList = [
    // 对比类型列表
      {
        id: 'none',
        name: window.i18n.t('不对比')
      },
      !window.__BK_WEWEB_DATA__?.lockTimeRange ? {
        id: 'time',
        name: window.i18n.t('时间对比')
      } : undefined,
      !this.readonly ? {
        id: 'metric',
        name: window.i18n.t('指标对比')
      } : undefined
    ].filter(Boolean);
    this.handleQueryConfig(this.viewConfig);
  }

  mounted() {
    const { clientHeight } = document.body;
    this.drag.height = clientHeight - 173;
    document.addEventListener('keyup', this.handleEsc);
  }
  beforeDestroy() {
    this.queryConfigUnwatch?.();
    document.removeEventListener('keyup', this.handleEsc);
  }

  beforeRouteEnter(to, from, next) {
    next((vm) => {
      if (from.name === 'performance-detail') {
        vm.chartOptions.annotation = {
          show: true,
          list: ['strategy']
        };
      }
    });
  }

  handleEsc(evt: KeyboardEvent) {
    if (evt.code === 'Escape') this.$emit('close-modal');
  }
  //  处理入参
  handleQueryConfig(data) {
    const { targets, title, type, subTitle = '' } = data.config;
    this.title = title;
    this.subtitle = subTitle;
    this.type = type;
    this.queryconfig = deepClone(targets);
    const str = 'ABCDEFGHIJKLNMOPQRSTUVWXYZ';
    this.rightData = this.queryconfig.map((item, index) => ({
      ...item,
      show: index === 0,
      name: str[index]
    }));
    const { compare, tools } = data.compareValue;
    if (compare.type === 'time') {
      if (typeof compare.value === 'string' && !this.timeshiftList.find(item => item.id === compare.value)) {
        this.timeshiftList.push({
          id: compare.value,
          name: compare.value
        });
      } else if (Array.isArray(compare.value)) {
        const itemList = compare.value.filter(id => !this.timeshiftList.some(item => item.id === id));
        if (itemList.length) {
          itemList.forEach((id) => {
            this.timeshiftList.push({
              name: id,
              id
            });
          });
        }
        this.queryconfig.forEach((item) => {
          item.data.function = { time_compare: compare.value };
        });
      }
    }
    this.compareValue.compare = {
      type: ['time', 'metric'].includes(compare.type) ? compare.type : 'none',
      value: compare.type === 'time' ? compare.value : 'false'
    };
    // if (Array.isArray(tools.timeRange)) {
    //   const valStr = `${tools.timeRange[0]} -- ${tools.timeRange[1]}`;
    //   const item = this.timerangeList.find(item => item.name === valStr);
    //   if (!item) {
    //     this.timerangeList.push({
    //       name: valStr,
    //       value: valStr
    //     });
    //   }
    // }
    this.compareValue.tools.timeRange = tools.timeRange;
    this.compareValue.tools.refleshInterval = tools.refleshInterval;
  }

  //  获取图表时间范围
  getTimerange() {
    const { tools } = this.compareValue;
    // const res = handleTimeRange(tools.timeRange);
    const [startTime, endTime] = handleTransformToTimestamp(tools.timeRange as TimeRangeType);
    return {
      start_time: startTime,
      end_time: endTime
    };
  }
  // 获取告警状态信息
  async getAlarmStatus(id) {
    const data = await fetchItemStatus({ metric_ids: [id] }).catch(() => ({ [id]: 0 }));
    return data?.[id];
  }
  //  图表数据请求方法
  getSeriesData(targets) {
    return async (startTime?, endTime?) => {
      // this.loading = true;
      const dataList = await Promise.all((targets || []).map(async (item) => {
        const { query_configs: queryConfig, ...otherParams } = item.data;
        const params = {
          query_configs: queryConfig,
          ...otherParams
        };
        let timerange = this.getTimerange();
        if (startTime && endTime) {
          timerange = {
            start_time: dayjs.tz(startTime).unix(),
            end_time: dayjs.tz(endTime).unix()
          };
        }
        return await graphUnifyQuery({
          ...params,
          ...timerange
        })
          .then(data => (data.series || []).map((set) => {
            const { datapoints, dimensions, target, ...setData } = set;
            const metric = data.metrics[0];
            // const { filter_dict: filterDict } = params
            // const aliasArr = [metric.metric_field]
            // Object.keys(dimensions || {}).forEach(key => aliasArr.push(dimensions[key]))
            // Object.keys(filterDict || {}).forEach(key => aliasArr.push(filterDict[key]))
            // const alias = aliasArr.join('-')
            return {
              metric,
              dimensions,
              datapoints,
              ...setData,
              target
              // taregt: this.handleBuildLegend()
            };
          }))
          .catch((err) => {
            console.log(err);
            return [];
          })
          .finally(() => (this.loading = false));
      }));
      const res = dataList.reduce<any[]>((data, item) => data.concat(item), []);
      this.handleRawData(res);
      return res;
    };
  }
  //  处理原始数据
  handleRawData(data) {
    if (data.length === 0) {
      this.loading = false;
      return;
    }
    const { tableThArr, tableTdArr } = transformSrcData(data);
    this.tableThArr = tableThArr.map(item => ({
      name: item,
      sort: ''
    }));
    this.tableTdArr = tableTdArr;
    this.tableData = [...tableTdArr];
    this.loading = false;
  }

  //  图表顶部工具栏数据变更触发
  handleComparePanelChange(params) {
    (this.queryconfig || []).forEach((item) => {
      if (params.compare.type === 'time') {
        if (!item.alias?.includes('$time_offset')) {
          item.alias = item.alias ? `$time_offset-${item.alias}` : '$time_offset';
        }
      } else {
        item.alias = item.alias?.replace?.('$time_offset-', '').replace('$time_offset', '');
      }
    });
    this.compareValue = params;
    //  自定义时间范围
    const curTools = params.tools;
    if (Array.isArray(curTools.timeRange)) {
      const valStr = `${curTools.timeRange[0]} -- ${curTools.timeRange[1]}`;
      const item = this.timerangeList.find(item => item.name === valStr);
      if (!item) {
        this.timerangeList.push({
          name: valStr,
          value: valStr
        });
      }
    }

    //  时间对比处理 不对比 value 是 false || ''
    const { value } = params.compare;
    if (!value) {
      this.queryconfig.forEach((item) => {
        Vue.delete(item.data, 'function');
      });
      return;
    }
    // const unit = value.replace(/[^a-z]+/ig, '')
    // const number = value.replace(/[^0-9]/ig, '')
    // if (['d', 'day', 'days', '天'].includes(unit)) {
    //   value = `${number}d`
    // }
    this.queryconfig.forEach((item) => {
      item.data.function = { time_compare: value };
    });
  }

  handleAddTimeshifOption(v: string) {
    v.trim().length
      && !this.timeshiftList.some(item => item.id === v)
      && this.timeshiftList.push({
        id: v,
        name: v
      });
  }

  //  处理method和interval变化派发出来的事件 变更图表查询参数
  handleQueryChange(value, type, groupIndex) {
    if (type === 'method') {
      this.queryconfig[groupIndex].data.query_configs[0].metrics[0].method = value;
    }
    if (type === 'interval') {
      this.queryconfig[groupIndex].data.query_configs[0].interval = value;
    }
    if (type === 'step') {
      this.queryconfig[groupIndex].data.query_configs[0].agg_interval = value;
    }
    if (type === 'promql') {
      this.queryconfig[groupIndex].data.query_configs[0].promql = value;
    }
    this.queryConfigKey = random(10);
  }

  /**
   * @description: 修改条件
   * @param {*} groupIndex 指标索引
   * @param {*} obj 条件
   * @param {*} metricDataList 指标信息
   */
  handleCheckedChange(groupIndex: number, obj, metricDataList: any[]) {
    const key = Object.keys(obj)[0];
    const val = obj[key];
    this.queryconfig[groupIndex].data.query_configs.forEach((item) => {
      !item.filter_dict && this.$set(item, 'filter_dict', {});
      if (val !== 'all') {
        const metricData = metricDataList.find(metric => (
          metric.data_source_label === item.data_source_label
          && metric.data_type_label === item.data_type_label
          && metric.result_table_id === item.table
          && metric.metric_field === item.metrics[0].field
        ));
        const groupByList = metricData?.dimensions?.map(item => item.id);
        if (groupByList?.includes(key)) {
          this.$set(item.filter_dict, key, val);
          item.filter_dict[key] = val;
        }
      } else {
        if (Object.prototype.hasOwnProperty.call(item.filter_dict, key)) {
          this.$delete(item.filter_dict, key);
        }
      }
    });
    this.queryConfigKey = random(10);
  }

  // 跳转新增策略
  async handleAddStrategy(item) {
    if (item.length === 1) {
      await this.$nextTick();
      const [{ data }] = item;
      if (data?.where?.length) {
        data.where.forEach((where, index) => {
          if (index > 0 && where && !where.condition) {
            where.condition = 'and';
          }
        });
      }
      window.open(`${location.href.replace(location.hash, '#/strategy-config/add')}?data=${JSON.stringify(data)}`);
    }
  }

  handleChangeLoading(status: boolean) {
    this.loading = status;
  }

  //  图表大小拖拽
  handleMouseDown(e) {
    let { target } = e;

    while (target && target.dataset.tag !== 'resizeTarget') {
      target = target.parentNode;
    }
    const rect = target.getBoundingClientRect();
    document.onselectstart = function () {
      return false;
    };
    document.ondragstart = function () {
      return false;
    };
    const handleMouseMove = (event) => {
      this.drag.height = Math.max(this.drag.minHeight, event.clientY - rect.top);
    };
    const handleMouseUp = () => {
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  handleMouseMove(e) {
    let { target } = e;
    while (target && target.dataset.tag !== 'resizeTarget') {
      target = target.parentNode;
    }
  }

  //  面板折叠事件
  handleChangeStatus(name) {
    const data = this.rightData.find(item => item.name === name);
    data && (data.show = !data.show);
  }

  //  右侧面板 隐藏/展开 事件
  handleHideRightBox() {
    this.isRightBoxShow = !this.isRightBoxShow;
  }

  handleBackStep() {
    this.$emit('close-modal');
  }

  dataMax(index, item) {
    return this.tableTdMaxMinMap[index].max === item;
  }

  dataMin(index, item) {
    return this.tableTdMaxMinMap[index].min === item;
  }

  handleImmediateReflesh() {
    this.refleshKey = String(+new Date());
  }
  /**
   * 导出csv文件
   */
  handleExportCsv() {
    const csvList = this.tableTdArr.map(item => item.map(i => i.value).join(','))
    csvList.unshift(this.tableThArr.map(item => item.name.replace(/,/gmi, '_')).join(','));
    downCsvFile(csvList.join('\n'), this.viewConfig?.config?.title);
  }
  /**
   * 表格排序
   * sort asc 升序 desc 降序
   */
  handleTableSort(sort, index) {
    this.tableThArr.forEach((item, i) => {
      i !== index && (item.sort = '');
    });
    if (!sort) {
      this.tableData = [...this.tableTdArr];
    } else {
      this.tableData = [...this.tableTdArr].sort((a, b) => {
        const left = a[index].originValue;
        const right = b[index].originValue;
        return sort === 'asc' ? left - right : right - left;
      });
    }
  }
  handleTableSortAuto(item, index) {
    const old = item.sort;
    if (!old) {
      item.sort = 'asc';
      this.handleTableSort('asc', index);
    } else {
      const newSort = old === 'asc' ? 'desc' : '';
      item.sort = newSort;
      this.handleTableSort(newSort, index);
    }
  }
}
</script>

<style lang="scss">
.view-detail-modal {
  /* stylelint-disable declaration-no-important */
  z-index: 4002 !important;

  :deep(.monitor-dialog) {
    background: #f5f7fa;
  }

  .view-box {
    margin: 30px 56px 0;
    overflow: auto;

    &.reduce-box {
      padding-left: 260px;
    }

    &-header {
      display: flex;

      .view-box-header-left {
        flex: 1;

        &.show-right {
          padding-right: 16px;
        }
      }

      .compare-panel {
        width: 100%;
      }

      .right-title {
        display: flex;
        align-items: center;
        width: 360px;
        min-width: 360px;
        height: 42px;
        background: #fff;
        border-bottom: 1px solid #f0f1f5;
        border-left: 1px solid #f0f1f5;
        transition: width .3s;

        .icon-double-up {
          padding: 4px;
          font-size: 24px;
          color: #979ba5;
          cursor: pointer;
          transform: rotate(90deg);
        }

        .icon-active {
          transform: rotate(-90deg);
        }
      }

      .right-title-active {
        justify-content: center;
        width: 54px;
        min-width: 54px;
      }
    }

    &-content {
      display: flex;

      .box-left {
        width: calc(100% - 359px);
        max-height: calc(100vh - 90px);
        padding: 16px 16px 16px 0;
        overflow-y: scroll;
        transition: width .3s;

        .section-chart {
          position: relative;
          padding: 5px;
          margin-bottom: 16px;
          background: white;

          :deep(.echart-legend) {
            margin-left: 0;

            .chart-legend {
              margin-bottom: 6px;
            }
          }

          :deep(.content-wrapper) {
            width: auto !important;
          }

          :deep(.chart-tools) .icon-mc-mark {
            display: none;
          }

          .chart-drag {
            position: absolute;
            right: calc(50% - 50px);
            bottom: -3px;
            display: flex;
            align-items: center;
            justify-items: center;
            width: 100px;
            height: 6px;
            cursor: row-resize;
            background-color: #dcdee5;
            border-radius: 3px;

            &::after {
              position: absolute;
              bottom: 2px;
              left: 10px;
              width: 80px;
              height: 3px;
              content: ' ';
              border-bottom: 2px dotted white;
            }
          }
        }

        .section-box {
          min-height: 160px;
          padding: 0 20px 20px 20px;
          background: #fff;
          border-radius: 2px;
          box-shadow: 0 1px 2px 0 rgba(0, 0, 0, .1);

          &-title {
            display: flex;
            align-items: center;
            width: 100%;
            height: 54px;
            // justify-content: space-between;
            font-weight: bold;

            .title-count {
              margin-left: 16px;
              font-weight: normal;
              color: #979ba5;
            }

            .export-csv-btn {
              margin-left: auto;
            }
          }

          &-content {
            overflow-x: scroll;

            .table-item {
              min-width: 170px;
              padding: 10px 20px;
              text-align: right;

              .item-max-min {
                display: inline-block;
                width: 28px;
                height: 16px;
                margin-right: -28px;
                vertical-align: middle;
              }

              &:last-child {
                padding-right: 30px;
              }

              .table-header {
                position: relative;

                .sort-btn {
                  position: absolute;
                  top: 50%;
                  right: -18px;
                  transform: translateY(-50%);
                }
              }

              &:hover {
                cursor: pointer;
                background-color: #f0f1f5;
              }
            }

            .sort-handle {
              cursor: pointer;
            }

            .table-head {
              background: #f5f6fa;
            }

            .table-content {
              border-bottom: 1px solid #e7e8ed;
            }
          }
        }
      }

      .box-left-active {
        width: 100%;
        padding-right: 0;
      }

      .box-right {
        width: 359px;
        height: calc(100vh - 89px);
        overflow-y: scroll;
        background: #fff;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, .1);
      }
    }
  }
}
</style>
