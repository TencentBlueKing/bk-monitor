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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type PropType, defineComponent } from 'vue';

import {
  traceDownloadTopK,
  traceFieldStatisticsGraph,
  traceFieldStatisticsInfo,
  traceFieldsTopK,
} from 'monitor-api/modules/apm_trace';
import { useI18n } from 'vue-i18n';

import StatisticsInfo from './statistics-info';
import StatisticsSlider from './statistics-slider';
import TopKFieldList from './topk-field-list';
import TopKListHeader from './topk-list-header';
import { type IStatisticsApi, useStatisticsData } from './use-statistics-data';

import type { TimeRangeType } from '../../../../components/time-range/utils';
import type { IStatisticsFieldItem } from '../../../rum-explore/composables/use-field-statistics-popover';
import type { ConditionChangeEvent, ICommonParams } from '../../typing';

import './statistics-list.scss';

const DEFAULT_STATISTICS_API: IStatisticsApi = {
  fieldsTopK: traceFieldsTopK,
  fieldStatisticsInfo: traceFieldStatisticsInfo,
  fieldStatisticsGraph: traceFieldStatisticsGraph,
  downloadTopK: traceDownloadTopK,
};

/**
 * 维度字段统计分析弹层 + TopK 全量侧栏。
 *
 * 上层分发组件：通过 isDuration / isInteger 归一化为 mode（duration/integer/text），
 * 字段名/单位/类型/枚举值统一从 field prop 取值；数据流收敛在 useStatisticsData，展示差异收敛在各子组件。
 */
export default defineComponent({
  name: 'StatisticsList',
  props: {
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
    /** 统计分析的字段对象，字段名/单位/类型/枚举值等均从这里取值 */
    field: {
      type: Object as PropType<IStatisticsFieldItem | null>,
      default: null,
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
    isDuration: {
      type: Boolean,
      default: false,
    },
    isInteger: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    conditionChange: (_condition: ConditionChangeEvent) => true,
    showMore: () => true,
    sliderShowChange: (_show: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const {
      mode,
      localField,
      rangeText,
      infoLoading,
      popoverLoading,
      statisticsInfo,
      statisticsList,
      chartData,
      downloadLoading,
      sliderShow,
      sliderLoading,
      sliderLoadMoreLoading,
      sliderDimensionList,
      showMore,
      loadMore,
      handleSliderShowChange,
      handleDownload,
    } = useStatisticsData(props, {
      onShowMore: () => emit('showMore'),
      onSliderShowChange: show => emit('sliderShowChange', show),
    });

    function handleConditionChange(condition: ConditionChangeEvent) {
      emit('conditionChange', condition);
    }

    return {
      t,
      mode,
      localField,
      rangeText,
      infoLoading,
      popoverLoading,
      statisticsInfo,
      statisticsList,
      chartData,
      downloadLoading,
      sliderShow,
      sliderLoading,
      sliderLoadMoreLoading,
      sliderDimensionList,
      showMore,
      loadMore,
      handleSliderShowChange,
      handleDownload,
      handleConditionChange,
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
              <StatisticsInfo
                chartData={this.chartData}
                loading={this.infoLoading}
                mode={this.mode}
                rangeText={this.rangeText}
                statisticsInfo={this.statisticsInfo}
              />
              <div class='top-k-list-header'>
                <TopKListHeader
                  displayName={this.field?.levelAlias || this.field?.name || ''}
                  distinctCount={this.statisticsList?.distinct_count}
                  downloadLoading={this.downloadLoading}
                  onDownload={this.handleDownload}
                />
              </div>
              <TopKFieldList
                fieldName={this.localField}
                list={this.statisticsList?.list}
                loading={this.popoverLoading}
                mode={this.mode}
                scene='popover'
                onConditionChange={this.handleConditionChange}
              />
              {this.statisticsList?.distinct_count > 5 && (
                <div
                  class={['load-more', { 'is-duration': this.mode === 'duration' }]}
                  onClick={this.showMore}
                >
                  {this.t('更多')}
                </div>
              )}
            </div>
          )}
        </div>

        <StatisticsSlider
          downloadLoading={this.downloadLoading}
          fieldName={this.localField}
          list={this.sliderDimensionList}
          loading={this.sliderLoading}
          loadMoreLoading={this.sliderLoadMoreLoading}
          mode={this.mode}
          show={this.sliderShow}
          onConditionChange={this.handleConditionChange}
          onDownload={this.handleDownload}
          onLoadMore={this.loadMore}
          onShowChange={this.handleSliderShowChange}
        />
      </div>
    );
  },
});
