/* eslint-disable @typescript-eslint/naming-convention */
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
import { type PropType, type Ref, defineComponent, getCurrentInstance, inject, ref, watch } from 'vue';

import { OverflowTitle, Popover } from 'bkui-vue';
import { Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { copyText } from 'monitor-common/utils/utils';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { useI18n } from 'vue-i18n';

import { NODE_TYPE_ICON } from './node-type-svg';
import { getApmServiceType, getNodeAttrs, truncateText } from './utils';

import type { IEdge, ITopoNode } from './types';

import './failure-topo-tooltips.scss';
const { i18n } = window;
type PopoverInstance = {
  [key: string]: any;
  close?: () => void;
  hide?: () => void;
  show?: () => void;
};

export default defineComponent({
  props: {
    /** 显示查看资源的icon */
    showViewResource: {
      type: Boolean,
      default: true,
    },
    type: {
      type: String,
      default: 'node',
    },
    edge: {
      type: Object as PropType<IEdge>,
      default: () => {},
    },
    model: {
      type: [Object, Array] as PropType<any>,
      required: true,
    },
  },
  emits: ['viewResource', 'FeedBack', 'toDetail', 'toDetailSlider', 'toDetailTab', 'toTracePage'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    /** 当前点击的线和边 */
    const activeEdge = ref(null);
    const activeNode = ref(null);
    const popover = ref<HTMLDivElement>();
    /** 线存在变化或者type变化为edge时，重置边的图表 */
    watch(
      () => ({ edge: props.edge, type: props.type }),
      ({ edge, type }) => {
        activeEdge.value = edge || {};
        if (leftChart) {
          leftChart.dispose();
          leftChart = null;
        }
        if (rightChart) {
          rightChart.dispose();
          rightChart = null;
        }
        if (type === 'edge' && !edge.aggregated) {
          setTimeout(renderChart, 300);
        }
      }
    );
    const { proxy } = getCurrentInstance();
    /** 展示右侧资源图 */
    const handleViewResource = node => {
      emit('viewResource', { sourceNode: props.model, node });
    };
    /** 图表缓存 */
    let leftChart = null;
    let rightChart = null;
    /** 根因上报 */
    const handleFeedBack = node => {
      emit('FeedBack', node);
    };
    /** 渲染调用关系线左右两侧的图 */
    const renderChart = () => {
      const charts = [];
      // 默认只渲染2个图表 分在线的左右两边展示
      activeEdge.value.events.forEach((item, index) => {
        if (index < 2) {
          /** 根据数据大小调整边界 */
          const maxValue = String(Math.max(...item.time_series.map(value => value[1])));
          const gridLeftMap = ['8%', '10%', '12%', '15%', '18%'];
          const timeSeries = item.time_series.map(item => {
            item[0] = dayjs.tz(item[0]).format('YYYY-MM-DD HH:mm:ss');
            return item;
          });
          const dom = document.getElementById(`edge-chart-${index}`) as HTMLDivElement;
          if (!dom) return;
          const chart = echarts.init(dom);
          chart.setOption({
            grid: {
              left: gridLeftMap[maxValue.length - 1] ?? '18%',
              right: '0%',
              top: '10%',
              bottom: '20',
              containLabel: false,
            },
            tooltip: {
              trigger: 'item',
              appendToBody: true,
              position(pos) {
                const top = 10; // 偏移量，可根据需要调整
                return [pos[0] + top, pos[1]];
              },
              formatter: params => {
                return `
                  <p style="color=#979BA5;line-height: 16px;">${item.event_name}：<span style="color: white">${(params as any).data[1]}</span></p>
                  <p style="color=#979BA5;line-height: 16px;">时间：<span style="color: white">${(params as any).data[0]}</span></p>
                `;
              },
            },
            xAxis: {
              type: 'category',
              axisLabel: {
                align: 'right',
                formatter(value) {
                  return dayjs.tz(value).format('HH:mm');
                },
              },
              axisTick: {
                show: false,
              },
              axisLine: {
                lineStyle: {
                  color: 'rgba(151, 155, 165, 1)', // 设置刻度线颜色为蓝色
                },
              },
            },
            yAxis: {
              type: 'value',
              splitNumber: 2,
              minInterval: 1,
              axisLabel: {
                color: 'rgba(151, 155, 165, 1)',
              },
              axisTick: {
                length: 3,
              },
              splitLine: {
                lineStyle: {
                  type: 'dashed',
                  color: 'rgba(151, 155, 165, 1)',
                },
              },
              axisLine: {
                lineStyle: {
                  color: 'rgba(151, 155, 165, 1)', // 设置刻度线颜色为蓝色
                },
              },
            },
            series: [
              {
                data: timeSeries,
                type: 'line',
                connectNulls: true,
                tooltip: {
                  backgroundColor: '#000000',
                  borderColor: '#000000',
                  padding: 8,
                },
                lineStyle: {
                  color: 'rgba(253, 185, 128, 1)',
                },
                symbol: 'circle',
                symbolSize: params => {
                  if (params[2] > 0) return 10;
                  return 5;
                },
                itemStyle: {
                  /** 大于0为异常点 */
                  color: params => {
                    if (params.data[2] > 0) return '#EA3636';
                    return 'rgba(253, 185, 128, 1)';
                  },
                },
                markPoint: {
                  symbolSize: 7,
                  itemStyle: {
                    color: '#EA3636',
                  },
                },
              },
            ],
          });
          charts.push(chart);
        }
      });
      [leftChart, rightChart] = charts;
    };
    /** tooltips消失销毁图表 */
    const handleAfterHidden = () => {
      activeNode.value = null;
      if (leftChart) {
        leftChart.dispose();
        leftChart = null;
      }
      if (rightChart) {
        rightChart.dispose();
        rightChart = null;
      }
    };
    /** 点击展示对应详情 */
    const handleShowNodeTips = (node: ITopoNode) => {
      activeNode.value = node;
      // 如果当前是展示边的tips 则需要渲染图表
      if (props.type === 'edge') {
        activeEdge.value = node;
        setTimeout(() => {
          renderChart();
        }, 200);
      }
    };
    /** popover隐藏 */
    const hide = () => {
      if (!activeNode?.value?.id) {
        return;
      }
      activeEdge.value = null;
      (proxy.$refs?.[`popover_${activeNode.value.id}`] as PopoverInstance)?.hide?.();
      activeNode.value = null;
    };
    /** 跳转详情 */
    const handleToDetail = node => {
      emit('toDetail', node);
    };
    /** 不同类型的路由跳转逻辑处理 */
    const typeToLinkHandle = {
      BcsService: {
        title: 'pod详情页',
        path: () => '/k8s-new',
        beforeJumpVerify: () => true,
        query: node => {
          const { namespace, cluster_id, service_name, pod_name } = node.entity?.dimensions || {};
          const filterBy = {
            service: service_name ? [service_name] : [],
            namespace: namespace ? [namespace] : [],
            pod: pod_name ? [pod_name] : [],
          };
          return {
            groupBy: JSON.stringify(['namespace', 'service']),
            scene: 'network',
            sceneId: 'kubernetes',
            activeTab: 'list',
            cluster: cluster_id ?? '',
            filterBy: JSON.stringify(filterBy),
          };
        },
      },
      BcsWorkload: {
        title: 'pod详情页',
        path: () => '/k8s-new',
        beforeJumpVerify: () => true,
        query: node => {
          const { namespace, pod_name, cluster_id, workload_name, workload_type } = node.entity?.dimensions || {};
          const filterBy = {
            workload: workload_name ? [`${workload_type}:${workload_name}`] : [],
            namespace: namespace ? [namespace] : [],
            pod: pod_name ? [pod_name] : [],
          };
          return {
            sceneId: 'kubernetes',
            groupBy: JSON.stringify(['namespace', 'workload']),
            activeTab: 'list',
            cluster: cluster_id ?? '',
            filterBy: JSON.stringify(filterBy),
          };
        },
      },
      BcsPod: {
        title: 'pod详情页',
        path: () => '/k8s-new',
        beforeJumpVerify: () => true,
        query: node => {
          const { namespace, pod_name, cluster_id } = node.entity?.dimensions || {};
          const filterBy = {
            namespace: namespace ? [namespace] : [],
            pod: pod_name ? [pod_name] : [],
          };
          return {
            groupBy: JSON.stringify(['namespace', 'pod']),
            sceneId: 'kubernetes',
            activeTab: 'detail',
            cluster: cluster_id ?? '',
            filterBy: JSON.stringify(filterBy),
          };
        },
      },
      BkNodeHost: {
        title: '主机详情页',
        path: node => `/performance/detail/${node.entity?.dimensions?.bk_host_id}`,
        beforeJumpVerify: node => !!node.entity?.dimensions?.bk_host_id,
        query: node => ({
          'filter-bk_host_id': node.entity?.dimensions?.bk_host_id ?? '',
          'filter-bk_target_cloud_id': node.entity?.dimensions?.bk_cloud_id ?? '',
          'filter-bk_target_ip': node.entity?.dimensions?.inner_ip ?? '',
        }),
      },
      APMService: {
        title: '服务详情页',
        path: () => '/apm/service/',
        beforeJumpVerify: node => !!node.entity?.dimensions?.apm_service_name,
        query: node => ({
          'filter-app_name': node.entity?.dimensions?.apm_application_name ?? '',
          'filter-service_name': node.entity?.dimensions?.apm_service_name ?? '',
        }),
      },
    };

    /** 根据类型判断是否可以跳转 */
    function canJumpByType(node) {
      const type = node.entity.entity_type;
      // @ts-ignore
      if (!(Object.hasOwn(typeToLinkHandle, type) && !!typeToLinkHandle[type])) {
        return false;
      }
      return typeToLinkHandle[type].beforeJumpVerify(node);
    }

    /** 跳转pod页面 */
    const handleToLink = node => {
      if (!canJumpByType(node)) return;
      const timestamp = new Date().getTime();
      const linkHandleByType = typeToLinkHandle[node.entity.entity_type];
      const query = linkHandleByType?.query(node);
      const { observe_time_rage } = node.entity;
      if (observe_time_rage && Object.keys(observe_time_rage).length > 0) {
        query.from = observe_time_rage.start_at;
        query.to = observe_time_rage.end_at;
      }
      const queryString = Object.keys(query)
        .map(key => `${key}=${query[key]}`)
        .join('&');

      const { origin, pathname } = window.location;
      // 使用原始 URL 的协议、主机名和路径部分构建新的 URL
      const baseUrl = bkzIds.value[0] ? `${origin}${pathname}?bizId=${bkzIds.value[0]}` : '';
      window.open(`${baseUrl}#${linkHandleByType?.path(node)}?${queryString.toString()}`, timestamp.toString());
    };

    /** 拷贝操作 */
    const handleCopy = (text: string) => {
      copyText(text);
      Message({
        theme: 'success',
        message: i18n.t('复制成功'),
      });
    };

    /** 详情侧滑 */
    const goDetailSlider = node => {
      emit('toDetailSlider', node);
    };

    /** 跳转trace详情页，高亮对应span */
    const handleViewSpan = node => {
      emit('toTracePage', node.entity, 'traceDetail');
    };

    /** 跳转trace详情页，打开对应span详情 */
    const handleViewSpanDetail = node => {
      emit('toTracePage', node.entity, 'spanDetail');
    };

    /** 告警详情 */
    const goDetailTab = node => {
      emit('toDetailTab', node);
    };
    return {
      popover,
      typeToLinkHandle,
      activeNode,
      hide,
      activeEdge,
      canJumpByType,
      handleAfterHidden,
      handleShowNodeTips,
      handleToDetail,
      handleViewResource,
      handleFeedBack,
      handleToLink,
      handleCopy,
      goDetailSlider,
      goDetailTab,
      handleViewSpan,
      handleViewSpanDetail,
      t,
    };
  },
  render() {
    if (!this.model) return undefined;
    const { aggregated_nodes } = this.model;
    /** 创建边的node展示  */
    const createEdgeNodeItem = (node: ITopoNode) => {
      return [
        <div
          key={`${node?.entity?.entity_id}-${node?.entity?.entity_name}`}
          class='node-source-wrap'
        >
          <div
            class={[
              'node-source',
              node?.entity?.is_anomaly && 'node-source-anomaly',
              node?.entity?.is_on_alert && 'node-source-alert',
              node?.alert_all_recorved && 'node-source-alert-recorved',
            ]}
          >
            <span class='node-item'>
              <span>
                {(node?.entity?.is_on_alert || node?.alert_all_recorved) && (
                  <span class='alert-wrap'>
                    <i class='icon-monitor icon-menu-event' />
                  </span>
                )}

                <i
                  style={{ color: '#fff' }}
                  class={[
                    'item-source mr0',
                    'icon-monitor',
                    'edge-item-source',
                    NODE_TYPE_ICON[getApmServiceType(node?.entity)],
                    node?.entity?.is_anomaly && 'item-anomaly',
                  ]}
                />
              </span>
            </span>
            {node?.entity?.properties?.entity_category}(
            <OverflowTitle
              key={node?.entity?.entity_id}
              class={['node-name', this.canJumpByType(node) && 'node-link-name']}
              type='tips'
            >
              <span onClick={this.handleToLink.bind(this, node)}>{node?.entity?.entity_name || '--'}</span>
            </OverflowTitle>
            ）
            {(node?.entity.is_root || node.is_feedback_root) && (
              <span class={['node-root-icon', node.is_feedback_root ? 'node-root-feedback-icon' : false]}>
                {this.t('根因')}
              </span>
            )}
          </div>
        </div>,
      ];
    };
    /** 传入text 这些只有在渲染调用关系的流动线才会传入，所以内部会根据text等进行判断，不传入则默认是走渲染2个节点中间的线
     * 调用关系的流动线需要根据方向渲染在中间线的左右2侧， 从属的流动关系则直接修改中线
     * 线会根据边的调用关系和从属关系画在不同的位置
     * 从属 线居中
     * 调用 区分左右两侧在不同的方向
     * 线根据direction 渲染不同的流动方向
     */
    const createEdgeNodeLink = (
      text = '',
      direction = 'forward',
      showLink = true,
      index = 0,
      edgeEvent?: IEdge,
      exitTimeSeries?: boolean
    ) => {
      const { is_anomaly, edge_type, events } = this.activeEdge;
      const ebpfCall = edge_type === 'ebpf_call';
      const directionReverse = (direction || events[0]?.direction) === 'reverse';
      const eventText = this.t(ebpfCall ? '调用关系' : '从属关系');
      /** 流动线创建 */
      const renderSvg = () => {
        return (
          showLink &&
          is_anomaly &&
          events.length > 0 && (
            <div class='link-svg'>
              <svg
                width='2'
                height={exitTimeSeries ? 200 : 80}
                xmlns='http://www.w3.org/2000/svg'
              >
                <line
                  class={{ 'flowing-dash': ebpfCall }}
                  stroke='#f55555'
                  stroke-dasharray='5,5'
                  stroke-width='2'
                  x1='1'
                  x2='1'
                  y1='0'
                  y2='200'
                />
              </svg>
            </div>
          )
        );
      };
      return (
        <div
          class={[
            'node-link',
            is_anomaly && !ebpfCall && 'node-err-link',
            directionReverse && 'reverse-node-link',
            ebpfCall && !text && 'edpf-node-link',
          ]}
        >
          {index > 0 && renderSvg()}
          <div class='node-link-text'>
            <span>{text ? '' : eventText}</span>
          </div>
          {showLink && is_anomaly && events.length > 0 && events[index]?.time_series?.length > 0 && (
            <div class='edge-chart-wrap'>
              <div class='edge-chart-title'>
                <div>
                  <span class='edge-chart-title-text'>{edgeEvent.event_name}</span>
                  <span class='edge-chart-title-time'>1m</span>
                </div>
                <span class='edge-chart-sub-title'>{edgeEvent.metric_name}</span>
              </div>
              <div id={`edge-chart-${index}`} />
            </div>
          )}
          {index === 0 && renderSvg()}
        </div>
      );
    };
    /** 边的tips详情 */
    const createEdgeToolTip = (nodes: ITopoNode[]) => {
      const linkMap: { direction_0?: IEdge; direction_1?: IEdge } = {};
      /** 最多展示2个，分别在线的左右两侧 */
      const { events } = this.activeEdge;
      /** 是否存在 time_series */
      let exitTimeSeries = false;
      events.forEach((event: IEdge, index) => {
        if (index < 2) {
          linkMap[`direction_${index}`] = event;
          if (!exitTimeSeries) {
            exitTimeSeries = event.time_series.length > 0;
          }
        }
      });
      return [
        <div
          key={`edge-tooltip-${this.activeEdge.id}`}
          class={[
            'edge-tooltip-content',
            this.activeEdge.edge_type !== 'ebpf_call' && 'dependency-tooltip-content',
            linkMap.direction_0 && !linkMap.direction_1 && 'flex-end',
            linkMap.direction_1 && !linkMap.direction_0 && 'flex-start',
          ]}
        >
          {createEdgeNodeItem(nodes[0])}
          {createEdgeNodeLink('', '', this.activeEdge.edge_type !== 'ebpf_call', 1, this.activeEdge, exitTimeSeries)}

          <div class='link-wrap'>
            {/* 左边的线和图 */}
            {this.activeEdge.edge_type === 'ebpf_call' && linkMap.direction_0 && (
              <div class='left-link'>
                {createEdgeNodeLink(
                  linkMap.direction_0.event_name,
                  linkMap.direction_0.direction,
                  true,
                  0,
                  linkMap.direction_0,
                  exitTimeSeries
                )}
              </div>
            )}
            {/* 右侧的线和图 */}
            {this.activeEdge.edge_type === 'ebpf_call' && linkMap.direction_1 && (
              <div class='right-link'>
                {createEdgeNodeLink(
                  linkMap.direction_1.event_name,
                  linkMap.direction_1.direction,
                  true,
                  1,
                  linkMap.direction_1,
                  exitTimeSeries
                )}
              </div>
            )}
          </div>

          {createEdgeNodeItem(nodes[1])}
        </div>,
      ];
    };
    /** icon */
    const createCommonIconBtn = (
      name: string,
      style?: Record<string, any>,
      needIcon = true,
      node: ITopoNode = {},
      clickFn = ''
    ) => {
      const feedbackRootIcon = node.is_feedback_root ? 'icon-mc-cancel-feedback' : 'icon-fankuixingenyin';
      return (
        <span
          style={{ ...style }}
          class='icon-btn'
          onClick={() => clickFn && this[`handle${clickFn}`](node)}
        >
          {needIcon && (
            <i
              class={[
                'icon-monitor',
                'btn-icon',
                clickFn === 'FeedBack'
                  ? feedbackRootIcon
                  : clickFn === 'ViewSpan'
                    ? 'icon-fenxiang'
                    : 'icon-ziyuantuopu',
              ]}
            />
          )}
          <span
            class='btn-text'
            v-overflow-tips
            onClick={this.handleToDetail.bind(this, node)}
          >
            {name}
          </span>
        </span>
      );
    };
    /** 左右组合样式 */
    const createCommonForm = (label: string, value: () => any) => {
      return (
        <div class='content-form'>
          <div class='content-form-label'>{label}</div>
          <div class='content-form-value'>{value?.()}</div>
        </div>
      );
    };
    /** 聚合node或者边的list tips */
    const createNodeToolTipList = (node: IEdge | ITopoNode, isEdge = false) => {
      const { aggregated_edges, aggregated_nodes, total_count, anomaly_count, entity, edge_type } = node;
      const aggregatedList = isEdge ? aggregated_edges : aggregated_nodes;
      const { groupAttrs } = getNodeAttrs(this.model);
      const createNodeItem = node => {
        const isShowRootText = node?.entity?.is_anomaly;
        return (
          <Popover
            ref={`popover_${node.id}`}
            extCls='failure-topo-tooltips-popover'
            v-slots={{
              content: (
                <div class='failure-topo-tooltips'>
                  {isEdge ? createEdgeToolTip(node.nodes) : createNodeToolTip(node)}
                </div>
              ),
              default: (
                <li
                  class={['tool-tips-list-item', this.activeNode?.id === node.id && 'active']}
                  onClick={this.handleShowNodeTips.bind(this, node)}
                >
                  <span>
                    {isEdge
                      ? [
                          <span
                            key={`${node.id}-edge`}
                            class={[
                              'item-edge',
                              edge_type === 'ebpf_call' && 'call-edge',
                              node.is_anomaly && 'anomaly-edge',
                            ]}
                          />,
                          <span key={`${node.id}-edge-text`}>
                            {`${node.source_type} ${node.source_name}`}-{`${node.target_type} ${node.target_name}`}
                          </span>,
                        ]
                      : [
                          <span
                            key={`${node.id}-edge-icon-source`}
                            style={{ backgroundColor: groupAttrs.fill, border: `1px solid ${groupAttrs.stroke}` }}
                            class='item-source'
                          >
                            <i
                              style={{
                                color: '#fff',
                              }}
                              class={[
                                'icon-monitor',
                                NODE_TYPE_ICON[getApmServiceType(node?.entity)],
                                isShowRootText && 'item-anomaly',
                                node?.entity?.is_on_alert && 'item-alert',
                              ]}
                            />
                          </span>,
                          <span key={`${node.id}-edge-name`}>{node?.entity?.entity_name}</span>,
                        ]}
                  </span>
                  <i class='icon-monitor icon-arrow-right' />
                </li>
              ),
            }}
            placement='right'
            popoverDelay={[100, 200]}
            renderType='shown'
            trigger='click'
            onAfterHidden={this.handleAfterHidden}
          />
        );
      };
      return (
        <div class='tool-tips-list-wrap'>
          <span class='title-wrap'>
            {isEdge ? (
              <i18n-t
                class='tool-tips-list-title'
                v-slots={{
                  slot0: () => <span class='weight'>{aggregatedList.length + 1}</span>,
                }}
                keypath='共 {slot0} 条边'
                tag='span'
              />
            ) : (
              <i18n-t
                class='tool-tips-list-title'
                v-slots={{
                  slot0: () => <span class='weight'>{total_count}</span>,
                  type: () => entity.entity_type,
                  slot1: () => <span class='weight error-color'>{anomaly_count}</span>,
                }}
                keypath={
                  (anomaly_count as number) > 0
                    ? '共 {slot0} 个 {type}节点，其中 {slot1} 个异常'
                    : '共 {slot0} 个 {type}节点'
                }
                tag='span'
              />
            )}
          </span>
          <ul class='tool-tips-list'>{[createNodeItem(node), ...aggregatedList.map(createNodeItem)]}</ul>
        </div>
      );
    };
    /** node的tips详情 */
    const createNodeToolTip = (node: ITopoNode) => {
      const isShowRootText = node.is_feedback_root || node?.entity?.is_root;
      const bgColor = node?.entity?.is_root ? '#EA3636' : '#FF9C01';
      return (
        <div class='node-tooltip'>
          <div class='node-tooltip-header'>
            <span class='item-source'>
              <i
                style={{
                  color: '#F55555',
                }}
                class={[
                  'icon-monitor',
                  NODE_TYPE_ICON[getApmServiceType(node?.entity)],
                  (isShowRootText || node?.entity?.is_anomaly) && 'item-anomaly',
                ]}
              />
            </span>
            <div
              key={node?.entity?.entity_id}
              class={['header-name', this.canJumpByType(node) && 'header-pod-name']}
              v-bk-tooltips={{
                disabled: !this.canJumpByType(node),
                content: (
                  <div>
                    <div>{node?.entity?.entity_name}</div>
                    <br />
                    {this.t(`点击前往：${this.typeToLinkHandle[node?.entity?.entity_type]?.title ?? '主机详情页'}`)}
                  </div>
                ),
              }}
            >
              <span onClick={this.handleToLink.bind(this, node)}>{node?.entity?.entity_name}</span>
            </div>
            <span
              class='icon-btn'
              onClick={this.handleCopy.bind(this, node?.entity?.entity_name)}
            >
              <i class={['icon-monitor', 'btn-icon', 'icon-mc-copy-fill']} />
              {this.t('复制')}
            </span>
            {isShowRootText && (
              <span
                style={{
                  backgroundColor: isShowRootText ? bgColor : '#00FF00',
                }}
                class='root-mark'
              >
                {truncateText(this.t('根因'), 28, 11, 'PingFangSC-Medium')}
              </span>
            )}
            <div class='node-tooltip-header-icon-wrap'>
              {this.showViewResource &&
                node.entity.rank.rank_category.category_name !== 'third_party' &&
                createCommonIconBtn(
                  this.t('查看从属'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'ViewResource'
                )}
              {isShowRootText &&
                node.entity.rca_trace_info?.abnormal_traces?.length > 0 &&
                createCommonIconBtn(
                  this.t('查看Span'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'ViewSpan'
                )}
              {this.showViewResource &&
                node.is_feedback_root &&
                createCommonIconBtn(
                  this.t('取消反馈根因'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'FeedBack'
                )}
              {this.showViewResource &&
                !node.is_feedback_root &&
                !node?.entity?.is_root &&
                createCommonIconBtn(
                  this.t('反馈新根因'),
                  {
                    marginLeft: '16px',
                  },
                  true,
                  node,
                  'FeedBack'
                )}
            </div>
          </div>
          <div class='node-tooltip-content'>
            {node.alert_display.alert_name &&
              createCommonForm(`${this.t('包含告警')}：`, () => (
                <>
                  <span
                    class='flex-label'
                    onClick={this.goDetailSlider.bind(this, node)}
                  >
                    {createCommonIconBtn(
                      node.alert_display.alert_name || '',
                      {
                        marginRight: '4px',
                      },
                      false,
                      node
                    )}
                  </span>
                  {node.alert_ids.length > 1 && (
                    <span
                      class='flex-text'
                      onClick={this.goDetailTab.bind(this, node)}
                    >
                      <i18n-t
                        class='tool-tips-list-title'
                        v-slots={{
                          slot0: () =>
                            createCommonIconBtn(
                              node.alert_ids.length.toString(),
                              {
                                marginRight: '4px',
                                marginLeft: '4px',
                                color: '#699DF4',
                              },
                              false
                            ),
                        }}
                        keypath='等共 {slot0} 个同类告警'
                        tag='span'
                      />
                    </span>
                  )}
                </>
              ))}
            {isShowRootText &&
              node.entity?.rca_trace_info?.abnormal_message &&
              createCommonForm(`${this.t('异常信息')}：`, () => (
                <div
                  class='except-info'
                  onClick={this.handleViewSpanDetail.bind(this, node)}
                >
                  <OverflowTitle
                    class='except-text'
                    type='tips'
                  >
                    <span>{node.entity.rca_trace_info.abnormal_message}</span>
                  </OverflowTitle>
                  <i class='icon-monitor except-icon icon-fenxiang' />
                </div>
              ))}
            {createCommonForm(`${this.t('分类')}：`, () => (
              <>{node.entity.rank.rank_category.category_alias}</>
            ))}
            {createCommonForm(`${this.t('节点类型')}：`, () => (
              <>{node?.entity?.properties?.entity_category || node.entity.rank_name}</>
            ))}
            {createCommonForm(`${this.t('所属业务')}：`, () => (
              <>
                {node.bk_biz_name} (#{node.bk_biz_id})
              </>
            ))}
            {node.entity?.tags?.BcsService &&
              createCommonForm(`${this.t('所属服务')}：`, () => <>{node.entity.tags.BcsService.name}</>)}
          </div>
        </div>
      );
    };
    /** 渲染边的tips */
    const renderEdgeTips = () => {
      return this.edge?.aggregated ? createNodeToolTipList(this.edge, true) : createEdgeToolTip(this.model);
    };
    /** 渲染节点的tips */
    const renderNodeTips = () => {
      return this.showViewResource && aggregated_nodes.length > 0
        ? createNodeToolTipList(this.model)
        : createNodeToolTip(this.model);
    };
    return (
      <div
        class={{
          'failure-topo-tooltips': true,
          'edge-tooltip': this.type === 'edge',
        }}
      >
        {this.type === 'edge' ? renderEdgeTips() : renderNodeTips()}
      </div>
    );
  },
});
