/*
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
 */

import { defineComponent, reactive, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { $bkPopover, Progress, Sideslider } from 'bkui-vue';
import { CancelToken } from 'monitor-api/index';
import {
  traceDownloadTopK,
  traceFieldStatisticsGraph,
  traceFieldStatisticsInfo,
  traceFieldsTopK,
} from 'monitor-api/modules/apm_trace';
import { downloadFile } from 'monitor-common/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { handleTransformTime, handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useTraceExploreStore } from '../../../store/modules/explore';
import { topKColorList } from '../utils';
import DimensionEcharts from './dimension-echarts';

import type { DimensionType, ICommonParams, IStatisticsInfo, ITopKField } from '../typing';
import type { PropType } from 'vue';

import './statistics-list.scss';

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
    fieldType: {
      type: String as PropType<DimensionType>,
      default: 'text',
    },
    isDimensions: {
      type: Boolean,
      default: false,
    },
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['conditionChange', 'showMore', 'sliderShowChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    /** 注意这里的timeRange只做展示用途，实际接口请求需要拿实时的timeRange */
    const timeRangeText = shallowRef([]);
    const infoLoading = shallowRef(false);
    const popoverLoading = shallowRef(false);

    const localField = shallowRef('');
    /** 获取字段统计接口次数，用于判断接口取消后的逻辑 */
    const getStatisticsListCount = shallowRef(1);
    const statisticsInfo = shallowRef<IStatisticsInfo>({
      field: '',
      total_count: 0,
      field_count: 0,
      distinct_count: 0,
      field_percent: 0,
    });
    const statisticsList = reactive<ITopKField>({
      distinct_count: 0,
      field: '',
      list: [],
    });
    let topKInfoCancelFn = null;
    let topKCancelFn = null;
    let topKChartCancelFn = null;
    const chartData = shallowRef([]);
    const downloadLoading = shallowRef(false);

    watch(
      () => props.isShow,
      val => {
        if (val) {
          localField.value = props.selectField;
          timeRangeText.value = handleTransformTime(store.timeRange);
          getStatisticsList();
        } else {
          statisticsList.distinct_count = 0;
          statisticsList.field = '';
          statisticsList.list = [];
          infoLoading.value = true;
        }
      }
    );

    async function getStatisticsList() {
      infoLoading.value = true;
      popoverLoading.value = true;
      getStatisticsListCount.value += 1;
      const count = getStatisticsListCount.value;
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      topKCancelFn?.();
      const data: ITopKField[] = await traceFieldsTopK(
        {
          ...props.commonParams,
          start_time,
          end_time,
          limit: 5,
          fields: [localField.value],
        },
        {
          cancelToken: new CancelToken(c => (topKCancelFn = c)),
        }
      ).catch(() => [{ distinct_count: 0, field: '', list: [] }]);
      if (count !== getStatisticsListCount.value) return;
      statisticsList.distinct_count = data[0].distinct_count;
      statisticsList.field = data[0].field;
      statisticsList.list = data[0].list;
      popoverLoading.value = false;
      await getStatisticsGraphData();
    }

    async function getStatisticsGraphData() {
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      topKInfoCancelFn?.();
      const info: IStatisticsInfo = await traceFieldStatisticsInfo(
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
          cancelToken: new CancelToken(c => (topKInfoCancelFn = c)),
        }
      ).catch(() => []);
      if (!info) return;
      statisticsInfo.value = info;

      const { min, max } = statisticsInfo.value.value_analysis || {};
      const values =
        props.fieldType === 'integer'
          ? [min, max, statisticsInfo.value.distinct_count, 8]
          : statisticsList.list.map(item => item.value);
      topKChartCancelFn?.();
      const data = await traceFieldStatisticsGraph(
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
          cancelToken: new CancelToken(c => (topKChartCancelFn = c)),
        }
      ).catch(() => ({ series: [] }));

      const series = data.series || [];
      chartData.value = series.map(item => {
        const index = statisticsList.list.findIndex(i => item.dimensions?.[localField.value] === i.value) || 0;
        return {
          color: props.fieldType === 'integer' ? '#5AB8A8' : topKColorList[index],
          ...item,
        };
      });
      infoLoading.value = false;
    }

    const sliderShow = shallowRef(false);
    const sliderLoading = shallowRef(false);
    const sliderLoadMoreLoading = shallowRef(false);
    const sliderListPage = shallowRef(1);
    const sliderDimensionList = reactive<ITopKField>({
      distinct_count: 0,
      field: '',
      list: [],
    });
    const slideOverflowPopoverInstance = shallowRef(null);

    /** 展示侧栏 */
    async function showMore() {
      sliderShow.value = true;
      sliderLoading.value = true;
      sliderShowChange();
      emit('showMore');
      await loadMore();
      sliderLoading.value = false;
    }

    /** 加载更多 */
    async function loadMore() {
      sliderLoadMoreLoading.value = true;
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      const data = await traceFieldsTopK({
        ...props.commonParams,
        start_time,
        end_time,
        limit: sliderListPage.value * 100,
        fields: [localField.value],
      });
      sliderDimensionList.distinct_count = data.distinct_count;
      sliderDimensionList.field = data.field;
      sliderDimensionList.list = data.list;
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
      downloadLoading.value = true;
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      const data = await traceDownloadTopK({
        ...props.commonParams,
        start_time,
        end_time,
        limit: sliderShow.value ? sliderDimensionList?.distinct_count : statisticsList?.distinct_count,
        fields: [localField.value],
      }).finally(() => {
        downloadLoading.value = false;
      });
      try {
        downloadFile(data.data, 'txt', data.filename);
      } catch {}
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
          slideOverflowPopoverInstance.value?.show(50);
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
                    content: `${props.isDimensions ? 'dimensions.' : ''}${localField.value} = ${item.value || '""'}`,
                  }}
                  onClick={() => handleConditionChange('eq', item)}
                />
                <i
                  class='icon-monitor icon-sousuo-'
                  v-bk-tooltips={{
                    content: `${props.isDimensions ? 'dimensions.' : ''}${localField.value} != ${item.value || '""'}`,
                  }}
                  onClick={() => handleConditionChange('ne', item)}
                />
              </div>
              <div class='progress-content'>
                <div class='info-text'>
                  <span
                    class='field-name'
                    onMouseenter={e => topKItemMouseenter(e, item.alias)}
                    onMouseleave={hiddenSliderPopover}
                  >
                    {item.alias}
                  </span>
                  <span class='counts'>
                    <span class='total'>{t('{0}条', [item.count])}</span>
                    <span class='progress-count'>{item.proportions}%</span>
                  </span>
                </div>
                <Progress
                  color={props.fieldType !== 'integer' && scene === 'popover' ? topKColorList[index] : '#5AB8A8'}
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

    function handleConditionChange(type: 'eq' | 'ne', item: ITopKField['list'][0]) {
      emit('conditionChange', {
        key: localField.value,
        operator: type,
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

    return {
      t,
      timeRangeText,
      popoverLoading,
      infoLoading,
      statisticsInfo,
      statisticsList,
      chartData,
      downloadLoading,
      sliderShow,
      sliderLoading,
      sliderLoadMoreLoading,
      sliderDimensionList,
      renderTopKField,
      sliderShowChange,
      showMore,
      handleSliderShowChange,
      topKItemMouseenter,
      hiddenSliderPopover,
      handleDownload,
      loadMore,
      renderSkeleton,
    };
  },

  render() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='dimensionPopover'
          class='trace-explore-dimension-statistics-popover'
        >
          {this.infoLoading ? (
            <div class='info-skeleton'>
              <div class='total-skeleton'>
                <div class='skeleton-element' />
                <div class='skeleton-element' />
                <div class='skeleton-element' />
              </div>
              {this.fieldType === 'integer' && (
                <div class='info-skeleton'>
                  <div class='skeleton-element' />
                  <div class='skeleton-element' />
                  <div class='skeleton-element' />
                  <div class='skeleton-element' />
                </div>
              )}
              <div class='skeleton-element chart' />
            </div>
          ) : (
            <div class='statistics-info'>
              <div class='top-k-info-header'>
                <div class='label-item'>
                  <span class='label'>{this.t('总行数')}:</span>
                  <span class='value'> {this.statisticsInfo.total_count}</span>
                </div>
                <div class='label-item'>
                  <span class='label'>{this.t('出现行数')}:</span>
                  <span class='value'> {this.statisticsInfo.field_count}</span>
                </div>
                <div class='label-item'>
                  <span class='label'>{this.t('日志条数')}:</span>
                  <span class='value'> {this.statisticsInfo.field_percent}%</span>
                </div>
              </div>

              {this.fieldType === 'integer' && (
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
                  <div class='integer-item'>
                    <span class='label'>{this.t('中位数')}</span>
                    <span class='value'>{this.statisticsInfo.value_analysis?.median || 0}</span>
                  </div>
                </div>
              )}

              <div class='top-k-chart-title'>
                <span class='title'>{this.t(this.fieldType === 'integer' ? '数值分布直方图' : 'TOP 5 时序图')}</span>
                {this.fieldType === 'integer' && (
                  <span class='time-range'>
                    {this.timeRangeText[0]} ～ {this.timeRangeText[1]}
                  </span>
                )}
              </div>

              <DimensionEcharts
                data={this.chartData}
                seriesType={this.fieldType === 'integer' ? 'histogram' : 'line'}
              />
            </div>
          )}

          <div class='top-k-list-header'>
            <div class='dimension-top-k-title'>
              <span
                class='field-name'
                v-bk-overflow-tips
              >
                {this.selectField}
              </span>
              <span class='divider' />
              <span class='desc'>
                {this.$t('去重后的字段统计')} ({this.statisticsList?.distinct_count || 0})
              </span>
            </div>
            {this.downloadLoading ? (
              <img
                class='loading-icon'
                alt=''
                src={loadingIcon}
              />
            ) : (
              <div
                class='download-tool'
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-xiazai2' />
                <span class='text'>{this.$t('下载')}</span>
              </div>
            )}
          </div>
          {this.popoverLoading
            ? this.renderSkeleton()
            : [
                this.renderTopKField(this.statisticsList?.list, 'popover'),
                this.statisticsList?.distinct_count > 5 && (
                  <div
                    class='load-more'
                    onClick={this.showMore}
                  >
                    {this.$t('更多')}
                  </div>
                ),
              ]}
        </div>

        <Sideslider
          width='480'
          ext-cls='dimension-top-k-slider'
          is-show={this.sliderShow}
          // show-mask={false}
          transfer={true}
          quick-close
          onUpdate:isShow={this.handleSliderShowChange}
        >
          {{
            header: () => (
              <div class='dimension-slider-header'>
                <div class='dimension-top-k-title'>
                  <span
                    class='field-name'
                    v-bk-overflow-tips
                  >
                    {this.selectField}
                  </span>
                  <span class='divider' />
                  <span class='desc'>
                    {this.$t('去重后的字段统计')} ({this.sliderDimensionList.distinct_count || 0})
                  </span>
                </div>
                {this.downloadLoading ? (
                  <img
                    class='loading-icon'
                    alt=''
                    src={loadingIcon}
                  />
                ) : (
                  <div
                    class='download-tool'
                    onClick={this.handleDownload}
                  >
                    <i class='icon-monitor icon-xiazai2' />
                    <span class='text'>{this.$t('下载')}</span>
                  </div>
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
                    {this.$t(this.sliderLoadMoreLoading ? '正在加载...' : '加载更多')}
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
