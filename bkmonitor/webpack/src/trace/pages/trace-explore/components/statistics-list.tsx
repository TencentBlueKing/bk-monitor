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

import { type PropType, computed, defineComponent, reactive, shallowRef, watch } from 'vue';

import { $bkPopover, Progress, Sideslider } from 'bkui-vue';
import { CancelToken } from 'monitor-api/cancel';
import {
  traceDownloadTopK,
  traceFieldStatisticsGraph,
  traceFieldStatisticsInfo,
  traceFieldsTopK,
} from 'monitor-api/modules/apm_trace';
import { downloadFile, formatPercent } from 'monitor-common/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { NULL_VALUE_NAME } from '../../../components/retrieval-filter/utils';
import {
  type TimeRangeType,
  handleTransformTime,
  handleTransformToTimestamp,
} from '../../../components/time-range/utils';
import { formatDuration, formatDurationWithUnit } from '../../../components/trace-view/utils/date';
import { transformTableDataToCsvStr } from '../../../plugins/utls/menu';
import { useAppStore } from '../../../store/modules/app';
import { useTraceExploreStore } from '../../../store/modules/explore';
import { topKColorList } from '../utils';
import DimensionEcharts from './dimension-echarts';
import { transformFieldName } from './trace-explore-table/constants';

import type {
  ConditionChangeEvent,
  DimensionType,
  ICommonParams,
  IStatisticsGraph,
  IStatisticsInfo,
  ITopKField,
} from '../typing';

import './statistics-list.scss';

/**
 * 统计分析依赖的四个接口。
 * 默认对接 apm_trace，其他检索场景（如 RUM 检索）通过 api prop 注入自己的实现即可复用本组件。
 */
export interface IStatisticsApi {
  downloadTopK: (params: Record<string, unknown>) => Promise<{ data: string; filename: string }>;
  /** 返回 { series }，结构与 field_statistics_graph 协议一致；失败时调用方兜底为 { series: [] } */
  fieldStatisticsGraph: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<any>;
  /** 返回 IStatisticsInfo；失败时调用方有各自的兜底值，故此处不收紧类型 */
  fieldStatisticsInfo: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<any>;
  fieldsTopK: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<ITopKField[]>;
}

const DEFAULT_STATISTICS_API: IStatisticsApi = {
  fieldsTopK: traceFieldsTopK,
  fieldStatisticsInfo: traceFieldStatisticsInfo,
  fieldStatisticsGraph: traceFieldStatisticsGraph,
  downloadTopK: traceDownloadTopK,
};

/** 耗时字段 topk 数据，min/max 为格式化后的取值范围文本 */
type IDurationTopKField = ITopKField & { max: string; min: string };

const EMPTY_STATISTICS_INFO: IStatisticsInfo = {
  field: '',
  total_count: 0,
  field_count: 0,
  distinct_count: 0,
  field_percent: 0,
};

const EMPTY_TOPK_FIELD: ITopKField = {
  distinct_count: 0,
  field: '',
  list: [],
};

export default defineComponent({
  name: 'StatisticsList',
  props: {
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
    selectField: {
      type: String,
      default: '',
    },
    /** 字段单位，单位为 us / ms 的字段按耗时维度处理 */
    unit: {
      type: String,
      default: '',
    },
    fieldType: {
      type: String as PropType<DimensionType>,
      default: 'text',
    },
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 统计接口实现，不传则走 apm_trace */
    api: {
      type: Object as PropType<IStatisticsApi>,
      default: () => DEFAULT_STATISTICS_API,
    },
    /** 查询时间范围，不传则取 trace 检索 store 中的时间 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: null,
    },
  },
  emits: {
    conditionChange: (_condition: ConditionChangeEvent) => true,
    showMore: () => true,
    sliderShowChange: (_show: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const store = useTraceExploreStore();
    const { tableList, filterTableList } = storeToRefs(store);

    const currentTimeRange = computed<TimeRangeType>(() => props.timeRange || store.timeRange);

    /** 展示的范围文本 */
    const rangeText = shallowRef<TimeRangeType>([]);
    const infoLoading = shallowRef(false);
    const popoverLoading = shallowRef(false);

    const localField = shallowRef('');
    /** 获取字段统计接口次数，用于判断接口取消后的逻辑 */
    const getStatisticsListCount = shallowRef(1);
    /** 获取字段信息接口次数 */
    const getStatisticsInfoCount = shallowRef(1);
    const statisticsInfo = shallowRef<IStatisticsInfo>({ ...EMPTY_STATISTICS_INFO });
    const statisticsList = reactive<ITopKField>({ ...EMPTY_TOPK_FIELD });
    let topKInfoCancelFn: (() => void) | null = null;
    let topKCancelFn: (() => void) | null = null;
    let topKChartCancelFn: (() => void) | null = null;
    const chartData = shallowRef<IStatisticsGraph[]>([]);
    const downloadLoading = shallowRef(false);

    /** '耗时字段' topk列表 */
    const durationTopkList = shallowRef<IDurationTopKField>({
      distinct_count: 0,
      field: '',
      max: '',
      min: '',
      list: [],
    });

    /** 数值类型 */
    const isInteger = computed(() => ['double', 'long', 'integer'].includes(props.fieldType));

    /** 耗时维度：单位为 us / ms 的字段 */
    const isDuration = computed(() => ['us', 'ms'].includes(props.unit));

    watch(
      () => props.isShow,
      async val => {
        if (val) {
          await handleShowStatistics();
        } else {
          resetStatisticsState();
        }
      }
    );

    /** 弹窗打开：按是否耗时字段走两条数据流 */
    async function handleShowStatistics() {
      infoLoading.value = true;
      localField.value = props.selectField;
      if (!isDuration.value) {
        rangeText.value = handleTransformTime(currentTimeRange.value);
        getStatisticsList();
        return;
      }
      popoverLoading.value = true;
      await getStatisticsGraphData();
      popoverLoading.value = false;
      const { min, max, avg, median } = statisticsInfo.value.value_analysis || {};
      statisticsInfo.value.value_analysis = {
        min: formatDurationValue(min),
        max: formatDurationValue(max),
        avg: formatDurationValue(avg),
        median,
      };
      getDurationTopkList();
      rangeText.value = [durationTopkList.value.min, durationTopkList.value.max];
      statisticsList.distinct_count = durationTopkList.value.distinct_count;
      statisticsList.field = durationTopkList.value.field;
      statisticsList.list = durationTopkList.value.list.slice(0, 5);
    }

    /** 弹窗关闭：清空统计数据 */
    function resetStatisticsState() {
      statisticsList.distinct_count = 0;
      statisticsList.field = '';
      statisticsList.list = [];
      statisticsInfo.value = { ...EMPTY_STATISTICS_INFO };
      chartData.value = [];
    }

    /** 耗时统计值格式化为无空格的紧凑文本 */
    function formatDurationValue(value: number | string) {
      return formatDuration(Number(value) || 0, '', 3, props.unit).replace(/ /g, '');
    }

    /** 耗时topK列表逻辑特殊，通过traceFieldStatisticsGraph接口返回的数据由前端生成 */
    function getDurationTopkList() {
      const data = (chartData.value[0]?.datapoints as [number, string][]) || [];
      const total = data.reduce((pre, cur) => pre + cur[0], 0);
      let min = 0;
      let max = 0;
      const list = data.map((item, index) => {
        const [start, end] = item[1].split('-');
        if (index === 0) min = Number(start);
        if (index === data.length - 1) max = Number(end);
        return {
          alias: `${formatDurationWithUnit(Number(start), '', props.unit)} - ${formatDurationWithUnit(
            Number(end),
            '',
            props.unit
          )}`,
          count: item[0],
          proportions: formatPercent((item[0] / total) * 100, 3, 3, 3),
          value: item[1],
        };
      });
      durationTopkList.value = {
        distinct_count: list.length,
        field: localField.value,
        list: list.sort((a, b) => b.count - a.count),
        min: formatDurationWithUnit(min, '', props.unit),
        max: formatDurationWithUnit(max, '', props.unit),
      };
    }

    /** 获取topk列表 */
    async function getStatisticsList() {
      popoverLoading.value = true;
      getStatisticsListCount.value += 1;
      const count = getStatisticsListCount.value;
      const [start_time, end_time] = handleTransformToTimestamp(currentTimeRange.value);
      topKCancelFn?.();
      const data: ITopKField[] = await props.api
        .fieldsTopK(
          {
            ...props.commonParams,
            start_time,
            end_time,
            limit: 5,
            fields: [localField.value],
          },
          {
            cancelToken: new CancelToken(c => {
              topKCancelFn = c;
            }),
          }
        )
        .catch(() => [{ ...EMPTY_TOPK_FIELD }]);
      if (count !== getStatisticsListCount.value) return;
      statisticsList.distinct_count = data[0]?.distinct_count || 0;
      statisticsList.field = data[0]?.field || '';
      const list = data[0]?.list || [];
      statisticsList.list = list.map(item => ({
        ...item,
        alias: transformFieldName(localField.value, item.value),
      }));
      popoverLoading.value = false;
      await getStatisticsGraphData();
    }

    /** 获取维度信息和维度图表数据 */
    async function getStatisticsGraphData() {
      getStatisticsInfoCount.value += 1;
      const count = getStatisticsInfoCount.value;
      const [start_time, end_time] = handleTransformToTimestamp(currentTimeRange.value);
      topKInfoCancelFn?.();
      const info: IStatisticsInfo | null = await props.api
        .fieldStatisticsInfo(
          {
            ...props.commonParams,
            start_time,
            end_time,
            field: {
              field_name: localField.value,
              field_type: props.fieldType,
            },
          },
          {
            cancelToken: new CancelToken(c => {
              topKInfoCancelFn = c;
            }),
          }
        )
        .catch(() => null);
      /** 如果是取消接口，不进行后续操作 */
      if (count !== getStatisticsInfoCount.value) return;
      /** topk没有数据且keyword类型不请求graph接口 */
      if (!info || info.distinct_count === 0 || (props.fieldType === 'keyword' && !statisticsList.list.length)) {
        infoLoading.value = false;
        return;
      }
      statisticsInfo.value = info;
      const { min, max } = statisticsInfo.value.value_analysis || {};
      const values = isInteger.value
        ? [min, max, statisticsInfo.value.distinct_count, isDuration.value ? 15 : 10]
        : statisticsList.list.map(item => item.value);
      topKChartCancelFn?.();
      const data = await props.api
        .fieldStatisticsGraph(
          {
            ...props.commonParams,
            start_time,
            end_time,
            field: {
              field_name: localField.value,
              field_type: props.fieldType,
              values,
            },
          },
          {
            cancelToken: new CancelToken(c => {
              topKChartCancelFn = c;
            }),
          }
        )
        .catch(() => ({ series: [] }));

      const series = data.series || [];
      chartData.value = series.map(item => {
        if (isInteger.value) {
          return {
            datapoints: item.datapoints.map(point => [
              point[0],
              transformFieldName(localField.value, point[1]) || point[1],
            ]),
            color: '#5AB8A8',
            name: localField.value,
          };
        }
        const name = item.dimensions?.[localField.value];
        const index = Math.max(
          0,
          statisticsList.list.findIndex(i => name === i.value)
        );
        return {
          color: topKColorList[index],
          name: transformFieldName(localField.value, name) || name || NULL_VALUE_NAME,
          ...item,
        };
      });
      infoLoading.value = false;
    }

    const sliderShow = shallowRef(false);
    const sliderLoading = shallowRef(false);
    const sliderLoadMoreLoading = shallowRef(false);
    const sliderListPage = shallowRef(1);
    const sliderDimensionList = reactive<ITopKField>({ ...EMPTY_TOPK_FIELD });
    const slideOverflowPopoverInstance = shallowRef(null);

    /** 展示侧栏 */
    async function showMore() {
      sliderShow.value = true;
      sliderLoading.value = true;
      sliderShowChange();
      emit('showMore');
      if (!isDuration.value) {
        await loadMore();
      } else {
        sliderDimensionList.distinct_count = durationTopkList.value.distinct_count;
        sliderDimensionList.field = durationTopkList.value.field;
        sliderDimensionList.list = durationTopkList.value.list;
      }
      sliderLoading.value = false;
    }

    /** 加载更多 */
    async function loadMore() {
      sliderLoadMoreLoading.value = true;
      const [start_time, end_time] = handleTransformToTimestamp(currentTimeRange.value);
      const data = await props.api
        .fieldsTopK({
          ...props.commonParams,
          start_time,
          end_time,
          limit: sliderListPage.value * 100,
          fields: [localField.value],
        })
        .catch(() => []);
      sliderDimensionList.distinct_count = data[0]?.distinct_count || 0;
      sliderDimensionList.field = data[0]?.field || '';
      const list = data[0]?.list || [];
      sliderDimensionList.list = list.map(item => ({
        ...item,
        alias: transformFieldName(localField.value, item.value),
      }));
      sliderLoadMoreLoading.value = false;
      sliderListPage.value += 1;
    }

    function handleSliderShowChange(show: boolean) {
      sliderShow.value = show;
      sliderShowChange();
      if (!show) {
        sliderListPage.value = 1;
        sliderDimensionList.distinct_count = 0;
        sliderDimensionList.field = '';
        sliderDimensionList.list = [];
      }
    }

    async function handleDownload() {
      if (isDuration.value) {
        const csvString = transformTableDataToCsvStr(
          [],
          durationTopkList.value.list.map(item => [
            { value: item.value },
            { value: item.count },
            { value: `${item.proportions}%` },
          ])
        );
        downloadFile(
          csvString,
          'text/csv;charset=utf-8;',
          `topk_${appStore.bizId}_${props.commonParams.app_name}_${localField.value}.csv`
        );
      } else {
        downloadLoading.value = true;
        const [start_time, end_time] = handleTransformToTimestamp(currentTimeRange.value);
        const data = await props.api
          .downloadTopK({
            ...props.commonParams,
            start_time,
            end_time,
            limit: sliderShow.value ? sliderDimensionList?.distinct_count : statisticsList?.distinct_count,
            fields: [localField.value],
          })
          .finally(() => {
            downloadLoading.value = false;
          });
        try {
          downloadFile(data.data, 'txt', data.filename);
        } catch (err) {
          console.log('err', err);
        }
      }
    }

    function topKItemMouseenter(e: MouseEvent, content: string) {
      const target = e.target as HTMLElement;
      if (target.offsetWidth < target.scrollWidth) {
        slideOverflowPopoverInstance.value = $bkPopover({
          target,
          content,
          arrow: true,
          interactive: true,
          theme: 'slide-dimension-filter-overflow-tips',
        });
        slideOverflowPopoverInstance.value.install();
        setTimeout(() => {
          slideOverflowPopoverInstance.value?.show();
        }, 100);
      }
    }

    function hiddenSliderPopover() {
      slideOverflowPopoverInstance.value?.hide(0);
      slideOverflowPopoverInstance.value?.uninstall();
      slideOverflowPopoverInstance.value = null;
    }

    /** 渲染TopK字段行 */
    function renderTopKField(list: ITopKField['list'], scene: 'popover' | 'slider') {
      if (!list.length) return <EmptyStatus type='empty' />;
      return (
        <div class='top-k-list'>
          {list.map((item, index) => (
            <div
              key={item.value}
              class='top-k-list-item'
            >
              <div class='filter-tools'>
                <i
                  class='icon-monitor icon-a-sousuo'
                  v-bk-tooltips={{
                    content: `${localField.value} = ${item.value || '""'}`,
                    extCls: 'statistics-top-k-item-tooltips-wrap-popover',
                    disabled: isDuration.value,
                  }}
                  onClick={() => handleConditionChange('equal', item)}
                />
                {!isDuration.value && (
                  <i
                    class='icon-monitor icon-sousuo-'
                    v-bk-tooltips={{
                      content: `${localField.value} != ${item.value || '""'}`,
                      extCls: 'statistics-top-k-item-tooltips-wrap-popover',
                    }}
                    onClick={() => handleConditionChange('not_equal', item)}
                  />
                )}
              </div>
              <div class='progress-content'>
                <div class='info-text'>
                  <span
                    class='field-name'
                    onMouseenter={e => topKItemMouseenter(e, item.value)}
                    onMouseleave={hiddenSliderPopover}
                  >
                    <span>{item.alias || item.value || NULL_VALUE_NAME}</span>
                    {item.alias && !isDuration.value && <span class='sub-name'>（{item.value}）</span>}
                  </span>

                  <span class='counts'>
                    <span class='total'>{t('{0}条', [item.count])}</span>
                    <span class='progress-count'>{item.proportions}%</span>
                  </span>
                </div>
                <Progress
                  color={isInteger.value || scene === 'slider' ? '#5AB8A8' : topKColorList[index]}
                  percent={item.proportions}
                  show-text={false}
                  stroke-width={6}
                />
              </div>
            </div>
          ))}
        </div>
      );
    }

    function handleConditionChange(type: 'equal' | 'not_equal', item: ITopKField['list'][0]) {
      emit('conditionChange', {
        key: localField.value,
        method: isDuration.value ? 'between' : type,
        value: item.value,
      });
    }

    function sliderShowChange() {
      emit('sliderShowChange', sliderShow.value);
    }

    function renderSkeleton() {
      return (
        <div class='skeleton-wrap'>
          {new Array(5).fill(null).map((_, index) => (
            <div
              key={index}
              class='skeleton-element'
            />
          ))}
        </div>
      );
    }

    /** 统计信息区域的加载骨架 */
    function renderInfoSkeleton() {
      return (
        <div class='info-skeleton'>
          <div class='total-skeleton'>
            <div class='skeleton-element' />
            <div class='skeleton-element' />
            <div class='skeleton-element' />
          </div>
          {isInteger.value && (
            <div class='info-skeleton'>
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
            </div>
          )}
          <div class='skeleton-element chart' />
        </div>
      );
    }

    /** TopK 标题：字段名 + 去重统计数 */
    function renderTopKTitle(distinctCount?: number) {
      return (
        <div class='dimension-top-k-title'>
          <span
            class='field-name'
            v-overflow-tips
          >
            {localField.value}
          </span>
          <span class='divider' />
          <span class='desc'>
            {t('去重后的字段统计')} ({distinctCount || 0})
          </span>
        </div>
      );
    }

    return {
      t,
      localField,
      isInteger,
      rangeText,
      popoverLoading,
      infoLoading,
      statisticsInfo,
      statisticsList,
      chartData,
      tableList,
      filterTableList,
      downloadLoading,
      sliderShow,
      sliderLoading,
      sliderLoadMoreLoading,
      sliderDimensionList,
      isDuration,
      renderTopKField,
      sliderShowChange,
      showMore,
      handleSliderShowChange,
      topKItemMouseenter,
      hiddenSliderPopover,
      handleDownload,
      loadMore,
      renderSkeleton,
      renderInfoSkeleton,
      renderTopKTitle,
    };
  },

  render() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='dimensionPopover'
          class='trace-explore-dimension-statistics-popover'
        >
          {this.isShow && (
            <div class='trace-explore-dimension-statistics-popover-content'>
              {this.infoLoading ? (
                this.renderInfoSkeleton()
              ) : (
                <div class='statistics-info'>
                  {!this.isDuration && (
                    <div class='top-k-info-header'>
                      <div class='label-item'>
                        <span class='label'>{this.t('总行数')}:</span>
                        <span class='value'> {this.statisticsInfo.total_count}</span>
                      </div>
                      <div class='label-item'>
                        <span class='label'>{this.t('非空数据')}:</span>
                        <span class='value'> {this.statisticsInfo.field_count}</span>
                      </div>
                      <div class='label-item'>
                        <span class='label'>{this.t('非空数据占比')}:</span>
                        <span class='value'> {this.statisticsInfo.field_percent}%</span>
                      </div>
                    </div>
                  )}
                  {this.isInteger && (
                    <div class='integer-statics-info'>
                      <div class='integer-item'>
                        <span class='label'>{this.t('最大值')}</span>
                        <span class='value'>{this.statisticsInfo.value_analysis?.max || 0}</span>
                      </div>

                      <div class='integer-item'>
                        <span class='label'>{this.t('最小值')}</span>
                        <span class='value'>{this.statisticsInfo.value_analysis?.min || 0}</span>
                      </div>
                      <div class='integer-item'>
                        <span class='label'>{this.t('平均值')}</span>
                        <span class='value'>{this.statisticsInfo.value_analysis?.avg || 0}</span>
                      </div>
                      {!this.isDuration && (
                        <div class='integer-item'>
                          <span class='label'>{this.t('中位数')}</span>
                          <span class='value'>{this.statisticsInfo.value_analysis?.median || 0}</span>
                        </div>
                      )}
                    </div>
                  )}

                  <div class='top-k-chart-title'>
                    <span class='title'>
                      {this.t(this.isDuration ? '耗时区间' : this.isInteger ? '数值分布直方图' : 'TOP 5 时序图')}
                    </span>
                    {this.isInteger && (
                      <span
                        class='time-range'
                        v-overflow-tips
                      >
                        {this.rangeText[0]} ～ {this.rangeText[1]}
                      </span>
                    )}
                  </div>
                  <DimensionEcharts
                    data={this.chartData}
                    isDuration={this.isDuration}
                    seriesType={this.isInteger ? 'histogram' : 'line'}
                    unit={this.unit}
                  />
                </div>
              )}
              <div class='top-k-list-header'>
                {this.renderTopKTitle(this.statisticsList?.distinct_count)}
                {this.downloadLoading ? (
                  <img
                    class='loading-icon'
                    alt=''
                    src={loadingIcon}
                  />
                ) : (
                  <div
                    class='download-tool'
                    v-bk-tooltips={{ content: this.t('下载'), boundary: 'parent' }}
                    onClick={this.handleDownload}
                  >
                    <i class='icon-monitor icon-xiazai2' />
                  </div>
                )}
              </div>
              {this.popoverLoading
                ? this.renderSkeleton()
                : [
                    this.renderTopKField(this.statisticsList?.list, 'popover'),
                    this.statisticsList?.distinct_count > 5 && (
                      <div
                        class={['load-more', { 'is-duration': this.isDuration }]}
                        onClick={this.showMore}
                      >
                        {this.t('更多')}
                      </div>
                    ),
                  ]}
            </div>
          )}
        </div>

        <Sideslider
          width='480'
          ext-cls='trace-dimension-top-k-slider'
          is-show={this.sliderShow}
          transfer={true}
          quick-close
          onUpdate:isShow={this.handleSliderShowChange}
        >
          {{
            header: () => (
              <div class='dimension-slider-header'>
                {this.renderTopKTitle(this.sliderDimensionList.distinct_count)}
                {this.downloadLoading ? (
                  <img
                    class='loading-icon'
                    alt=''
                    src={loadingIcon}
                  />
                ) : (
                  !this.isDuration && (
                    <div
                      class='download-tool'
                      onClick={this.handleDownload}
                    >
                      <i class='icon-monitor icon-xiazai2' />
                      <span class='text'>{this.t('下载')}</span>
                    </div>
                  )
                )}
              </div>
            ),
            default: () => (
              <div class='dimension-slider-content'>
                {this.sliderLoading
                  ? this.renderSkeleton()
                  : this.renderTopKField(this.sliderDimensionList.list, 'slider')}
                {this.sliderDimensionList.distinct_count > this.sliderDimensionList.list.length && (
                  <div
                    class={['slider-load-more', { 'is-loading': this.sliderLoadMoreLoading }]}
                    onClick={this.loadMore}
                  >
                    {this.t(this.sliderLoadMoreLoading ? '正在加载...' : '加载更多')}
                  </div>
                )}
              </div>
            ),
          }}
        </Sideslider>
      </div>
    );
  },
});
