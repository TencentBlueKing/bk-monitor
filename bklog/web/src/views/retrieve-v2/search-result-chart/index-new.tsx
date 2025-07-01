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

import { defineComponent, ref, computed, nextTick, onMounted, watch } from 'vue';
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';
import ChartTitleV2 from '@/components/monitor-echarts/components/chart-title-v2.vue';
import TrendChart from '@/components/monitor-echarts/trend-chart.vue';
import useLocale from '@/hooks/use-locale';

import { formatNumberWithRegex } from '../../../common/util';
import BklogPopover from '@/components/bklog-popover';
import GradeOption from '@/components/monitor-echarts/components/grade-option';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';

import './index-new.scss';
import ChartTitle from '@/components/monitor-echarts/components/chart-title-v2.vue';

export default defineComponent({
  name: 'SearchResultChart',
  emits: ['toggle-change'],
  setup(props, { emit }) {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();
    const { t } = useLocale();

    const chartContainer = ref<HTMLElement | null>(null);
    const chartTitle = ref<HTMLElement | null>(null);
    const isFold = ref<boolean>(true);
    const chartInterval = ref<string>('auto');
    const subtitle = ref<string>(''); // 如有副标题可用
    const refGradePopover = ref();
    const refGradeOption = ref();

    // 监听store中interval变化，自动同步到chartInterval
    watch(
      () => store.getters.retrieveParams.interval,
      (newVal) => {
        chartInterval.value = newVal;
      },
      { immediate: true }
    );

    const tippyOptions = {
      appendTo: document.body,
      hideOnClick: false,
      onShown: () => {
        const cfg = store.state.indexFieldInfo.custom_config?.grade_options ?? {};
        refGradeOption.value?.updateOptions?.(cfg);
      },
    };

    const beforePopoverHide = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (
        ((target.classList.contains('bk-option-name') || target.classList.contains('bk-option-content-default')) &&
          target.closest('.bk-select-dropdown-content.bklog-popover-stop')) ||
        target.classList.contains('bklog-popover-stop')
      ) {
        return false;
      }
      return true;
    };

    const handleGradeOptionChange = ({ isSave }) => {
      refGradePopover.value?.hide();
      if (isSave) {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
      }
    };

    const searchTotal = computed(() => {
      if (store.state.searchTotal > 0) {
        return store.state.searchTotal;
      }
      return store.state.retrieve.trendDataCount;
    });

    const loading = computed(() => store.state.retrieve.isTrendDataLoading);
    const totalCount = computed(() => {
      if (store.state.searchTotal > 0) {
        return store.state.searchTotal;
      }
      return store.state.retrieve.trendDataCount;
    });
    const tookTime = computed(() => Number.parseFloat(store.state.tookTime).toFixed(0));

    const intervalArr = [
      { id: 'auto', name: 'auto' },
      { id: '1m', name: '1 min' },
      { id: '5m', name: '5 min' },
      { id: '1h', name: '1 h' },
      { id: '1d', name: '1 d' },
    ];

    const getShowTotalNum = (num: number) => formatNumberWithRegex(num);

    const getOffsetHeight = () => chartContainer.value?.offsetHeight ?? 26;

    const toggleExpand = (val: boolean) => {
      isFold.value = val;
      localStorage.setItem('chartIsFold', JSON.stringify(val));
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });
    };

    const handleChangeInterval = (v: string) => {
      chartInterval.value = v;
      store.commit('updateIndexItem', { interval: v });
      store.commit('retrieve/updateChartKey', { prefix: 'chart_interval_' });
      router.replace({
        query: {
          ...route.query,
          interval: v,
        },
      });
      // 触发趋势图刷新
      setTimeout(() => {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
      });
    };

    // 图表内容渲染
    const trendChart = () => {
      return t('图表内容');
    };

    onMounted(() => {
      isFold.value = JSON.parse(localStorage.getItem('chartIsFold') || 'true');
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });
    });

    return () => (
      <div
        ref={chartContainer}
        class={['monitor-echarts-container', { 'is-fold': isFold.value }]}
        data-test-id='retrieve_div_generalTrendEcharts'
      >
        {/* 标题部分 */}
        {/* <ChartTitleV2
          class="monitor-echarts-title"
          isFold={isFold.value}
          title={t('总趋势')}
          totalCount={searchTotal.value}
          loading={loading.value}
          on-interval-change={handleChangeInterval}
          on-toggle-expand={toggleExpand}
        /> */}
        <div class='title-wrapper-new'>
          <div
            ref={chartTitle}
            class='chart-title'
            tabindex={0}
          >
            <div class='main-title'>
              <div
                class='title-click'
                onClick={() => toggleExpand(!isFold.value)}
              >
                <span class={['bk-icon', 'icon-down-shape', { 'is-flip': isFold.value }]}></span>
                <div class='title-name'>{t('总趋势')}</div>
                <i18n
                  class="time-result"
                  path="（找到 {0} 条结果，用时 {1} 毫秒) {2}"
                >
                  <span class="total-count">{getShowTotalNum(totalCount.value)}</span>
                  <span>{tookTime.value}</span>
                </i18n>
              </div>
              {!isFold.value && (
                <div class='converge-cycle'>
                  <span>{t('汇聚周期')} : </span>
                  <bk-select
                    ext-cls="select-custom"
                    value={chartInterval.value}
                    clearable={false}
                    popover-width={70}
                    behavior="simplicity"
                    data-test-id="generalTrendEcharts_div_selectCycle"
                    size="small"
                    onChange={handleChangeInterval}
                  >
                    {intervalArr.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                  <BklogPopover
                    content-class="bklog-v3-grade-setting"
                    ref={refGradePopover}
                    options={tippyOptions as any}
                    beforeHide={beforePopoverHide}
                    content={() => <GradeOption
                          ref={refGradeOption}
                          on-Change={handleGradeOptionChange}
                        />}
                  >
                    <span class="bklog-icon bklog-shezhi"></span>
                  </BklogPopover>
                </div>
              )}
            </div>
            {subtitle.value && <div class='sub-title'>{subtitle.value}</div>}
          </div>
          {loading.value && !isFold.value && <bk-spin class='chart-spin'></bk-spin>}
        </div>
        {/* 图表部分 */}
        {!isFold.value && (
          <TrendChart
            ref="chartRef"
          />
        )}
        {/* {!isFold.value && trendChart()} */}
      </div>
    );
  },
});
