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
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { computed, defineComponent, onBeforeUnmount, onMounted, ref, watch, nextTick, type PropType } from 'vue';
import * as echarts from 'echarts';
import dayjs from 'dayjs';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';
import TimeRange, { type TimeRangeType } from '@/components/time-range/time-range';
import $http, { axiosInstance } from '@/api';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { blobDownload } from '@/common/util';
import { getConditionRouterParams } from '../utils';
import { type ClusteringConfigData } from '../index';
import './index.scss';

export default defineComponent({
  name: 'PatternAnalysisSlider',
  props: {
    requestData: {
      type: Object,
      require: true,
    },
    isShow: {
      type: Boolean,
      default: false,
    },
    indexSetId: {
      type: String,
      default: '',
    },
    markIndex: {
      type: Number,
      default: null,
    },
    markText: {
      type: String,
      default: '',
    },
    rowData: {
      type: Object as PropType<any>,
      default: () => null,
    },
    clusteringConfigData: {
      type: Object as PropType<ClusteringConfigData | null>,
      default: null,
    },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();
    const retrieveParams = computed(() => store.getters.retrieveParams);
    // 直接从 state.indexItem 获取 datePickerValue
    const datePickerValue = computed(() => store.state.indexItem.datePickerValue);
    const searchValue = ref('');
    const sortValue = ref('count_desc');
    const timeRange = ref<TimeRangeType>(['now-1d', 'now']);
    // 标记用户是否手动修改了弹窗内的时间选择器
    const isTimeRangeManualChanged = ref(false);

    // 值分布统计数据
    const statsData = ref<{
      uniqueValueCount: number | string;
      totalCount: number | string;
    }>({
      uniqueValueCount: '--',
      totalCount: '--',
    });

    // 将分组的数组改成对像，以 group 数组为主
    const getGroupsValue = (group: string[]) => {
      // 如果 group 是空的，返回空对象，不传递分组信息
      if (!group?.length) return {};
      if (!props.requestData?.group_by?.length) return {};

      const result: Record<string, string> = {};
      // 遍历 group 数组，根据索引从 group_by 取字段名
      group.forEach((value, index) => {
        const key = props.requestData?.group_by[index];
        if (key) {
          result[key] = value;
        }
      });
      return result;
    };

    // loading 状态
    const distributionLoading = ref(false);
    const trendLoading = ref(false);
    const samplesLoading = ref(false);

    // 构建公共请求参数
    const getBaseParams = () => {
      const { signature, origin_pattern, pattern, group } = props.rowData;
      const { addition, keyword, start_time, end_time } = retrieveParams.value;
      const { pattern_level } = props.requestData;
      const mergeGroup = getGroupsValue(group);

      // 初始化时使用 retrieveParams 的精确时间戳，用户手动修改时间选择器后使用 timeRange 转换
      let startTime = start_time;
      let endTime = end_time;
      if (isTimeRangeManualChanged.value) {
        [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      }

      return {
        signature,
        addition,
        keyword,
        pattern_level,
        pattern: origin_pattern || pattern,
        placeholder_index: props.markIndex,
        start_time: startTime,
        end_time: endTime,
        groups: mergeGroup,
        value_keyword: searchValue.value,
        sort: sortValue.value,
      };
    };

    // 公共前置校验
    const canRequest = () => {
      return props.rowData?.signature && props.markIndex !== null && props.indexSetId;
    };

    // 获取占位符分布数据
    const fetchPlaceholderDistribution = async () => {
      if (!canRequest()) return;

      const params = getBaseParams();

      distributionLoading.value = true;
      try {
        // 使用 placeholderDistribution 对象，:index_set_id 会被 params.index_set_id 替换
        const res = await $http.request('logClustering/placeholderDistribution/', {
          params: { index_set_id: props.indexSetId },
          data: params,
        });

        // 更新统计数据
        if (res.data) {
          statsData.value = {
            uniqueValueCount: res.data.unique_count ?? '--',
            totalCount: res.data.total_count ?? '--',
          };
          // 更新值分布列表
          valueDistributionList.value = res.data.values || [];

          // 默认选中第一条，并获取趋势数据和样本数据
          if (res.data.values?.length) {
            selectedValue.value = res.data.values[0].value;
            fetchPlaceholderTrend(res.data.values[0].value);
            fetchPlaceholderSamples(res.data.values[0].value);
          }
        }
      } catch (err) {
        console.error('获取占位符分布数据失败:', err);
      } finally {
        distributionLoading.value = false;
      }
    };

    watch(
      [() => props.rowData, () => props.markIndex, () => props.isShow],
      ([newRowData, newMarkIndex, newIsShow]) => {
        // 仅在侧边栏打开且有有效数据时才请求
        if (!newIsShow || !newRowData) return;

        // 切换 mark 时，重置所有旧数据，确保接口重新请求
        selectedValue.value = '';
        trendData.value = null;
        sampleList.value = [];
        valueDistributionList.value = [];
        statsData.value = { uniqueValueCount: '--', totalCount: '--' };

        // 销毁旧的图表实例，切换时重新初始化
        trendChartInstance.value?.dispose();
        trendChartInstance.value = null;

        // 初始化 timeRange 从 datePickerValue 获取（相对时间格式），重置手动修改标记
        isTimeRangeManualChanged.value = false;
        if (datePickerValue.value && Array.isArray(datePickerValue.value)) {
          timeRange.value = datePickerValue.value as TimeRangeType;
        }

        // 获取占位符分布数据
        fetchPlaceholderDistribution();
      },
      { immediate: true },
    );

    const handleTimeRangeChange = (val: TimeRangeType) => {
      timeRange.value = val;
      isTimeRangeManualChanged.value = true;
    };

    // 重新请求分布数据的公共逻辑
    const refreshDistribution = () => {
      if (!props.isShow || !props.rowData) return;
      selectedValue.value = '';
      trendData.value = null;
      sampleList.value = [];

      trendChartInstance.value?.dispose();
      trendChartInstance.value = null;

      fetchPlaceholderDistribution();
    };

    // 搜索防抖处理（300ms）
    let searchTimer: ReturnType<typeof setTimeout> | null = null;
    watch(searchValue, () => {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        refreshDistribution();
      }, 300);
    });

    // 排序、时间范围变化时立即重新请求数据
    watch([sortValue, timeRange], () => {
      refreshDistribution();
    });

    // 模拟值分布表数据
    const valueDistributionList = ref<{ value: string; count: number; percentage: number }[]>([]);

    // 当前选中的值
    const selectedValue = ref('');

    // 趋势数据
    const trendData = ref<any>(null);

    // ECharts 实例相关
    const trendChartRef = ref<HTMLElement | null>(null);
    const trendChartInstance = ref<echarts.ECharts | null>(null);

    // 初始化 ECharts 图表
    const initTrendChart = () => {
      if (!trendChartRef.value) return;
      trendChartInstance.value?.dispose();
      trendChartInstance.value = echarts.init(trendChartRef.value);
    };

    // 更新 ECharts 折线图
    const updateTrendChart = () => {
      if (!trendChartInstance.value || !trendData.value) return;

      const { overall = [], selected = [], interval } = trendData.value;

      // 合并所有时间点并去重排序
      const allTimes = new Set<number>();
      overall.forEach((item: any) => allTimes.add(item.time));
      selected.forEach((item: any) => allTimes.add(item.time));
      const sortedTimes = Array.from(allTimes).sort((a, b) => a - b);

      // 构建 overall 数据（时间轴格式 [timestamp, value]）
      const overallMap = new Map<number, number>();
      overall.forEach((item: any) => overallMap.set(item.time, item.count));
      const overallData = sortedTimes.map(time => [time, overallMap.get(time) ?? null]);

      // 构建 selected 数据（时间轴格式 [timestamp, value]）
      const selectedData = selected.map((item: any) => [item.time, item.count]);

      trendChartInstance.value.setOption({
        animation: false,
        grid: {
          top: 20,
          right: 20,
          bottom: 30,
          left: 10,
          containLabel: true,
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: '#fff',
          borderColor: '#dcdee5',
          borderWidth: 1,
          textStyle: {
            color: '#63656e',
            fontSize: 12,
          },
          formatter: (params: any) => {
            let html = '';
            params.forEach((p: any) => {
              if (p.value !== null && p.value !== undefined) {
                const val = p.value[1];
                html += `<div style="display:flex;align-items:center;gap:4px;">
                  <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};"></span>
                  <span>${p.seriesName}: ${val}</span>
                </div>`;
              }
            });
            return html;
          },
        },
        legend: {
          bottom: 0,
          icon: 'circle',
          itemWidth: 10,
          itemHeight: 10,
          textStyle: {
            color: '#63656e',
            fontSize: 12,
          },
        },
        xAxis: {
          type: 'time',
          axisTick: { show: false },
          axisLabel: {
            color: '#979BA5',
            fontSize: 11,
            formatter: (val: number) => {
              if (interval === '1d') return dayjs(val).format('MM-DD');
              if (interval === '1h' || interval === '1H') return dayjs(val).format('MM-DD HH:mm');
              return dayjs(val).format('HH:mm');
            },
          },
          axisLine: {
            lineStyle: {
              color: '#F0F1F5',
            },
          },
          splitLine: { show: false },
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            color: '#979BA5',
            fontSize: 11,
          },
          splitLine: {
            lineStyle: {
              color: '#F0F1F5',
              type: 'dashed',
            },
          },
        },
        series: [
          {
            name: selectedValue.value || t('选中值'),
            type: 'line',
            smooth: false,
            symbol: 'circle',
            symbolSize: 8,
            lineStyle: { color: '#3a84ff', width: 1 },
            itemStyle: {
              color: '#3a84ff',
              borderColor: '#fff',
              borderWidth: 1,
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(58,132,255,0.3)' },
                { offset: 1, color: 'rgba(58,132,255,0.05)' },
              ]),
            },
            data: selectedData,
          },
          {
            name: t('整体'),
            type: 'line',
            smooth: false,
            symbol: 'circle',
            symbolSize: 8,
            lineStyle: { color: '#00c873', width: 1 },
            itemStyle: {
              color: '#00c873',
              borderColor: '#fff',
              borderWidth: 1,
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(0,200,115,0.3)' },
                { offset: 1, color: 'rgba(0,200,115,0.05)' },
              ]),
            },
            data: overallData,
          },
        ],
      });
    };

    // 监听 trendData 变化，更新图表
    watch(trendData, () => {
      nextTick(() => {
        if (!trendChartInstance.value) {
          initTrendChart();
        }
        updateTrendChart();
      });
    });

    // 组件销毁前清理 ECharts 实例
    onBeforeUnmount(() => {
      trendChartInstance.value?.dispose();
      trendChartInstance.value = null;
      if (searchTimer) clearTimeout(searchTimer);
    });

    // 获取占位符趋势数据
    const fetchPlaceholderTrend = async (value: string) => {
      if (!canRequest()) return;

      const params = { ...getBaseParams(), value };

      trendLoading.value = true;
      try {
        const res = await $http.request('logClustering/placeholderTrend', {
          params: { index_set_id: props.indexSetId },
          data: params,
        });
        if (res.data) {
          trendData.value = res.data;
        }
      } catch (err) {
        console.error('获取占位符趋势数据失败:', err);
      } finally {
        trendLoading.value = false;
      }
    };

    // 获取占位符相关样本
    const fetchPlaceholderSamples = async (value: string) => {
      if (!canRequest()) return;

      const params = { ...getBaseParams(), value, limit: 5 };

      samplesLoading.value = true;
      try {
        const res = await $http.request('logClustering/placeholderSamples', {
          params: { index_set_id: props.indexSetId },
          data: params,
        });
        if (res.data) {
          sampleList.value = res.data.samples || [];
        }
      } catch (err) {
        console.error('获取占位符相关样本数据失败:', err);
      } finally {
        samplesLoading.value = false;
      }
    };

    // 选中值分布表某行
    const handleValueClick = (item: { value: string; count: number; percentage: number }) => {
      selectedValue.value = item.value;
      fetchPlaceholderTrend(item.value);
      fetchPlaceholderSamples(item.value);
    };

    // 模拟相关样本数据
    const sampleList = ref([]);

    const handleBeforeClose = () => {
      // 关闭弹窗时清除搜索和筛选条件，确保下次打开是初始状态
      searchValue.value = '';
      sortValue.value = 'count_desc';
      isTimeRangeManualChanged.value = false;
      if (datePickerValue.value && Array.isArray(datePickerValue.value)) {
        timeRange.value = datePickerValue.value as TimeRangeType;
      } else {
        timeRange.value = ['now-1d', 'now'];
      }

      emit('close');
      return true;
    };

    const exportLoading = ref(false);

    const handleViewOriginalLog = async () => {
      if (!canRequest()) return;

      const params = getBaseParams();
      const downRequestUrl = `/pattern/${props.indexSetId}/placeholder_export/`;

      exportLoading.value = true;
      try {
        const res = await axiosInstance.post(downRequestUrl, params);
        if (typeof res !== 'string') {
          console.error('导出失败');
          return;
        }
        const fileName = `pattern标签分析_值分布表_${props.indexSetId}_${dayjs().format('YYYY-MM-DD HH:mm:ss')}.csv`;
        blobDownload(res, fileName, 'text/csv');
      } catch (error) {
        console.error('导出失败:', error);
      } finally {
        exportLoading.value = false;
      }
    };

    // 跳转到日志检索（新开 Tab），实现与 handleMenuBatchClick 相同的跳转逻辑
    const handleJumpToRetrieve = (item: { value: string; count: number; percentage: number }) => {
      const params: any = getBaseParams();
      const { signature, group } = params;
      const { pattern_level } = props.requestData;

      // 构建 additionList，与 handleMenuBatchClick 逻辑一致
      const additionList = [];

      // 添加分组条件
      if (group && Object.keys(group).length) {
        Object.entries(group).forEach(([field, value]) => {
          additionList.push({
            field,
            operator: 'is',
            value,
            isLink: true,
          });
        });
      }

      // 添加聚类签名条件
      if (signature) {
        additionList.push({
          field: `__dist_${pattern_level}`,
          operator: 'is',
          value: signature.toString(),
          isLink: true,
        });
      }

      // 添加选中值的精确匹配条件
      additionList.push({
        field: props.clusteringConfigData?.clustering_fields || '',
        operator: 'is',
        value: item.value,
        isLink: true,
      });

      // 强制使用 UI 模式
      store.commit('updateIndexItem', { search_mode: 'ui' });
      store.commit('updateState', { key: 'clusterParams', value: null });

      store.dispatch('setQueryCondition', additionList).then(([newSearchList, searchMode, isNewSearchPage]) => {
        // 构建跳转 URL 的附加参数，包含 tab 和时间参数
        // URL 中的 start_time/end_time 存储的是 datePickerValue 格式的字符串（如 "2026-04-24 14:34:46" 或 "now-1d"）
        // 而不是数字时间戳，因此这里需要传 timeRange.value 而非 getBaseParams 返回的时间戳
        const appendParams: Record<string, any> = { tab: 'origin' };
        if (isTimeRangeManualChanged.value && timeRange.value?.length === 2) {
          appendParams.start_time = timeRange.value[0];
          appendParams.end_time = timeRange.value[1];
        }

        const openUrl = getConditionRouterParams(newSearchList, searchMode, isNewSearchPage, appendParams);
        window.open(openUrl, '_blank');
        // 回填当前页面聚类参数
        store.commit('updateState', {
          key: 'clusterParams',
          value: props.requestData,
        });
      });
    };

    return () => (
      <bk-sideslider
        is-show={props.isShow}
        width={960}
        ext-cls='pattern-analysis-slider'
        before-close={handleBeforeClose}
        quick-close={true}
      >
        <div
          slot='header'
          class='slider-header'
        >
          <span class='slider-title'>{t('Pattern 标签分析')}</span>
          <span class='slider-line'></span>
          <span class='tag-label'>{props.markText}</span>
        </div>
        <div
          slot='content'
          class='pattern-analysis-content'
        >
          {/* 统计卡片 */}
          <div class='stats-cards'>
            <div class='stat-card'>
              <div class='stat-icon'>
                <span>&lt;1&gt;</span>
              </div>
              <div class='stat-info'>
                <div class='stat-label'>{t('唯一值数量')}</div>
                <div
                  class='stat-value'
                  v-bkloading={{ isLoading: distributionLoading.value }}
                >
                  {statsData.value.uniqueValueCount}
                </div>
              </div>
            </div>
            <div class='stat-card'>
              <div class='stat-icon all'>
                <span>all</span>
              </div>
              <div class='stat-info'>
                <div class='stat-label'>{t('总出现次数')}</div>
                <div
                  class='stat-value'
                  v-bkloading={{ isLoading: distributionLoading.value }}
                >
                  {statsData.value.totalCount}
                </div>
              </div>
            </div>
          </div>

          {/* 搜索和筛选栏 */}
          <div class='filter-bar'>
            <bk-input
              value={searchValue.value}
              placeholder={t('搜索 值')}
              right-icon='bk-icon icon-search'
              on-change={val => (searchValue.value = val)}
            />
            <div class='filter-actions'>
              <bk-select
                value={sortValue.value}
                style='background: white;'
                on-change={val => (sortValue.value = val)}
              >
                <bk-option
                  id='count_desc'
                  name={t('出现次数 - 降序')}
                />
                <bk-option
                  disabled={true}
                  id='count_asc'
                  name={t('出现次数 - 升序')}
                />
              </bk-select>
              <TimeRange
                style='background: white;'
                value={timeRange.value}
                needTimezone={false}
                onChange={handleTimeRangeChange}
                type='normal'
              />
              <bk-button
                theme='primary'
                outline
                onClick={handleViewOriginalLog}
              >
                {t('下载')}
              </bk-button>
            </div>
          </div>

          {/* 主内容区域 */}
          <div class='main-content'>
            {/* 左侧：值分布表 */}
            <div class='distribution-section'>
              <div class='section-title'>
                {t('值分布表')}
                <span class='count-badge'>{valueDistributionList.value.length}</span>
              </div>
              <div class='distribution-table'>
                <div class='table-header'>
                  <div class='col-index'>#</div>
                  <div
                    class='col-value'
                    style={{ paddingLeft: '16px' }}
                  >
                    {t('值')}
                  </div>
                  <div class='col-count'>{t('出现次数 & 占比')}</div>
                </div>
                <div
                  class='table-body'
                  v-bkloading={{ isLoading: distributionLoading.value }}
                >
                  {valueDistributionList.value.length > 0
                    ? valueDistributionList.value.map((item, index) => (
                        <div
                          class={`table-row ${selectedValue.value === item.value ? 'active' : ''}`}
                          key={index}
                          onClick={() => handleValueClick(item)}
                        >
                          <div class='col-index'>{index + 1}</div>
                          <div class='col-value'>
                            <i
                              class='bklog-icon bklog-jump hover-icon'
                              onClick={e => {
                                e.stopPropagation();
                                handleJumpToRetrieve(item);
                              }}
                              v-bk-tooltips={{
                                placement: 'top',
                                content: t('前往日志检索'),
                                delay: 300,
                              }}
                            />
                            <i v-bk-overflow-tips>
                              <span
                                class='col-value-text'
                                onClick={() => handleValueClick(item)}
                              >
                                {item.value}
                              </span>
                            </i>
                          </div>
                          <div class='col-count'>
                            <div class='count-bar-wrapper'>
                              <div class='count-info'>
                                <span class='count-num'>{item.count}</span>
                                <span class='percentage'>{item.percentage.toFixed(2)}%</span>
                              </div>
                              <div class='progress-bar'>
                                <div
                                  class='progress-fill'
                                  style={{ width: `${item.percentage}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    : !distributionLoading.value && (
                        <bk-exception
                          class='exception-wrap-item exception-part'
                          scene='part'
                          style='margin-top: 240px;'
                          type='empty'
                        />
                      )}
                </div>
              </div>
            </div>

            {/* 右侧：趋势图和样本 */}
            <div class='right-section'>
              <div class='trend-section'>
                <div class='section-title'>
                  {t('整体趋势')}
                  {selectedValue.value && (
                    <span class='vs-text'>
                      <span class='vs-letter'>VS</span>
                      {selectedValue.value}
                    </span>
                  )}
                </div>
                <div
                  class='trend-chart-wrapper'
                  v-bkloading={{ isLoading: trendLoading.value }}
                >
                  {trendData.value ? (
                    <div class='trend-chart'>
                      <div
                        ref={trendChartRef}
                        style={{ width: '100%', height: '250px' }}
                      />
                    </div>
                  ) : (
                    !trendLoading.value && (
                      <bk-exception
                        class='exception-wrap-item exception-part'
                        scene='part'
                        style='margin-top: 60px;'
                        type='empty'
                      />
                    )
                  )}
                </div>
              </div>

              <div class='sample-section'>
                <div class='section-title'>
                  {selectedValue.value} {t('相关样本')}
                </div>
                <div
                  class='sample-list'
                  v-bkloading={{ isLoading: samplesLoading.value }}
                >
                  {sampleList.value.length > 0
                    ? sampleList.value.map(sample => (
                        <div
                          class='sample-item'
                          key={sample.id}
                        >
                          <div class='sample-time'>{sample.dteventtime}</div>
                          <div class='sample-content'>{sample.log}</div>
                        </div>
                      ))
                    : !samplesLoading.value && (
                        <bk-exception
                          class='exception-wrap-item exception-part'
                          scene='part'
                          style='margin-top: 80px;margin-bottom: 80px'
                          type='empty'
                        />
                      )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </bk-sideslider>
    );
  },
});
