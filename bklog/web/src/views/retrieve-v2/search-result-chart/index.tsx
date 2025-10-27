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

import { defineComponent, ref, computed, nextTick, onMounted, watch, onBeforeUnmount, inject } from 'vue';

import { formatNumberWithRegex } from '@/common/util';
import BklogPopover from '@/components/bklog-popover';
import GradeOption from '@/components/monitor-echarts/components/grade-option';
import useLocale from '@/hooks/use-locale';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import useStore from '@/hooks/use-store';
import useTrendChart from '@/hooks/use-trend-chart';
import { getCommonFilterAddition } from '@/store/helper';
import { BK_LOG_STORAGE } from '@/store/store.type.ts';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';
import { throttle } from 'lodash-es';
import { useRoute, useRouter } from 'vue-router/composables';

import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'SearchResultChart',
  emits: ['toggle-change'],
  setup(_props, { emit }) {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();
    const { t } = useLocale();

    // 图表容器和标题的 DOM 引用
    const chartContainer = ref<HTMLElement | null>(null);
    const chartTitle = ref<HTMLElement | null>(null);

    // 折叠状态
    const isFold = ref<boolean>(false);

    // 当前选中的汇聚周期
    const chartInterval = ref<string>('auto');

    const subtitle = ref<string>(''); // 如有副标题可用
    const refGradePopover = ref();
    const refGradeOption = ref();

    const trendChartCanvas = ref(null);
    const dynamicHeight = ref(130);

    const retrieveParams = computed(() => store.getters.retrieveParams);
    const requestAddition = computed(() => store.getters.requestAddition ?? []);
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const unionIndexList = computed(() => store.getters.unionIndexList);
    const gradeOptions = computed(() => store.state.indexFieldInfo.custom_config?.grade_options);

    const finishPolling = ref(false); // 是否完成轮询
    const isStart = ref(false); // 是否开始轮询
    let runningInterval = 'auto'; // 当前实际使用的 interval

    let logChartCancel: any = null; // 取消请求的方法
    // let isInit = true; // 是否为首次请求
    let runningTimer: any = null; // 定时器

    // 初始化、设置、重绘图表
    const handleChartDataZoom = inject('handleChartDataZoom', () => {});
    const { initChartData, setChartData, backToPreChart, canGoBack } = useTrendChart({
      target: trendChartCanvas,
      handleChartDataZoom,
      dynamicHeight,
    });

    // 监听store中interval变化，自动同步到chartInterval
    watch(
      () => store.getters.retrieveParams.interval,
      newVal => {
        chartInterval.value = newVal;
      },
      { immediate: true },
    );

    const tippyOptions = {
      appendTo: document.body,
      hideOnClick: false,
      onShown: () => {
        // popover 展开时，更新分级配置
        const cfg = store.state.indexFieldInfo.custom_config?.grade_options ?? {};
        refGradeOption.value?.updateOptions?.(cfg);
      },
    };

    // popover 隐藏前的拦截逻辑
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

    // 分级配置变更回调
    const handleGradeOptionChange = ({ isSave }) => {
      refGradePopover.value?.hide();
      if (isSave) {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
      }
    };

    // 是否正在加载趋势图数据
    const loading = computed(() => store.state.retrieve.isTrendDataLoading);

    // 总条数和耗时
    const totalCount = computed(() => store.state.searchTotal);
    const tookTime = computed(() => Number.parseFloat(store.state.tookTime).toFixed(0));

    // 汇聚周期选项
    const intervalArr = [
      { id: 'auto', name: 'auto' },
      { id: '1m', name: '1 min' },
      { id: '5m', name: '5 min' },
      { id: '1h', name: '1 h' },
      { id: '1d', name: '1 d' },
    ];

    // 格式化数字
    const getShowTotalNum = (num: number) => formatNumberWithRegex(num);

    // 获取容器高度
    const getOffsetHeight = () => chartContainer.value?.offsetHeight ?? 26;

    // 切换折叠状态
    const toggleExpand = (val: boolean) => {
      isFold.value = val;
      store.commit('updateStorage', { [BK_LOG_STORAGE.TREND_CHART_IS_FOLD]: val });
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });
    };

    // 切换汇聚周期
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
      store.commit('retrieve/updateTrendDataLoading', true);
      setTimeout(() => {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH); // 触发趋势图刷新
      });
    };

    // 节流后的回退操作函数
    const throttledBackToPreChart = throttle(backToPreChart, 500, { trailing: false });

    /**
     * 分段请求的原因：
     * 当查询的时间范围较大时，单次请求的数据量可能非常大，容易导致后端超时或前端卡顿。
     * 通过将大时间段拆分为多个小时间段分别请求，可以降低单次请求压力，提高数据加载的稳定性和用户体验。
     * 例如：若时间范围为近30天，一次请求时间可能会很长，前端等待时间会变长，导致页面出现卡顿现象。
     */
    // 根据时间范围决定是否分段请求
    const handleRequestSplit = (startTime, endTime) => {
      // if(chartInterval.value === 'auto') return 0; // 若需要auto模式下不分段请求，取消注释
      const duration = (endTime - startTime) / 3_600_000; // 计算时间间隔,单位:小时
      if (duration <= 6) {
        return 0;
      } // 0-6小时不分段请求
      if (duration <= 48) {
        return 21_600 * 1000;
      } // 6-48小时, 每6小时1段
      return (86_400 * 1000) / 2; // 超过48小时, 每12小时1段
    };

    // 趋势图数据请求主函数
    const getSeriesData = async (startTimeStamp, endTimeStamp) => {
      finishPolling.value = false;
      store.commit('retrieve/updateTrendDataLoading', true);

      try {
        const requestInterval = handleRequestSplit(startTimeStamp, endTimeStamp); // 计算请求接口的分段间隔,单位:毫秒
        const gen = getGenFn({ startTimeStamp, endTimeStamp, requestInterval }); // 定义生成器

        isStart.value = true; // 开始请求，设置状态

        let result: IteratorResult<{ urlStr: string; indexId: string | string[]; queryData: any; isInit: boolean }>;
        result = gen.next();
        while (!result.done) {
          const { urlStr, indexId, queryData, isInit: currentIsInit } = result.value;
          try {
            const res = await fetchTrendChartData(urlStr, indexId, queryData);
            setChartData(res?.data?.aggs, queryData.group_field, currentIsInit);

            if (!res?.result || requestInterval === 0) {
              break;
            }
          } catch {
            setChartData(null, null, true); // 清空图表数据
            break;
          }
          result = gen.next();
        }
      } finally {
        // 无论如何，结束时都更新状态
        finishPolling.value = true;
        isStart.value = false;
        store.commit('retrieve/updateTrendDataLoading', false);
      }
    };

    // 趋势图数据请求生成器
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    function* getGenFn({ startTimeStamp, endTimeStamp, requestInterval }) {
      const { interval } = initChartData(); // 获取趋势图汇聚周期
      runningInterval = interval;

      let currentTimeStamp = endTimeStamp; // 从最后一段时间开始请求
      let localIsInit = true; // 添加初始化标志，控制图表首次渲染

      // 组装请求参数方法
      const buildQueryParams = (start_time, end_time) => {
        const indexId = window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId;
        const urlStr = isUnionSearch.value ? 'unionSearch/unionDateHistogram' : 'retrieve/getLogChartList';
        const queryData = {
          ...retrieveParams.value,
          addition: [...requestAddition.value, ...getCommonFilterAddition(store.state)],
          time_range: 'customized',
          interval: runningInterval,
          start_time,
          end_time,
        };
        if (isUnionSearch.value) {
          Object.assign(queryData, { index_set_ids: unionIndexList.value });
        }
        if (
          gradeOptions.value &&
          !gradeOptions.value.disabled &&
          gradeOptions.value.type === 'custom' &&
          gradeOptions.value.field
        ) {
          Object.assign(queryData, { group_field: gradeOptions.value.field });
        }
        return { urlStr, indexId, queryData };
      };

      while (currentTimeStamp > startTimeStamp) {
        // 计算本轮请求结束时间
        const end_time = requestInterval === 0 ? endTimeStamp : currentTimeStamp;

        // 计算本轮请求开始时间
        let start_time = requestInterval === 0 ? startTimeStamp : end_time - requestInterval;

        // 边界条件处理
        if (start_time < startTimeStamp) {
          start_time = startTimeStamp;
        }
        if (start_time < retrieveParams.value.start_time) {
          start_time = retrieveParams.value.start_time;
        }
        if (start_time > end_time) {
          return;
        }

        // 获取请求参数
        const params = buildQueryParams(start_time, end_time);

        if ((!isUnionSearch.value && !!params.indexId) || (isUnionSearch.value && unionIndexList.value?.length)) {
          yield { ...params, isInit: localIsInit };

          // 更新isInit状态
          localIsInit = false;

          // 如果不分段，请求一次就直接结束
          if (requestInterval === 0) {
            break;
          }

          // 如果已经到达起始时间，结束生成yield
          if (start_time === startTimeStamp) {
            return;
          }

          currentTimeStamp -= requestInterval;
        } else {
          return; // 无有效索引时直接退出
        }
      }
    }

    // 趋势图数据请求接口
    const fetchTrendChartData = (urlStr, indexId, queryData) => {
      const controller = new AbortController();
      logChartCancel = () => controller.abort();

      return http.request(
        urlStr,
        {
          params: { index_set_id: indexId },
          data: queryData,
        },
        {
          signal: controller.signal,
        },
      );
    };

    // 加载趋势图数据
    const loadTrendData = () => {
      store.commit('retrieve/updateTrendDataLoading', true); // 开始加载前，打开loading

      logChartCancel?.(); // 取消上一次未完成的趋势图请求
      setChartData(null, null, true); // 清空图表数据, 重置为初始状态

      runningTimer && clearTimeout(runningTimer); // 清理上一次的定时器

      // 开始拉取新一轮趋势数据
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      runningTimer = setTimeout(async () => {
        finishPolling.value = false;
        // isInit = true;
        // 若未选择索引集（无索引集或索引集为空数组），则直接关闭loading 并终止后续流程
        if (!store.state.indexItem.ids?.length) {
          isStart.value = false;
          store.commit('retrieve/updateTrendDataLoading', false);
          return;
        }
        // 1. 先请求总数
        const res = await store.dispatch('requestSearchTotal');
        // 2. 判断总数是否为0或请求是否失败
        if (store.state.searchTotal === 0 || res.result === false) {
          isStart.value = false;
          store.commit('retrieve/updateTrendDataLoading', false);
          return;
        }
        // 3. 有数据才请求趋势图
        getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time).catch(e => console.log(e));
      });
    };

    const { addEvent } = useRetrieveEvent();
    addEvent(
      [
        RetrieveEvent.SEARCH_VALUE_CHANGE,
        RetrieveEvent.SEARCH_TIME_CHANGE,
        RetrieveEvent.TREND_GRAPH_SEARCH,
        RetrieveEvent.FAVORITE_ACTIVE_CHANGE,
        RetrieveEvent.INDEX_SET_ID_CHANGE,
        RetrieveEvent.AUTO_REFRESH
      ],
      loadTrendData,
    );

    onMounted(() => {
      // 初始化折叠状态
      isFold.value = store.state.storage[BK_LOG_STORAGE.TREND_CHART_IS_FOLD];
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });

      loadTrendData();
    });

    onBeforeUnmount(() => {
      // 组件卸载时清理定时器和事件监听
      runningTimer && clearTimeout(runningTimer);
      logChartCancel?.();
    });

    // 渲染标题内容
    const chartTitleContent = () => {
      return (
        <div
          ref={chartTitle}
          class='chart-title'
          tabindex={0}
        >
          <div class='main-title'>
            {/* 折叠/展开按钮及主标题 */}
            <div
              class='title-click'
              onClick={() => toggleExpand(!isFold.value)}
            >
              <span class={['bk-icon', 'icon-down-shape', { 'is-flip': isFold.value }]} />
              <div class='title-name'>{t('总趋势')}</div>
              <i18n
                class='time-result'
                path='（找到 {0} 条结果，用时 {1} 毫秒) {2}'
              >
                <span class='total-count'>{getShowTotalNum(totalCount.value)}</span>
                <span>{tookTime.value}</span>
              </i18n>
            </div>
            {/* 汇聚周期选择与分级设置 */}
            {!isFold.value && (
              <div class='converge-cycle'>
                {canGoBack.value && (
                  <span
                    class='chart-back-btn'
                    onClick={throttledBackToPreChart}
                  >
                    <span
                      style={{ marginRight: '2px' }}
                      class='bk-icon icon-angle-left-line'
                    />
                    {t('回退')}
                  </span>
                )}
                <span>{t('汇聚周期')} : </span>
                <bk-select
                  ext-cls='select-custom'
                  behavior='simplicity'
                  clearable={false}
                  data-test-id='generalTrendEcharts_div_selectCycle'
                  popover-width={70}
                  size='small'
                  value={chartInterval.value}
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
                  ref={refGradePopover}
                  content={() => (
                    <GradeOption
                      ref={refGradeOption}
                      on-Change={handleGradeOptionChange}
                    />
                  )}
                  beforeHide={beforePopoverHide}
                  content-class='bklog-v3-grade-setting'
                  options={tippyOptions as any}
                >
                  <span class='bklog-icon bklog-shezhi' />
                </BklogPopover>
              </div>
            )}
          </div>
          {/* 副标题 */}
          {subtitle.value && <div class='sub-title'>{subtitle.value}</div>}
        </div>
      );
    };

    // 渲染主入口
    return () => (
      <div
        ref={chartContainer}
        class={['bklog-v2-echarts-container', { 'is-fold': isFold.value }]}
        data-test-id='retrieve_div_generalTrendEcharts'
      >
        {/* 标题部分 */}
        <div class='title-wrapper'>
          {/* 1. 标题内容 */}
          {chartTitleContent()}
          {/* 2. 加载中动画 */}
          {loading.value && !isFold.value && <bk-spin class='chart-spin' />}
        </div>
        {/* 图表部分 */}
        <div
          class='echart-wrapper'
          v-bkloading={{ isLoading: !isStart.value && loading.value, size: 'mini' }}
          v-show={!isFold.value}
        >
          <div
            ref={trendChartCanvas}
            style={{ height: `${dynamicHeight.value}px` }}
          />
        </div>
      </div>
    );
  },
});
