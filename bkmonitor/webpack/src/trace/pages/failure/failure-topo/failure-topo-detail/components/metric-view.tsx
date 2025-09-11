/* eslint-disable @typescript-eslint/naming-convention */
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
import {
  type PropType,
  type Ref,
  computed,
  defineComponent,
  inject,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from 'vue';

import { Button, Checkbox, Exception, Loading, Popover, Switcher } from 'bkui-vue';
import { fitPosition } from 'monitor-ui/chart-plugins/utils';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { useI18n } from 'vue-i18n';

import ErrorImg from '../../../../../static/img/error.svg';
import NoDataImg from '../../../../../static/img/no-data.svg';
import useMetrics from '../useMetrics';
import CustomEventMenu from './custom-event-menu';
import MetricChart from './metric-chart';

import type { IEventTagsItem } from '../../types';
import type { ILegendItem } from 'monitor-ui/chart-plugins/typings';

import './metric-view.scss';

// 定义固定的图表连接组ID - 用于标识需要联动的图表组
const CONNECT_GROUP_ID = 'incident-metric-chart-group';

export default defineComponent({
  components: {
    MetricChart,
  },
  props: {
    data: {
      type: Object as PropType<any>,
      required: true,
    },
    type: {
      type: String as PropType<'edge' | 'node'>,
      required: true,
    },
    getMetricsDataLength: {
      type: Function as PropType<(length: number) => void>,
      default: () => {},
    },
    refreshTime: {
      type: Number,
      required: true,
    },
    showServiceOverview: {
      type: Boolean,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    // 事件分析开关状态
    const showEventAnalyze = ref(false);
    // 是否展示事件分析弹窗
    const popoverShow = ref(false);
    // 当前是否为"节点概览"
    const isNodeView = computed(() => props.type === 'node');
    // 自定义事件menu位置信息
    const customMenuPosition = ref({ left: 0, top: 0 });
    // 点击的事件项
    const clickEventItem = ref<IEventTagsItem>();
    // 存储当前打开的自定义事件弹窗元素
    const customMenuRef = ref(null);
    // 是否在弹窗内点击
    const mousedownInMenu = ref(false);
    // 图例数据
    const legendData = ref<ILegendItem[]>([]);
    // 指标类型
    const metricType = computed(() => (isNodeView.value ? 'node' : props.data.edge_type));
    // 节点类型
    const nodeType = computed(() => props.data.entity.properties?.entity_category || props.data.entity.rank_name);
    // 边的指标数据
    const edgeMetricData = computed(() => props.data.events ?? []);
    // 数据自动刷新时间
    const refreshTime = computed(() => props.refreshTime);
    const showServiceOverview = computed(() => props.showServiceOverview);

    /** 获取接口请求的公共传参数据 */
    const commonParams = computed(() => {
      let index_info = null;
      if (isNodeView.value) {
        index_info = {
          index_type: 'entity',
          entity_type: props.data.entity.entity_type,
          entity_name: props.data.entity.entity_name,
          is_anomaly: props.data.entity.is_anomaly,
          dimensions: props.data.entity.dimensions || {},
        };
      } else {
        index_info = {
          index_type: 'edge',
          source_type: props.data.source_type,
          source_name: props.data.source_name,
          target_type: props.data.target_type,
          target_name: props.data.target_name,
          is_anomaly: props.data.is_anomaly,
        };
      }
      return {
        bk_biz_id: window.bk_biz_id,
        index_info,
      };
    });

    const {
      endTime,
      eventInterval,
      metricsData,
      allEventsData,
      eventsData,
      eventColumns,
      eventConfig,
      isEventsLoaded,
      loading,
      exceptionData,
      disableEventAnalysis,
      getMetricsData,
      getEventsData,
      transformEventData,
      handleChartInit,
      handleChartDestroy,
      handleCheckedAllChange,
      handleGroupChange,
    } = useMetrics(
      commonParams,
      metricType,
      refreshTime,
      showServiceOverview,
      props.getMetricsDataLength,
      edgeMetricData
    );

    // 数据变化时，重置图表
    watch(
      () => props.data,
      () => {
        getMetricsData();
        getEventsData();
      }
    );

    onMounted(() => {
      getMetricsData();
      showEventAnalyze.value = JSON.parse(localStorage.getItem('show-event-analyze')) || false;
      getEventsData();

      document.addEventListener('mousedown', handleDocumentMouseDown);
    });

    // 组件卸载时断开连接
    onUnmounted(() => {
      echarts.disconnect(CONNECT_GROUP_ID);

      document.removeEventListener('mousedown', handleDocumentMouseDown);
    });

    /** 处理事件点击（定位自定义事件菜单） */
    const handleClick = params => {
      const start_time = Math.floor(params.value[0] / 1000);
      const { clientX, clientY } = params.event.event;
      // 计算菜单位置，确保在可视区域内
      const position = fitPosition(
        {
          left: clientX + 12,
          top: clientY + 12,
        },
        400,
        300
      );
      customMenuPosition.value = {
        left: position.left,
        top: position.top,
      };

      clickEventItem.value = {
        bk_biz_id: window.bk_biz_id,
        start_time,
        interval: eventInterval.value,
        index_info: {
          index_type: 'entity',
          entity_type: props.data.entity.entity_type,
          entity_name: props.data.entity.entity_name,
          is_anomaly: props.data.entity.is_anomaly,
          dimensions: props.data.entity.dimensions || {},
          source_filter: eventConfig.value.event_source.list || [],
          type_filter: eventConfig.value.event_level.list || [],
        },
        end_time: endTime.value,
      };
    };

    const handleDocumentMouseDown = event => {
      // 弹窗未显示时跳过
      if (!customMenuPosition.value.left) return;
      const target = event.target;
      const menuEl = customMenuRef.value?.$el;
      // 检测点击目标是否在弹窗内
      mousedownInMenu.value = menuEl?.contains(target);
      if (!mousedownInMenu.value) {
        handleChartBlur();
      }
    };

    /** 隐藏菜单 */
    const handleChartBlur = () => {
      nextTick(() => {
        customMenuPosition.value = {
          left: 0,
          top: 0,
        };
      });
    };

    const handleChangeSwitch = val => {
      localStorage.setItem('show-event-analyze', val);
      if (!val) {
        handleEventAnalyzeCancel();
      }
    };

    const handleShowPopover = () => {
      if (
        !showEventAnalyze.value ||
        !isEventsLoaded.value ||
        allEventsData.value.length === 0 ||
        disableEventAnalysis.value
      )
        return;
      popoverShow.value = !popoverShow.value;
    };

    const handleEventAnalyzeConfirm = () => {
      popoverShow.value = false;
      eventsData.value = transformEventData(eventConfig.value);
      localStorage.setItem('selected-event-config', JSON.stringify(eventConfig.value));
    };

    const handleEventAnalyzeCancel = () => {
      popoverShow.value = false;
      eventConfig.value = JSON.parse(localStorage.getItem('selected-event-config'));
    };

    /** 无数据处理或异常占位 */
    const handleException = () => {
      const { type, msg } = exceptionData.value;
      if (!type && !msg) return '';
      return (
        <Exception
          class='metric-view-exception'
          v-slots={{
            type: () => (
              <img
                class='custom-icon'
                alt=''
                src={type === 'noData' ? NoDataImg : ErrorImg}
              />
            ),
          }}
        >
          <div style={{ color: type === 'noData' ? '#979BA5' : '#E04949' }}>
            <div class='exception-title'>{type === 'noData' ? msg : t('查询异常')}</div>
            {type === 'error' && <span class='exception-desc'>{msg}</span>}
          </div>
        </Exception>
      );
    };

    return {
      loading,
      eventConfig,
      eventColumns,
      showEventAnalyze,
      popoverShow,
      legendData,
      customMenuPosition,
      clickEventItem,
      metricsData,
      allEventsData,
      eventsData,
      isEventsLoaded,
      customMenuRef,
      isNodeView,
      exceptionData,
      nodeType,
      disableEventAnalysis,
      handleException,
      handleShowPopover,
      handleCheckedAllChange,
      handleGroupChange,
      handleEventAnalyzeConfirm,
      handleEventAnalyzeCancel,
      handleChangeSwitch,
      handleChartInit,
      handleChartDestroy,
      handleClick,
      t,
    };
  },
  render() {
    if (this.loading) {
      return (
        <Loading
          class='metric-view-loading'
          color='#1d2024'
          loading={this.loading}
        />
      );
    }
    if (this.exceptionData.showException) {
      return this.handleException();
    }
    return (
      <div class='metric-wrap'>
        {this.isNodeView && (
          <div
            class='event-analyze'
            v-bk-tooltips={{
              content: this.t('暂无关联的事件数据'),
              disabled: this.allEventsData.length > 0 && !this.disableEventAnalysis,
            }}
          >
            <Switcher
              v-model={this.showEventAnalyze}
              disabled={this.allEventsData.length === 0 || this.disableEventAnalysis}
              size='small'
              theme='primary'
              onChange={this.handleChangeSwitch}
            />
            <span class='event-analyze_title'>{this.t('事件分析')}</span>
            <Popover
              extCls='event-analyze-popover'
              arrow={false}
              is-show={this.popoverShow}
              placement='bottom-start'
              theme='light'
              trigger='manual'
              onAfterHidden={this.handleEventAnalyzeCancel}
            >
              {{
                content: () => (
                  <div class='event-analyze-wrapper'>
                    <div class='event-content'>
                      {this.eventColumns.map(column => {
                        const config = this.eventConfig[column.name];
                        if (!config) return undefined;
                        return (
                          <div
                            key={column.name}
                            class='event-wrapper'
                          >
                            <div class='event-content-title'>{column.alias}</div>
                            <Checkbox
                              key={`${column.name}-all`}
                              v-model={config.is_select_all}
                              size='small'
                              onChange={v => this.handleCheckedAllChange(v, column.name, column.list)}
                            >
                              {this.t('全选')}
                            </Checkbox>
                            <Checkbox.Group
                              class='event-content-list'
                              v-model={config.list}
                              onChange={() => this.handleGroupChange(column)}
                            >
                              {column.list?.map(item => (
                                <Checkbox
                                  key={item.value}
                                  disabled={config.list.length === 1 && config.list.includes(item.value)}
                                  label={item.value}
                                  size='small'
                                >
                                  {`${item.alias} (${item.count})`}
                                </Checkbox>
                              ))}
                            </Checkbox.Group>
                          </div>
                        );
                      })}
                    </div>
                    <div class='event-footer'>
                      <Button
                        size='small'
                        theme='primary'
                        onClick={this.handleEventAnalyzeConfirm}
                      >
                        {this.t('确定')}
                      </Button>
                      <Button
                        size='small'
                        onClick={this.handleEventAnalyzeCancel}
                      >
                        {this.t('取消')}
                      </Button>
                    </div>
                  </div>
                ),
                default: () => (
                  <span
                    class='event-analyze_icon'
                    v-bk-tooltips={{
                      content: this.t('请先打开事件分析'),
                      disabled: this.showEventAnalyze || this.allEventsData.length === 0 || this.disableEventAnalysis,
                    }}
                    onClick={this.handleShowPopover}
                  >
                    <i
                      style={{
                        cursor:
                          this.showEventAnalyze &&
                          this.isEventsLoaded &&
                          this.allEventsData.length > 0 &&
                          !this.disableEventAnalysis
                            ? 'pointer'
                            : 'not-allowed',
                      }}
                      class={['icon-monitor icon-filter-fill', this.popoverShow && 'event-analyze_icon-active']}
                    />
                  </span>
                ),
              }}
            </Popover>
          </div>
        )}
        {/* 指标图表 */}
        {this.metricsData.length > 0 &&
          this.metricsData.map((item, index) => (
            <div
              key={`metric-chart-${index}`}
              class='chart-wrap'
            >
              <MetricChart
                eventsData={this.eventsData}
                index={index}
                isNodeView={this.isNodeView}
                metricItem={item}
                showEventAnalyze={this.showEventAnalyze}
                onDestroy={this.handleChartDestroy}
                onEventClick={this.handleClick}
                onInit={this.handleChartInit}
              />
            </div>
          ))}
        {/* 自定义事件菜单 */}
        {this.customMenuPosition?.left > 0 && (
          <CustomEventMenu
            ref='customMenuRef'
            eventItem={this.clickEventItem}
            nodeType={this.nodeType}
            position={this.customMenuPosition}
          />
        )}
      </div>
    );
  },
});
