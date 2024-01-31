/* eslint-disable max-len */
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
import { computed, ComputedRef, defineComponent, inject, PropType, reactive, Ref, ref, watch } from 'vue';
import { TranslateResult, useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';
import { Alert, Button, Exception, Input, Popover, Select, Table } from 'bkui-vue';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import type { EChartOption } from 'echarts';
import { toPng } from 'html-to-image';

// 原先绑定 Vue 原型的 $api
import api from '../../../../monitor-api/api';
// TODO：需要重新实现
// import CommonTable from '../../../../monitor-pc/pages/monitor-k8s/components/common-table';
// TODO：这个是父组件，需要将相关代码和mixins部分 copy 过来这里
// import { CommonSimpleChart } from '../../common-simple-chart';
import { debounce } from '../../../../monitor-common/utils/utils';
import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
import { ITableColumn } from '../../../../monitor-pc/pages/monitor-k8s/typings';
// import { MONITOR_BAR_OPTIONS } from '../../constants';
import { MONITOR_BAR_OPTIONS } from '../../../../monitor-ui/chart-plugins/constants';
// 原有类型
// import { PanelModel } from '../../typings';
import { IViewOptions, PanelModel } from '../../../../monitor-ui/chart-plugins/typings';
// src/monitor-ui/chart-plugins/utils/index.ts
import { downFile } from '../../../../monitor-ui/chart-plugins/utils';
// import { VariablesService } from '../../utils/variable';
import { VariablesService } from '../../../utils';
// import BaseEchart from '../monitor-base-echart';
import BaseEchart from '../../base-echart';
// mixins 转 hooks 相关
import {
  useChartIntersection,
  useRefleshImmediateInject,
  useRefleshIntervalInject,
  useTimeRanceInject
} from '../../hooks';
import { ITableDataItem } from '../../typings/table-chart';

import './related-log-chart.scss';
import 'vue-json-pretty/lib/styles.css';

const option: EChartOption = {
  animation: false,
  color: ['#A3C5FD'],
  xAxis: {
    show: true,
    type: 'time'
  },
  yAxis: {
    type: 'value',
    splitLine: {
      show: true,
      lineStyle: {
        color: '#F0F1F5',
        type: 'solid'
      }
    }
  },
  series: []
};

export default defineComponent({
  name: 'RelatedLogChartMigrated',
  props: {
    // 以下是继承自 common-simple-chart 的属性
    panel: { required: true, type: Object as PropType<PanelModel> },
    // 结束

    // 继承自 ErrorMsgMixins
    clearErrorMsg: { default: () => {}, type: Function }
    // 结束
  },
  emits: ['loading', 'errorMsg'],
  setup(props, { emit }) {
    const { t } = useI18n();
    // 标签引用
    const baseChart = ref<HTMLDivElement>();
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const RelatedLogChartRef = ref<HTMLDivElement>();

    const empty = ref(true);
    const emptyText = ref(t('加载中...'));
    const emptyChart = ref(false);
    /** 关联是否为蓝鲸日志平台 */
    const isBkLog = ref(true);
    /** alert提示文字 */
    const alertText = ref<string | TranslateResult>('');
    /** 第三方日志 */
    const thirdPartyLog = ref('');
    /** 搜索关键字 */
    const keyword = ref('');
    /** 关联蓝鲸日志的业务ID */
    const relatedBkBizId = ref(-1);
    /** 关联蓝鲸日志的索引集ID */
    const relatedIndexSetId = ref(-1);
    /** 关联索引集列表 */
    const relatedIndexSetList = ref([]);
    /** 柱状图配置 */
    const customOptions = ref<EChartOption>(
      deepmerge(MONITOR_BAR_OPTIONS, option, {
        arrayMerge: (_, srcArr) => srcArr
      })
    );
    /** 汇聚周期 */
    const chartInterval = ref<number | 'auto'>('auto');
    /** 汇聚周期选项 */
    const intervalList = ref([
      { id: 'auto', name: 'auto' },
      { id: '1m', name: '1m' },
      { id: '15m', name: '5m' },
      { id: '1h', name: '1h' },
      { id: '1d', name: '1d' }
    ]);
    /** 表格数据 */
    const tableData = ref<ITableDataItem[]>([]);
    /** 表格列数据 */
    const columns = ref<ITableColumn[]>([]);
    const pagination = reactive({
      value: 1,
      count: 0,
      limit: 20
    });

    // 以下是继承自 common-simple-chart 的属性
    /** 高度 */
    const height = ref(100);
    /** 宽度度 */
    const width = ref(300);
    /** 自动刷新定时任务 */
    let refleshIntervalInstance = null;
    /** 是否配置初始化 */
    const inited = ref(false);
    // 顶层注入数据
    const timeRange = useTimeRanceInject();
    const refleshInterval = useRefleshIntervalInject();
    /** 是否滚动到底部，用作判断加载完table数据后是否需要清空table数据还是添加数据 */
    let isScrollLoadTableData = false;
    // 在 Span-Detail 里 provide appName与serviceName。
    const appName = inject<ComputedRef<string>>('appName');
    const serviceName = inject<Ref<string>>('serviceName');
    // const viewOptions = useViewOptionsInject();
    // 这里强行凑一个 viewOptions
    const viewOptions = ref<Record<string, any>>({
      service_name: serviceName.value,
      app_name: appName.value,
      category: 'http',
      kind: 'service',
      predicate_value: 'POST',
      compare_targets: [],
      current_target: {},
      method: 'AVG',
      interval: 'auto',
      group_by: [],
      filters: {
        service_name: serviceName,
        app_name: appName,
        category: 'http',
        kind: 'service',
        predicate_value: 'POST'
      }
    });

    const refleshImmediate = useRefleshImmediateInject();
    // 好像用不着
    // @InjectReactive('queryData') readonly queryData!: IQueryData;
    /** 更新queryData */
    // 好像用不着
    // @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;
    // 当前使用的业务id
    // 好像用不着
    // @InjectReactive('bkBizId') readonly bkBizId: string | number;

    const scopedVars = computed(() => ({
      ...(viewOptions.value || {}),
      ...(viewOptions.value?.filters || {}),
      ...(viewOptions.value?.variables || {}),
      ...(viewOptions.value?.current_target || []),
      ...(viewOptions.value?.variables?.current_target || {}),
      ...{ current_target: viewOptions.value?.filters || {} }
    }));

    watch(viewOptions, (val: IViewOptions, old: IViewOptions) => {
      if (val && Object.keys(val).some(key => val[key] !== old?.[key])) {
        getPanelData();
      }
    });

    let formattedStartTime = 0;
    let formattedEndTime = 0;
    watch(timeRange, () => {
      getPanelData();
    });

    const setFormattedTime = () => {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value as [string, string]);
      formattedStartTime = startTime;
      formattedEndTime = endTime;
    };
    setFormattedTime();

    watch(refleshInterval, (v: number) => {
      if (refleshIntervalInstance) {
        window.clearInterval(refleshIntervalInstance);
      }
      if (v <= 0) return;
      refleshIntervalInstance = window.setInterval(() => {
        inited.value && getPanelData();
      }, refleshInterval.value);
    });

    watch(refleshImmediate, (v: boolean) => {
      if (v) getPanelData();
    });

    // 以上是继承自 common-simple-chart 的属性

    // 以下是使用自 common-simple-chart 的 mixins 部分。
    // IntersectionMixin 监听是否在可视窗口内
    const { unregisterOberver } = useChartIntersection(RelatedLogChartRef, async () => {
      getPanelData();
    });
    // ChartLoadingMixin 部分
    function handleLoadingChange(loading: boolean) {
      emit('loading', loading);
    }
    // ToolMixin 好像没有

    // ResizeMixin
    // 好像用不上
    // const { handleResize } = useChartResize(RelatedLogChartRef.value, baseChart.value, width.value, height.value);

    // LegendMixin 好像用不上

    // ErrorMsgMixins
    function handleErrorMsgChange(message: string) {
      emit('errorMsg', message);
    }

    // 以上是使用自 common-simple-chart 的 mixins 部分。

    /**
     * @description: 获取图表数据
     */
    const getPanelData = debounce(async (start_time?: string, end_time?: string) => {
      unregisterOberver();
      handleLoadingChange(true);
      emptyText.value = t('加载中...');
      keyword.value = props.panel.options?.related_log_chart?.defaultKeyword ?? keyword.value;
      // 先用 log_predicate 接口判断日志类型 蓝鲸日志平台 or 第三方其他日志
      const predicateLogTarget = props.panel.targets.find(item => item.dataType === 'log_predicate');
      if (predicateLogTarget) {
        const variablesService = new VariablesService({
          ...viewOptions.value
        });
        const params = variablesService.transformVariables(predicateLogTarget.data);
        api[predicateLogTarget.apiModule]
          [predicateLogTarget.apiFunc](params, { needMessage: false })
          .then(data => {
            if (data) {
              empty.value = false;
              relatedBkBizId.value = data.related_bk_biz_id;
              // 增加前置条件（索引集）列表获取
              const conditionTarget = props.panel.targets.find(item => item.dataType === 'condition');
              if (conditionTarget) {
                const payload = variablesService.transformVariables(conditionTarget.data);
                api[conditionTarget.apiModule]
                  [conditionTarget.apiFunc](payload, {
                    needMessage: false
                  })
                  .then(res => {
                    if (res.length) {
                      relatedIndexSetList.value = res;
                      const defaultIndexSet = res[0];
                      const { index_set_id: indexSetId } = defaultIndexSet;
                      relatedIndexSetId.value = indexSetId;
                      handleRealtionData(defaultIndexSet, start_time, end_time);
                    }
                  });
              }
            } else {
              empty.value = true;
              emptyText.value = '';
              handleLoadingChange(false);
            }
            props.clearErrorMsg();
          })
          .catch(error => {
            empty.value = true;
            handleErrorMsgChange(error.msg || error.message);
            emptyText.value = t('出错了');
            handleLoadingChange(false);
          });
      }
    }, 300);

    /** 处理关联信息展示 */
    const handleRealtionData = (info, start_time = '', end_time = '') => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { log_type: logType, index_set_id: indexSetId, related_bk_biz_id } = info;
      if (logType === 'bk_log') {
        relatedBkBizId.value = related_bk_biz_id;
        updateBarChartData(start_time, end_time);
        updateTableData(start_time, end_time);
        alertText.value = t('如果需要查看完整日志，可跳转日志检索进行查看');
      } else {
        alertText.value = t('关联了非蓝鲸日志平台的日志，只能进行日志的跳转');
        thirdPartyLog.value = indexSetId;
      }
    };

    /**
     * @desc 更新柱状图数据
     */
    const updateBarChartData = debounce(async (start_time?: string, end_time?: string) => {
      handleLoadingChange(true);
      try {
        unregisterOberver();
        const params = {
          start_time: start_time ? dayjs.tz(start_time).unix() : formattedStartTime,
          end_time: end_time ? dayjs.tz(end_time).unix() : formattedEndTime,
          interval: chartInterval.value,
          index_set_id: relatedIndexSetId.value,
          keyword: keyword.value
        };
        const variablesService = new VariablesService({
          ...scopedVars.value
        });
        await props.panel.targets
          .filter(item => item.dataType === 'time_series')
          .map(
            item =>
              api[item.apiModule]
                ?.[item.apiFunc](
                  {
                    ...variablesService.transformVariables(item.data),
                    ...params,
                    view_options: {
                      // 在继承组件
                      ...viewOptions.value
                    }
                  },
                  { needMessage: false }
                )
                .then(res => {
                  if (res.series?.[0].datapoints?.length) {
                    customOptions.value.series = [];
                    const data = {
                      series: [
                        {
                          data: res.series[0].datapoints,
                          type: 'bar',
                          colorBy: 'data',
                          name: 'COUNT ',
                          zlevel: 100
                        }
                      ]
                    };
                    const updateOption = deepmerge(option, data);
                    customOptions.value = deepmerge(customOptions.value, updateOption);
                    emptyChart.value = false;
                  } else {
                    emptyChart.value = true;
                  }
                })
          );
      } catch (error) {
        handleErrorMsgChange(error.msg || error.message);
      }
      props.clearErrorMsg();
      setTimeout(() => {
        handleLoadingChange(false);
      }, 100);
    }, 300);

    /**
     * @desc 更新表格数据
     */
    const isScrollLoading = ref(false);
    async function updateTableData(start_time?: string, end_time?: string) {
      isScrollLoading.value = true;
      handleLoadingChange(true);
      try {
        unregisterOberver();
        const params = {
          start_time: start_time || formattedStartTime,
          end_time: end_time || formattedEndTime,
          keyword: keyword.value,
          limit: pagination.limit,
          offset: (pagination.value - 1) * pagination.limit,
          index_set_id: relatedIndexSetId.value
        };
        const variablesService = new VariablesService({
          ...scopedVars.value
        });
        await props.panel.targets
          .filter(item => item.dataType === 'table-chart')
          .map(
            item =>
              api[item.apiModule]
                ?.[item.apiFunc]({
                  ...variablesService.transformVariables(item.data),
                  ...params,
                  view_options: {
                    ...viewOptions.value
                  }
                })
                .then(data => {
                  if (isScrollLoadTableData) {
                    tableData.value.push(...data.data);
                    isScrollLoadTableData = false;
                  } else {
                    tableData.value = data.data;
                  }
                  columns.value = data.columns;
                })
                .finally(() => {
                  isScrollLoading.value = false;
                })
          );
      } catch (e) {}
      setTimeout(() => {
        handleLoadingChange(false);
      }, 100);
    }

    /** 切换分页 */
    const handlePageChange = debounce(async () => {
      const temp = pagination.value;
      pagination.value += 1;
      isScrollLoadTableData = true;
      await updateTableData().catch(() => {
        pagination.value = temp;
      });
    }, 300);

    /* 每页个数切换 */
    async function handleLimitChange(limit: number) {
      const temp = pagination.limit;
      pagination.limit = limit;
      pagination.value = 1;
      await updateTableData().catch(() => {
        pagination.limit = temp;
      });
    }

    function dataZoom(startTime: string, endTime: string) {
      updateBarChartData(startTime, endTime);
    }

    function handleDblClick() {
      updateBarChartData();
    }

    /**
     * @desc 切换汇聚周期
     */
    function handleIntervalChange(v) {
      chartInterval.value = v;
      updateBarChartData();
    }

    /**
     * @description: 截图操作
     */
    function handleSavePng() {
      toPng(baseChart.value)
        .then(url => {
          downFile(url, `${t('总趋势')}.png`);
        })
        .catch(err => {
          console.log(err);
        });
    }

    const handleSearchChange = debounce((v: string) => {
      keyword.value = v;
      handleQueryTable();
    }, 300);

    /**
     * @desc 表格数据查询
     */
    const handleQueryTable = () => {
      pagination.value = 1;
      updateTableData();
    };

    /**
     * @desc 链接跳转
     */
    function goLink() {
      const url = isBkLog.value
        ? `${window.bk_log_search_url}#/retrieve/${relatedIndexSetId.value}?bizId=${relatedBkBizId.value}`
        : thirdPartyLog.value;
      window.open(url, '_blank');
    }

    /**
     * @desc 关联日志
     */
    function handleRelated() {
      const { app_name: appName, service_name: serviceName } = viewOptions.value as Record<string, string>;
      const hash = `#/apm/service-config?app_name=${appName}&service_name=${serviceName}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /** 选择索引集 */
    const handleSelectIndexSet = v => {
      const indexSetOption = relatedIndexSetList.value.find(item => item.index_set_id === v);
      if (indexSetOption) {
        handleRealtionData(indexSetOption);
      }
    };

    /**
     * columns 是原先用于 vue2 组件的，无法在 vue3 组件上继续使用，这里进行调整。
     */
    const transformedColumns = computed(() => {
      const result = columns.value.map(item => {
        const newColumn: Record<string, any> = {};
        newColumn.label = item.name;
        newColumn.field = item.id;
        newColumn.width = item.width;
        newColumn.minWidth = item.min_width;
        return newColumn;
      });
      // 需要留个位置做折叠 json 数据展示。
      result.unshift({
        width: 30,
        type: 'expand'
      });
      return result;
    });

    const selectedOptionAlias = computed(() => {
      const target = relatedIndexSetList.value.find(item => {
        // eslint-disable-next-line eqeqeq
        return item.index_set_id == relatedIndexSetId.value;
      });
      return target?.index_set_name ?? '';
    });

    return {
      empty,
      alertText,
      isBkLog,
      goLink,
      thirdPartyLog,
      emptyChart,
      chartInterval,
      intervalList,
      handleSavePng,
      width,
      height,
      customOptions,
      dataZoom,
      handleDblClick,
      keyword,
      handleSearchChange,
      emptyText,
      handleRelated,
      baseChart,
      RelatedLogChartRef,
      handleIntervalChange,
      tableData,
      columns,
      transformedColumns,
      handleLimitChange,
      handlePageChange,
      pagination,
      handleSelectIndexSet,
      relatedIndexSetList,
      relatedIndexSetId,
      isScrollLoading,
      selectedOptionAlias,
      handleQueryTable
    };
  },
  render() {
    return (
      <div
        class='related-log-chart-wrap'
        ref='RelatedLogChartRef'
      >
        {!this.empty ? (
          <div>
            <div class='related-alert-info'>
              <Alert
                show-icon={false}
                v-slots={{
                  title: () => (
                    <div>
                      <span class='alter-text'>{this.alertText}</span>
                      {this.isBkLog ? (
                        <span
                          class='link'
                          onClick={() => this.goLink()}
                        >
                          {this.$t('route-日志检索')}
                          <i class='icon-monitor icon-fenxiang'></i>
                        </span>
                      ) : (
                        <span
                          class='link'
                          onClick={() => this.goLink()}
                        >
                          <i class='icon-monitor icon-mc-target-link'></i>
                          <span>{this.thirdPartyLog}</span>
                        </span>
                      )}
                    </div>
                  )
                }}
              ></Alert>
            </div>
            {this.isBkLog && (
              <div class='related-log-chart-main'>
                <div class='log-chart-collapse'>
                  <div class='collapse-header'>
                    <span class='collapse-title'>
                      <span class='title'>{this.$t('总趋势')}</span>
                      {!this.emptyChart && (
                        <div class='title-tool'>
                          <span class='interval-label'>{this.$t('汇聚周期')}</span>

                          <Select
                            class='interval-select'
                            size='small'
                            behavior='simplicity'
                            clearable={false}
                            v-model={this.chartInterval}
                            onChange={this.handleIntervalChange}
                          >
                            {this.intervalList.map(item => (
                              <Select.Option
                                key={item.id}
                                value={item.name}
                              >
                                {item.name}
                              </Select.Option>
                            ))}
                          </Select>
                        </div>
                      )}
                    </span>
                    {!this.emptyChart && (
                      <Popover
                        placement='top'
                        content={this.$t('截图到本地')}
                      >
                        <i
                          class='icon-monitor icon-mc-camera'
                          onClick={() => this.handleSavePng()}
                        />
                      </Popover>
                    )}
                  </div>
                  <div class='collapse-content'>
                    <div class='monitor-echart-common-content'>
                      {!this.emptyChart ? (
                        <div
                          class='chart-instance'
                          ref='baseChart'
                        >
                          <BaseEchart
                            class='base-chart'
                            height={this.height}
                            width={this.width}
                            options={this.customOptions}
                            onDataZoom={this.dataZoom}
                            onDblClick={this.handleDblClick}
                          />
                        </div>
                      ) : (
                        <div class='empty-chart'>{this.$t('查无数据')}</div>
                      )}
                    </div>
                  </div>
                </div>
                <div class='query-tool'>
                  <Select
                    class='table-search-select'
                    v-model={this.relatedIndexSetId}
                    clearable={false}
                    onChange={v => this.handleSelectIndexSet(v)}
                    style='flex-shrink: 0;'
                  >
                    {this.relatedIndexSetList.map(option => (
                      <Select.Option
                        key={option.index_set_id}
                        id={option.index_set_id}
                        name={option.index_set_name}
                      ></Select.Option>
                    ))}
                  </Select>
                  <Input
                    class='table-search-input'
                    v-model={this.keyword}
                    onEnter={this.handleSearchChange}
                    onClear={() => this.handleSearchChange('')}
                    onChange={this.handleSearchChange}
                  />
                  <Button
                    theme='primary'
                    onClick={this.handleQueryTable}
                  >
                    {this.$t('查询')}
                  </Button>
                </div>
                <div class='related-table-container'>
                  <Table
                    data={this.tableData}
                    height='100%'
                    columns={this.transformedColumns}
                    scroll-loading={this.isScrollLoading}
                    onScrollBottom={this.handlePageChange}
                    style='width: 100%;'
                    v-slots={{
                      expandRow: row => {
                        return (
                          <div>
                            <JsonPretty data={row.source}></JsonPretty>
                          </div>
                        );
                      }
                    }}
                  ></Table>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div class='empty-chart'>
            {this.emptyText ? (
              this.emptyText
            ) : (
              <Exception type='building'>
                <span>{this.$t('暂无关联日志')}</span>
                <div class='text-wrap'>
                  <span class='text-row'>{this.$t('可前往配置页去配置相关日志')}</span>
                  <Button
                    theme='primary'
                    onClick={() => this.handleRelated()}
                  >
                    {this.$t('关联日志')}
                  </Button>
                </div>
              </Exception>
            )}
          </div>
        )}
      </div>
    );
  }
});
