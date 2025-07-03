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
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';
import useLocale from '@/hooks/use-locale';
import { formatNumberWithRegex } from '../../../common/util';
import BklogPopover from '@/components/bklog-popover';
import GradeOption from '@/components/monitor-echarts/components/grade-option';
import RetrieveHelper, { RetrieveEvent } from '@/views/retrieve-helper';
import http from '@/api';
import axios from 'axios';
import useTrendChart from '@/hooks/use-trend-chart';
import { getCommonFilterAddition } from '@/store/helper';
import './index-new.scss';

export default defineComponent({
  name: 'SearchResultChart',
  emits: ['toggle-change'],
  setup(props, { emit }) {
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
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const unionIndexList = computed(() => store.getters.unionIndexList);
    const gradeOptions = computed(() => store.state.indexFieldInfo.custom_config?.grade_options);

    const CancelToken = axios.CancelToken;

    let finishPolling = ref(false);  // 是否完成轮询
    let isStart = ref(false);  // 是否开始轮询
    let requestInterval = 0;  // 轮询间隔
    let pollingEndTime = 0;  // 当前轮询结束时间
    let pollingStartTime = 0;  // 当前轮询开始时间
    let logChartCancel: any = null;  // 取消请求的方法
    let runningInterval = 'auto';  // 当前实际使用的 interval
    let isInit = true;  // 是否为首次请求
    let sumCount = 0;  // 累计总数
    let runningTimer: any = null;  // 定时器

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
    const totalCount = computed(() => {
      if (store.state.searchTotal > 0) {
        return store.state.searchTotal;
      }
      return store.state.retrieve.trendDataCount;
    });
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
      localStorage.setItem('chartIsFold', JSON.stringify(val));
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
      setTimeout(() => {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);  // 触发趋势图刷新
      });
    };

    // 初始化、设置、重绘图表
    const handleChartDataZoom = inject('handleChartDataZoom', () => {});
    const { initChartData, setChartData } = useTrendChart({
      target: trendChartCanvas,
      handleChartDataZoom,
      dynamicHeight,
    });

    // 根据时间范围决定是否分段请求
    const handleRequestSplit = (startTime, endTime) => {
      const duration = (endTime - startTime) / 3600000;
      if (duration <= 6) return 0;
      if (duration < 48) return 21600 * 1000;
      return (86400 * 1000) / 2;
    };

    // 拉取趋势图数据（支持分段轮询）
    const getSeriesData = (startTimeStamp, endTimeStamp) => {
      if (finishPolling.value) return;
      requestInterval = isStart.value ? requestInterval : handleRequestSplit(startTimeStamp, endTimeStamp);

      if (!isStart.value) {
        // 首次请求，初始化状态
        isInit = true;
        sumCount = 0;
        pollingEndTime = endTimeStamp;
        pollingStartTime = requestInterval > 0 ? pollingEndTime - requestInterval : startTimeStamp;
        isStart.value = true;
        store.commit('retrieve/updateTrendDataLoading', true);
        store.commit('retrieve/updateTrendDataCount', 0);
        const { interval } = initChartData();
        runningInterval = interval;
      } else {
        // 后续请求，向前推进时间窗口
        pollingEndTime = pollingStartTime;
        pollingStartTime = pollingStartTime - requestInterval;
      }

      // 轮询边界判断
      if (pollingStartTime < startTimeStamp) {
        pollingStartTime = startTimeStamp;
        finishPolling.value = true;
        store.commit('retrieve/updateTrendDataLoading', false);
      }

      if (pollingStartTime < retrieveParams.value.start_time) {
        pollingStartTime = retrieveParams.value.start_time;
      }

      if (pollingStartTime > pollingEndTime) {
        finishPolling.value = true;
        isStart.value = false;
        store.commit('retrieve/updateTrendDataLoading', false);
        return;
      }

      // 组装请求参数
      const indexId = window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId;
      if ((!isUnionSearch.value && !!indexId) || (isUnionSearch.value && unionIndexList.value?.length)) {
        const urlStr = isUnionSearch.value ? 'unionSearch/unionDateHistogram' : 'retrieve/getLogChartList';
        const queryData = {
          ...retrieveParams.value,
          addition: [...retrieveParams.value.addition, ...getCommonFilterAddition(store.state)],
          time_range: 'customized',
          interval: runningInterval,
          start_time: pollingStartTime,
          end_time: pollingEndTime,
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

        // 发起请求
        http
          .request(
            urlStr,
            {
              params: { index_set_id: indexId },
              data: queryData,
            },
            {
              cancelToken: new CancelToken(c => {
                logChartCancel = c;
              }),
            },
          )
          .then(res => {
            if (res?.data) {
              sumCount += setChartData(res?.data?.aggs, queryData.group_field, isInit);
              isInit = false;
              store.commit('retrieve/updateTrendDataCount', sumCount);
            }
            if (!res?.result || requestInterval === 0) {
              isStart.value = false;
              finishPolling.value = true;
              store.commit('retrieve/updateTrendDataLoading', false);
              return;
            }
            if (!finishPolling.value && requestInterval > 0) {
              getSeriesData(startTimeStamp, endTimeStamp);
              return;
            }
          })
          .catch(() => {
            isStart.value = false;
            finishPolling.value = true;
            store.commit('retrieve/updateTrendDataLoading', false);
          });
      } else {
        isStart.value = false;
        finishPolling.value = true;
        store.commit('retrieve/updateTrendDataLoading', false);
      }
    };

    // 加载趋势图数据
    const loadTrendData = () => {
      logChartCancel?.();  // 取消上一次未完成的趋势图请求
      setChartData(null, null, true);  // 清空图表数据, 重置为初始状态

      runningTimer && clearTimeout(runningTimer);
      runningTimer = setTimeout(() => {
        finishPolling.value = false;
        isStart.value = false;
        getSeriesData(retrieveParams.value.start_time, retrieveParams.value.end_time);  // 开始拉取新一轮趋势数据
      });
    };

    onMounted(() => {
      // 初始化折叠状态
      isFold.value = JSON.parse(localStorage.getItem('chartIsFold') || 'false');
      nextTick(() => {
        emit('toggle-change', !isFold.value, getOffsetHeight());
      });

      // 挂载时自动拉去数据，避免热重载时数据丢失
      loadTrendData();

      // 监听检索相关事件，自动刷新趋势图
      RetrieveHelper.on(
        [
          RetrieveEvent.SEARCH_VALUE_CHANGE,
          RetrieveEvent.SEARCH_TIME_CHANGE,
          RetrieveEvent.TREND_GRAPH_SEARCH,
          RetrieveEvent.FAVORITE_ACTIVE_CHANGE,
          RetrieveEvent.INDEX_SET_ID_CHANGE,
        ],
        loadTrendData,
      );
    });

    onBeforeUnmount(() => {
      // 组件卸载时清理定时器和事件监听
      finishPolling.value = true;
      runningTimer && clearTimeout(runningTimer);
      logChartCancel?.();
      RetrieveHelper.off(RetrieveEvent.TREND_GRAPH_SEARCH, loadTrendData);
      RetrieveHelper.off(RetrieveEvent.SEARCH_VALUE_CHANGE, loadTrendData);
      RetrieveHelper.off(RetrieveEvent.SEARCH_TIME_CHANGE, loadTrendData);
      RetrieveHelper.off(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, loadTrendData);
      RetrieveHelper.off(RetrieveEvent.INDEX_SET_ID_CHANGE, loadTrendData);
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
                <span class={['bk-icon', 'icon-down-shape', { 'is-flip': isFold.value }]}></span>
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
                  <span>{t('汇聚周期')} : </span> 
                  <bk-select
                    ext-cls='select-custom'
                    value={chartInterval.value}
                    clearable={false}
                    popover-width={70}
                    behavior='simplicity'
                    data-test-id='generalTrendEcharts_div_selectCycle'
                    size='small'
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
                    content-class='bklog-v3-grade-setting'
                    ref={refGradePopover}
                    options={tippyOptions as any}
                    beforeHide={beforePopoverHide}
                    content={() => (
                      <GradeOption
                        ref={refGradeOption}
                        on-Change={handleGradeOptionChange}
                      />
                    )}
                  >
                    <span class='bklog-icon bklog-shezhi'></span>
                  </BklogPopover>
                </div>
              )}
            </div>
            {/* 副标题 */}
            {subtitle.value && <div class='sub-title'>{subtitle.value}</div>}
          </div>
      )
    }

    // 渲染主入口
    return () => (
      <div
        ref={chartContainer}
        class={['monitor-echarts-container', { 'is-fold': isFold.value }]}
        data-test-id='retrieve_div_generalTrendEcharts'
      >
        {/* 标题部分 */}
        <div class='title-wrapper-new'>
          {/* 1. 标题内容 */}
          { chartTitleContent() }
          {/* 2. 加载中动画 */}
          {loading.value && !isFold.value && <bk-spin class='chart-spin'></bk-spin>}
        </div>
        {/* 图表部分 */}
        <div v-show={!isFold.value} class='monitor-echart-wrap' v-bkloading={{ isLoading: loading.value, zIndex: 10, size: 'mini' }}>
            <div
              ref={trendChartCanvas}
              style={{ height: `${dynamicHeight.value}px` }}>
            </div>
        </div>
      </div>
    );
  },
});
