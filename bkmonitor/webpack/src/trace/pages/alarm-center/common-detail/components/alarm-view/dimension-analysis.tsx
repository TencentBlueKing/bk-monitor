/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
 */

import { type PropType, computed, defineComponent, provide, shallowRef, toRef } from 'vue';
import { watch } from 'vue';

import { Dialog, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { getDrillDimensions } from 'monitor-api/modules/grafana';
import { graphDrillDown } from 'monitor-api/modules/scene_view';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants/charts';
import { useAppStore } from 'trace/store/modules/app';
import { useI18n } from 'vue-i18n';

import { useDimensionChartPanel } from '../../../composables/use-dimension-chart-panel';
import DimensionAnalysisTable from './components/dimension-analysis-table';
import DimensionSelector from './components/dimension-selector';
import DimensionTreeMapCharts from './echarts/dimension-tree-map-charts';
import MonitorCharts from './echarts/monitor-charts';

import type { IGraphPanel } from '../../../typings';
import type { DateValue } from '@blueking/date-picker';
import type { AlarmDetail } from 'trace/pages/alarm-center/typings/detail';

import './dimension-analysis.scss';

const TYPE_ENUM = {
  TABLE: 'table',
  CHART: 'chart',
};
const showTypeList = [
  {
    id: TYPE_ENUM.TABLE,
    icon: 'icon-mc-list',
  },
  { id: TYPE_ENUM.CHART, icon: 'icon-mc-overview' },
];

export default defineComponent({
  name: 'DimensionAnalysis',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
    /** 告警ID */
    alertId: {
      type: String,
    },
    /** 业务ID */
    bizId: {
      type: Number,
    },
    /** 默认时间范围 */
    defaultTimeRange: {
      type: Array as unknown as PropType<DateValue>,
    },
    graphPanel: {
      type: Object as PropType<IGraphPanel>,
    },
  },
  emits: {
    change: (_val: any) => true,
  },
  setup(props) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const spaceTimezone = computed(() => appStore.spaceTimezone);
    const showTypeActive = shallowRef(TYPE_ENUM.TABLE);
    const dimensionList = shallowRef([]);
    const dimensionListLoading = shallowRef(false);
    /** 是否多选 */
    const isMulti = shallowRef(false);
    /** 选中的维度 */
    const selectedDimension = shallowRef<string[]>([]);
    /** 下钻条件 */
    const where = shallowRef([]);
    // 表格数据
    const tableData = shallowRef([]);
    const tableDataLoading = shallowRef(false);
    /** 图表点击事件对象 */
    const chartClickPointEvent = shallowRef<{ xAxis: number; yAxis: number }>(null);
    /** 是否查看大图 */
    const chartIsFullscreen = shallowRef(false);

    const {
      panel,
      viewerTimeRange,
      showRestore,
      formatterChartData,
      formatterOptions,
      handleDataZoomTimeRangeChange,
      handleChartRestore,
    } = useDimensionChartPanel({
      alertId: toRef(props, 'alertId'),
      bizId: toRef(props, 'bizId'),
      defaultTimeRange: toRef(props, 'defaultTimeRange'),
      groupBy: selectedDimension,
      graphPanel: toRef(props, 'graphPanel'),
      where,
    });
    provide('timeRange', viewerTimeRange);

    const getDrillDimensionsData = async () => {
      dimensionListLoading.value = true;
      const queryConfigsParams =
        props.detail.extra_info?.strategy?.items?.[0]?.query_configs
          ?.map(queryConfig => ({
            result_table_id: queryConfig.result_table_id,
            metric_field: queryConfig.metric_field,
            configured_dimensions: queryConfig.agg_dimension || [],
          }))
          ?.filter(item => item.result_table_id && item.metric_field) || [];
      if (!queryConfigsParams.length) {
        dimensionListLoading.value = false;
        return [];
      }
      const res = await getDrillDimensions({
        bk_biz_id: props.detail.bk_biz_id,
        query_configs: queryConfigsParams,
      }).catch(() => []);
      dimensionListLoading.value = false;
      return res;
    };

    const graphDrillDownData = async () => {
      tableDataLoading.value = true;
      if (!selectedDimension.value.length) {
        tableDataLoading.value = false;
        return [];
      }
      const res = await graphDrillDown({
        bk_biz_id: props.detail.bk_biz_id,
        alert_id: props.detail.id,
        aggregation_method: 'avg',
        expression: props.detail.graph_panel?.targets?.[0]?.data?.expression || 'a',
        query_configs: props.detail.graph_panel?.targets?.[0]?.data?.query_configs?.map(queryConfig => {
          return {
            ...queryConfig,
            filter_dict: {
              ...(queryConfig.filter_dict || {}),
              ...(where.value.length
                ? {
                    drill_filter: where.value.reduce((prev, cur) => {
                      prev[cur.key] = cur.value;
                      return prev;
                    }, {}),
                  }
                : {}),
            },
          };
        }),
        start_time: dayjs(chartClickPointEvent.value?.xAxis || viewerTimeRange.value[0]).unix(),
        end_time: dayjs(viewerTimeRange.value[1]).unix(),
        group_by: selectedDimension.value,
      }).catch(() => []);
      tableData.value = res.map((item, index) => {
        return {
          ...item,
          color: COLOR_LIST[index % COLOR_LIST.length],
        };
      });
      tableDataLoading.value = false;
      return res;
    };

    watch(
      () => props.detail,
      async newVal => {
        if (newVal) {
          dimensionListLoading.value = true;
          tableDataLoading.value = true;
          const dimensionsData = await getDrillDimensionsData();
          dimensionList.value = dimensionsData.map(item => ({ id: item, name: item }));
          selectedDimension.value = dimensionList.value.length ? [dimensionList.value[0].id] : [];
          graphDrillDownData();
        }
      },
      {
        immediate: true,
      }
    );

    const handleDrillDown = (item: any) => {
      console.log(item);
    };

    const handleTableDrillDown = async (obj: { dimension: string; where: any[] }) => {
      console.log(obj);
      const existingKeys = new Set(obj.where.map(item => item.key));
      where.value = [...where.value.filter(item => !existingKeys.has(item.key)), ...obj.where];
      selectedDimension.value = [obj.dimension];
      graphDrillDownData();
    };

    const handleShowTypeChange = (val: string) => {
      showTypeActive.value = val;
    };

    const handleMultiChange = async (val: boolean) => {
      isMulti.value = val;
      if (!val) {
        selectedDimension.value = selectedDimension.value.length ? [selectedDimension.value[0]] : [];
        graphDrillDownData();
      }
    };

    const handleDimensionSelectChange = async (val: string[]) => {
      selectedDimension.value = val;
      graphDrillDownData();
    };

    const handleRemoveCondition = (index: number) => {
      where.value = [...where.value.slice(0, index), ...where.value.slice(index + 1)];
      graphDrillDownData();
    };

    /**
     * @description 处理图表空白处点击事件(zrClick)
     * @param event 图表空白处点击事件对象
     */
    const handleChartZrClick = (event: { xAxis: number; yAxis: number }) => {
      if (!event) return;
      const { xAxis, yAxis } = event;
      chartClickPointEvent.value = { xAxis, yAxis };
      graphDrillDownData();
    };

    /**
     * @description 维度分析图表 查看大图 icon 点击回调
     * @param {MouseEvent} event 事件对象
     */
    const handleFullscreen = (event: MouseEvent) => {
      event.stopPropagation();
      chartIsFullscreen.value = true;
    };

    const handleRemoveTimeCondition = () => {
      chartClickPointEvent.value = null;
      graphDrillDownData();
    };

    /**
     * @description 渲染图表
     * @param {boolean} isFullscreen 渲染的图表是否为大图状态下的图表
     */
    const renderChart = (isFullscreen = false) => {
      const chartConfig = isFullscreen
        ? {
            props: { class: 'dimension-fullscreen-chart' },
            slots: {},
          }
        : {
            props: {
              class: 'dimension-chart',
              customLegendOptions: { legendData: () => [] },
              onZrClick: handleChartZrClick,
            },
            slots: {
              customTools: () => (
                <Popover content={t('查看大图')}>
                  <i
                    class='icon-monitor icon-fullscreen dimension-chart-fullscreen'
                    onClick={handleFullscreen}
                  />
                </Popover>
              ),
            },
          };

      return (
        <MonitorCharts
          v-slots={chartConfig.slots}
          customOptions={{
            formatterData: formatterChartData,
            options: formatterOptions,
          }}
          panel={panel.value}
          showRestore={showRestore.value}
          onDataZoomChange={handleDataZoomTimeRangeChange}
          onRestore={handleChartRestore}
          {...chartConfig.props}
        />
      );
    };

    return {
      isMulti,
      showTypeActive,
      dimensionList,
      selectedDimension,
      where,
      panel,
      showRestore,
      tableData,
      tableDataLoading,
      dimensionListLoading,
      chartClickPointEvent,
      spaceTimezone,
      chartIsFullscreen,
      formatterChartData,
      handleDrillDown,
      handleTableDrillDown,
      handleShowTypeChange,
      handleMultiChange,
      handleDimensionSelectChange,
      handleRemoveCondition,
      handleDataZoomTimeRangeChange,
      handleChartRestore,
      handleChartZrClick,
      handleRemoveTimeCondition,
      handleFullscreen,
      renderChart,
      t,
    };
  },
  render() {
    return (
      <div class='alarm-view-panel-dimension-analysis-wrap'>
        <div class='alarm-dimension-chart'>{this.renderChart()}</div>
        <div class='dimension-analysis-table-view'>
          <div class='dimension-analysis-left'>
            <DimensionSelector
              dimensions={this.dimensionList}
              isMulti={this.isMulti}
              loading={this.dimensionListLoading}
              selected={this.selectedDimension}
              onChange={this.handleDimensionSelectChange}
              onMultiChange={this.handleMultiChange}
            />
          </div>
          <div class='dimension-analysis-right'>
            <div class='type-select'>
              {showTypeList.map(item => (
                <div
                  key={item.id}
                  class={['type-select-item', { active: this.showTypeActive === item.id }]}
                  onClick={() => this.handleShowTypeChange(item.id)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>

            {(this.where.length > 0 || !!this.chartClickPointEvent) && (
              <div class='conditions-wrap'>
                {!!this.chartClickPointEvent && (
                  <div class='condition-item'>
                    <span class='text-ellipsis'>{this.t('时间')}</span>
                    <span class='method'>=</span>
                    <span class='text-ellipsis'>
                      {dayjs(this.chartClickPointEvent.xAxis).tz(this.spaceTimezone).format('YYYY-MM-DD HH:mm:ssZZ')}
                    </span>

                    <span
                      class='icon-monitor icon-mc-close'
                      onClick={() => this.handleRemoveTimeCondition()}
                    />
                  </div>
                )}
                {this.where.map((item, index) => (
                  <div
                    key={index}
                    class='condition-item'
                  >
                    <span class='text-ellipsis'>{item.key}</span>
                    <span class='method'>=</span>
                    <span class='text-ellipsis'>{item.value || '--'}</span>
                    <span
                      class='icon-monitor icon-mc-close'
                      onClick={() => this.handleRemoveCondition(index)}
                    />
                  </div>
                ))}
              </div>
            )}
            <div class='dimension-analysis-data'>
              {this.showTypeActive === TYPE_ENUM.TABLE ? (
                <DimensionAnalysisTable
                  dimensions={this.dimensionList}
                  displayDimensions={this.selectedDimension}
                  loading={this.tableDataLoading}
                  tableData={this.tableData}
                  onDrillDown={this.handleTableDrillDown}
                />
              ) : (
                <DimensionTreeMapCharts
                  chartData={this.tableData}
                  dimensionList={this.dimensionList}
                  displayDimensions={this.selectedDimension}
                  onDrillDown={this.handleTableDrillDown}
                />
              )}
            </div>
          </div>
        </div>
        <Dialog
          class='alarm-dimension-chart-full-dialog'
          dialog-type='if'
          draggable={false}
          header-align='center'
          is-show={this.chartIsFullscreen}
          title={this.t('查看大图')}
          zIndex={8004}
          fullscreen
          onClosed={() => {
            this.chartIsFullscreen = false;
          }}
        >
          <div class='view-wrap'>{this.renderChart(true)}</div>
        </Dialog>
      </div>
    );
  },
});
