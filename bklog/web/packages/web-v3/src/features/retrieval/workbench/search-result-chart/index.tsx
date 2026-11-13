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

import ChartSkeleton from '@/app/skeleton/chart-skeleton';


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useRetrieveStore } from '@/app/state/domains/retrieve-store';


import { ServicesInstance } from '@/platform/services';
import type { ServiceOperation } from '@/platform/services/runtime/service-client';

import { computed, defineComponent, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { Select, Option } from 'tdesign-vue-next';
import 'tdesign-vue-next/es/select/style/index.css';

import { formatNumberWithRegex } from '@/shared/lib/util';
import BklogPopover from '@/shared/ui/bklog-popover/index';
import GradeOption from '@/features/charts/components/grade-option';
import useLocale from '@/shared/composables/use-locale';
import useRetrieveEvent from '@/shared/composables/use-retrieve-event';
import { useRetrieveLoadingCovered } from '@/features/retrieval/use-retrieve-loading-queue';

import useTrendChart from '@/shared/composables/use-trend-chart';
import { formatAdditionalFields, getCommonFilterAddition } from '@/app/state/helper';
import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
import { getEffectiveSearchTotal, normalizeSearchTotal } from '@/platform/persistence/utils/normalize-search-total';
import RetrieveHelper, { RetrieveEvent } from '@/features/retrieval/retrieve-helper';
import { throttle } from 'lodash-es';
import { useRoute, useRouter } from 'vue-router';


import './index.scss';

/** 趋势图唯一视图状态：loading/polling 不展示空态，ready/empty 为终态 */
type TrendStatus = 'loading' | 'polling' | 'ready' | 'empty';

export default defineComponent({
  name: 'SearchResultChart',
  emits: ['toggle-change', 'trend-ready', 'change-total-count', 'change-queue-res', "changeTotalCount", "changeQueueRes", "toggleChange", "trendReady"],
  setup(_props, { emit }) {
    const store = useApplicationStore();
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

    const retrieveParams = computed(() => store.retrieveParams);
    const requestAddition = computed(() => store.requestAddition ?? []);
    const isUnionSearch = computed(() => store.isUnionSearch);
    const unionIndexList = computed(() => store.unionIndexList);
    const gradeOptions = computed(() => store.indexFieldInfo.custom_config?.grade_options);

    // 唯一状态机 + 代次号（防竞态），替代 isStart/finishPolling/isChartEmpty/isEmptySettled/isSearchingCanceled
    const trendStatus = ref<TrendStatus>('loading');
    let runningInterval = 'auto';
    let trendLoadSeq = 0;
    let logChartCancel: (() => void) | null = null;
    let runningTimer: ReturnType<typeof setTimeout> | null = null;

    const isCurrentTrendLoad = (seq: number) => seq === trendLoadSeq;
    const trendLoadingCovered = useRetrieveLoadingCovered('trend');
    const isLoading = computed(() => trendStatus.value === 'loading' || trendStatus.value === 'polling');
    const showTrendSkeleton = computed(() => trendStatus.value === 'loading' && !trendLoadingCovered.value);
    const showTrendProgress = computed(() => trendStatus.value === 'polling' && !trendLoadingCovered.value && !isFold.value);
    const showEmpty = computed(() => trendStatus.value === 'empty');
    const finishPolling = computed(() => trendStatus.value === 'ready' || trendStatus.value === 'empty');

    const setTrendStatus = (status: TrendStatus, seq?: number) => {
      if (seq !== undefined && !isCurrentTrendLoad(seq)) {
        return;
      }
      trendStatus.value = status;
      useRetrieveStore().updateTrendDataLoading(status === 'loading' || status === 'polling');
    };

    // 初始化、设置、重绘图表
    const handleChartDataZoom = inject('handleChartDataZoom', () => {});
    const {
      initChartData,
      setChartData,
      backToPreChart,
      canGoBack,
      cacheChartOptions,
      restoreChartOptions,
      processChartDataWithWorker,
      destroyChart,
      ensureChart,
    } = useTrendChart({
      target: trendChartCanvas,
      handleChartDataZoom,
      dynamicHeight,
    });

    // 监听store中interval变化，自动同步到chartInterval
    watch(
      () => store.retrieveParams.interval,
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
        const cfg = store.indexFieldInfo.custom_config?.grade_options ?? {};
        refGradeOption.value?.updateOptions?.(cfg);
      },
    };

    // popover 隐藏前的拦截逻辑：点击内层浮层内的任意位置时，不关闭外层弹层
    const beforePopoverHide = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target?.closest('.bklog-popover-stop, .bk-selector-list')) {
        return false;
      }
      return true;
    };

    // 分级配置变更回调
    const handleGradeOptionChange = ({ isSave }: { isSave: boolean }) => {
      refGradePopover.value?.hide();
      if (isSave) {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH, { source: 'grade-option' });
      }
    };

    // 总趋势展示总数以 Total 接口写入的 searchTotal 为准，避免 /search 截断 total 覆盖展示
    const totalCount = computed(() => normalizeSearchTotal(store.searchTotal));
    const tookTime = computed(() => Number.parseFloat(String(store.tookTime)).toFixed(0));

    watch(
      totalCount,
      value => {
        emit('change-total-count', value);
      },
      { immediate: true },
    );

    watch(
      finishPolling,
      value => {
        emit('change-queue-res', value);
      },
      { immediate: true },
    );

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
      store.updateStorage({ [BK_LOG_STORAGE.TREND_CHART_IS_FOLD]: val });
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });
    };

    // 切换汇聚周期
    const handleChangeInterval = (v: string) => {
      chartInterval.value = v;
      store.updateIndexItem({ interval: v });
      useRetrieveStore().updateChartKey({ prefix: 'chart_interval_' });
      router.replace({
        query: {
          ...route.query,
          interval: v,
        },
      });
      useRetrieveStore().updateTrendDataLoading(true);
      RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH); // 触发趋势图刷新
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
    const handleRequestSplit = (startTime: number, endTime: number) => {
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

    const markTrendReady = () => {
      emit('trend-ready');
    };

    // 趋势图数据请求主函数
    const getSeriesData = async (startTimeStamp: number, endTimeStamp: number, seq: number) => {
      let hasMarkedReady = false;
      const ensureTrendReady = () => {
        if (hasMarkedReady) return;
        hasMarkedReady = true;
        markTrendReady();
      };

      try {
        const requestInterval = handleRequestSplit(startTimeStamp, endTimeStamp); // 计算请求接口的分段间隔,单位:毫秒
        const gen = getGenFn({ startTimeStamp, endTimeStamp, requestInterval }); // 定义生成器

        let result: ReturnType<typeof gen.next>;
        result = gen.next();
        while (!result.done) {
          if (!isCurrentTrendLoad(seq)) {
            logChartCancel?.();
            break;
          }

          const { urlStr, indexId, queryData, isInit: currentIsInit } = result.value;
          try {
            const res = await fetchTrendChartData(urlStr, indexId, queryData);
            // 请求返回后再次校验：索引切换/取消后丢弃旧响应，避免写回上一索引的图
            if (!isCurrentTrendLoad(seq)) {
              break;
            }

            // P3 优化：对于大数据量使用 Worker 处理
            const bucketCount = res?.data?.aggs?.group_by_histogram?.buckets?.length ?? 0;
            if (bucketCount > 100 && processChartDataWithWorker) {
              try {
                await processChartDataWithWorker(
                  res?.data?.aggs,
                  queryData.group_field,
                  gradeOptions.value?.settings ?? [],
                  queryData,
                  runningInterval,
                  store.indexItem.timezone,
                  currentIsInit,
                );
                if (!isCurrentTrendLoad(seq)) {
                  break;
                }
                // Worker 返回计算结果，不会更新 ECharts；使用现有回填入口提交本段数据。
                setChartData(res?.data?.aggs, queryData.group_field, currentIsInit);
              } catch {
                // Worker 处理失败，降级到主线程处理
                if (isCurrentTrendLoad(seq)) {
                  setChartData(res?.data?.aggs, queryData.group_field, currentIsInit);
                }
              }
            } else {
              setChartData(res?.data?.aggs, queryData.group_field, currentIsInit);
            }
            if (currentIsInit) {
              // 首段绘制后才能露出图表；后续分段仅显示角落进度，不能继续遮住已回填的数据。
              if (res?.result && requestInterval !== 0) {
                setTrendStatus('polling', seq);
              }
              ensureTrendReady();
            }

            if (!res?.result || requestInterval === 0) {
              break;
            }
          } catch {
            if (isCurrentTrendLoad(seq)) {
              setChartData(null, null, true); // 清空图表数据
            }
            break;
          }
          result = gen.next();
        }
      } finally {
        // 仅当前代次可收尾：旧请求 finally 不得覆盖新一轮状态
        if (isCurrentTrendLoad(seq)) {
          ensureTrendReady();
          setTrendStatus('ready', seq);
        }
      }
    };

    // 趋势图数据请求生成器
    function* getGenFn({ startTimeStamp, endTimeStamp, requestInterval }: {startTimeStamp: number; endTimeStamp: number; requestInterval: number}) {
      const { interval } = initChartData(); // 获取趋势图汇聚周期
      runningInterval = interval;

      let currentTimeStamp = endTimeStamp; // 从最后一段时间开始请求
      let localIsInit = true; // 添加初始化标志，控制图表首次渲染

      // 组装请求参数方法
      const buildQueryParams = (startTime: unknown, endTime: unknown) => {
        const indexId = window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId;
        const urlStr = isUnionSearch.value
          ? ServicesInstance.unionSearch.unionDateHistogram
          : store.isSceneMode
            ? ServicesInstance.retrieve.getSceneDateHistogram
            : ServicesInstance.retrieve.getLogChartList;
        const queryData = {
          ...retrieveParams.value,
          addition: formatAdditionalFields(store, [
            ...requestAddition.value,
            ...getCommonFilterAddition(store),
          ]),
          time_range: 'customized',
          interval: runningInterval,
          start_time: startTime,
          end_time: endTime,
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
        const endTime = requestInterval === 0 ? endTimeStamp : currentTimeStamp;

        // 计算本轮请求开始时间
        let startTime = requestInterval === 0 ? startTimeStamp : endTime - requestInterval;

        // 边界条件处理
        if (startTime < startTimeStamp) {
          startTime = startTimeStamp;
        }
        if (startTime < retrieveParams.value.start_time) {
          startTime = retrieveParams.value.start_time;
        }
        if (startTime > endTime) {
          return;
        }

        // 获取请求参数
        const params = buildQueryParams(startTime, endTime);

        if (
          store.isSceneMode ||
          (!isUnionSearch.value && !!params.indexId) ||
          (isUnionSearch.value && unionIndexList.value?.length)
        ) {
          yield { ...params, isInit: localIsInit };

          // 更新isInit状态
          localIsInit = false;

          // 如果不分段，请求一次就直接结束
          if (requestInterval === 0) {
            break;
          }

          // 如果已经到达起始时间，结束生成yield
          if (startTime === startTimeStamp) {
            return;
          }

          currentTimeStamp -= requestInterval;
        } else {
          return; // 无有效索引时直接退出
        }
      }
    }

    // 趋势图数据请求接口
    const fetchTrendChartData = (urlStr: ServiceOperation, indexId: ReturnType<typeof useRoute>['query'][string] | ReturnType<typeof useRoute>['params'][string], queryData: unknown) => {
      const controller = new AbortController();
      logChartCancel = () => controller.abort();

      const requestConfig: any = { data: queryData };
      if (!store.isSceneMode) {
        requestConfig.params = { index_set_id: indexId };
      }

      let timer: ReturnType<typeof setTimeout> | undefined;
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          reject(new Error('trend-timeout'));
        }, 20000);
      });
      return Promise.race([
        urlStr(requestConfig, {
          signal: controller.signal,
        }),
        timeout,
      ]).finally(() => {
        if (timer) clearTimeout(timer);
      });
    };

    // 结算为空态：仅当前代次、且请求结束后才展示
    const settleChartEmpty = (seq: number) => {
      if (!isCurrentTrendLoad(seq)) {
        return;
      }
      destroyChart();
      setTrendStatus('empty', seq);
      markTrendReady();
    };

    // 使进行中的请求失效（新加载 / 取消 / 清空共用）
    const invalidateTrendLoad = () => {
      trendLoadSeq += 1;
      logChartCancel?.();
      if (runningTimer) {
        clearTimeout(runningTimer);
        runningTimer = null;
      }
    };

    // 加载趋势图数据
    const loadTrendData = () => {
      // 场景化检索模式下，过滤条件为空时不加载趋势图
      if (store.isSceneMode && store.isSceneFilterEmpty) {
        setTrendStatus('empty');
        markTrendReady();
        return;
      }

      invalidateTrendLoad();
      const seq = trendLoadSeq;

      cacheChartOptions();
      useRetrieveStore().updateTotalCountLoaded(false);
      setTrendStatus('loading', seq);
      setChartData(null, null, true);

      // 开始拉取新一轮趋势数据
      runningTimer = setTimeout(async () => {
        if (!isCurrentTrendLoad(seq)) {
          return;
        }
        // 若未选择索引集（无索引集或索引集为空数组），则直接结算空态
        if (!store.indexItem.ids?.length) {
          settleChartEmpty(seq);
          return;
        }

        try {
          // 1. 先请求总数（stream 检索 meta 可能已写入 indexSetQueryResult.total）
          let totalTimer: ReturnType<typeof setTimeout> | undefined;
          const totalTimeout = new Promise(resolve => {
            totalTimer = setTimeout(() => resolve({ result: false, timeout: true }), 20000);
          });
          await Promise.race([
            store.requestSearchTotal().catch(() => ({ result: false })),
            totalTimeout,
          ]).finally(() => {
            if (totalTimer) clearTimeout(totalTimer);
          });
          if (!isCurrentTrendLoad(seq)) {
            return;
          }
          useRetrieveStore().updateTotalCountLoaded(true);
          // 2. 结果为空：整轮前置请求结束后再结算空态（含 stream meta 兜底）
          if (!getEffectiveSearchTotal(store)) {
            settleChartEmpty(seq);
            return;
          }
          // 3. 有数据：确保实例存在后再请求趋势图（空态恢复时需重新 init）
          const ready = await ensureChart();
          if (!isCurrentTrendLoad(seq)) {
            return;
          }
          if (!ready) {
            setTrendStatus('ready', seq);
            markTrendReady();
            return;
          }
          getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time, seq).catch(e => console.log(e));
        } catch (e) {
          console.error(e);
          if (isCurrentTrendLoad(seq)) {
            setChartData(null, null, true);
            setTrendStatus('ready', seq);
            markTrendReady();
          }
        }
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
        RetrieveEvent.AUTO_REFRESH,
        RetrieveEvent.SORT_LIST_CHANGED,
        RetrieveEvent.SEARCH_TIME_ZONE_CHANGE,
      ],
      loadTrendData,
    );

    addEvent(RetrieveEvent.TREND_GRAPH_CLEAR, () => {
      invalidateTrendLoad();
      destroyChart();
      store.SET_APP_STATE({ searchTotal: 0, tookTime: 0 });
      setTrendStatus('empty');
    });

    addEvent(RetrieveEvent.SEARCH_CANCEL, () => {
      const wasEmpty = trendStatus.value === 'empty';
      invalidateTrendLoad();
      // 取消时若当前为空态则保持空态；有图则恢复取消前缓存
      if (!wasEmpty) {
        restoreChartOptions();
        setTrendStatus('ready');
      } else {
        setTrendStatus('empty');
      }
      markTrendReady();
    });

    onMounted(() => {
      // 初始化折叠状态
      isFold.value = store.storage[BK_LOG_STORAGE.TREND_CHART_IS_FOLD] ?? false;
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });

      loadTrendData();
    });

    onBeforeUnmount(() => {
      invalidateTrendLoad();
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
                <Select
                  class='select-custom'
                  borderless
                  clearable={false}
                  data-test-id='generalTrendEcharts_div_selectCycle'
                  popupProps={{ overlayInnerStyle: { width: '70px' } }}
                  size='small'
                  value={chartInterval.value}
                  onChange={value => { if (typeof value === 'string') handleChangeInterval(value); }}
                >
                  {intervalArr.map(option => (
                    <Option
                      value={option.id}
                      key={option.id}
                      label={option.name}
                    />
                  ))}
                </Select>
                {!store.isSceneMode && (
                  <BklogPopover
                    ref={refGradePopover}
                    content={() => (
                      <GradeOption
                        ref={refGradeOption}
                        onChange={handleGradeOptionChange}
                      />
                    )}
                    beforeHide={beforePopoverHide}
                    contentClass='bklog-v3-grade-setting bklog-popover-stop'
                    ignoreSelector='.bklog-popover-stop, .bk-selector-list, .bk-select-dropdown'
                    overlayGroup='retrieve-grade'
                    options={tippyOptions as any}
                  >
                    <span class='bklog-icon bklog-shezhi' />
                  </BklogPopover>
                )}
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
          {chartTitleContent()}
          {showTrendProgress.value && (
            <span class='chart-spin trend-chart-progress' role='status' aria-label={t('加载中')} data-testid='trend-chart-progress'>
              <svg width='16' height='16' viewBox='0 0 16 16' aria-hidden='true'>
                <circle cx='8' cy='8' r='6' fill='none' stroke='currentColor' stroke-width='2' stroke-dasharray='28 10' />
              </svg>
            </span>
          )}
        </div>
        {/* 图表部分：loading/polling 不展示空态；empty 为唯一空态终态 */}
        <div
          class='echart-wrapper'
          aria-busy={isLoading.value}
          v-show={!isFold.value}
        >
          {showTrendSkeleton.value && (
            <div class='trend-chart-loading-overlay' role='status' aria-label={t('加载中')} data-testid='trend-chart-skeleton'>
              <ChartSkeleton type='bar' height={dynamicHeight.value} length={40} />
            </div>
          )}
          {showEmpty.value ? (
            <div
              style={{ height: `${dynamicHeight.value}px` }}
              class='trend-chart-empty'
            >
              <svg
                width='64'
                height='48'
                viewBox='0 0 64 48'
                aria-hidden='true'
              >
                <rect x='8' y='6' width='28' height='34' rx='2' fill='#f5f7fa' stroke='#dcdee5' />
                <path d='M14 16h16M14 22h12M14 28h14' stroke='#c4c6cc' stroke-linecap='round' />
                <circle cx='42' cy='30' r='8' fill='none' stroke='#979ba5' stroke-width='2' />
                <path d='M48 36l6 6' stroke='#979ba5' stroke-width='2' stroke-linecap='round' />
              </svg>
              <span>检索无数据</span>
            </div>
          ) : (
            <div
              ref={trendChartCanvas}
              style={{ height: `${dynamicHeight.value}px` }}
            />
          )}
        </div>
      </div>
    );
  },
});
