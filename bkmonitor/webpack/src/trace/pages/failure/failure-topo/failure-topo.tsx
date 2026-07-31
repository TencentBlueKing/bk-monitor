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
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
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
import { defineComponent, onMounted, onUnmounted, watch } from 'vue';

import { Loading, Popover, Slider } from 'bkui-vue';

import DataAccess from '../../../components/data-access';
import ExceptionComp from '../../../components/exception';
import ResourceGraph from '../resource-graph/resource-graph';
import { useTopoData } from './composables/use-topo-data';
import { useTopoGraph } from './composables/use-topo-graph';
import { useTopoInteraction } from './composables/use-topo-interaction';
import { type TopoStateProps, useTopoState } from './composables/use-topo-state';
import { useTopoTimeline } from './composables/use-topo-timeline';
import { useTopoTooltip } from './composables/use-topo-tooltip';
import FailureTopoDetail from './detail/failure-topo-detail';
import FeedbackCauseDialog from './feedback-cause-dialog';
import LegendPopoverContent from './legend/legend-popover-content';
import TopoTools from './toolbar/topo-tools';
import FailureTopoTooltips from './tooltip/failure-topo-tooltips';

import type { GraphAccess, RenderGraphAccess, TooltipAccess } from './types/composable';
import type { ITopoNode } from './types/topo';

import './failure-topo.scss';

export default defineComponent({
  name: 'FailureTopo',
  props: {
    selectNode: {
      type: Array,
      default: () => {
        return [];
      },
    },
    isCollapsed: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['toDetail', 'playing', 'toDetailTab', 'changeSelectNode', 'refresh', 'closeCollapse'],
  setup(props, { emit }) {
    // 整包状态，Vue Array prop 推断为 unknown[]，与 TopoStateProps.selectNode 做兼容断言
    const state = useTopoState(props as TopoStateProps);

    /** Graph / Tooltip 访问器（统一读写 shallowRef） */
    const graphAccess: GraphAccess = { getGraph: () => state.graphInstanceRef.value };
    const tooltipAccess: TooltipAccess = { getTooltip: () => state.g6TooltipRef.value };

    // 数据层
    const data = useTopoData(state, graphAccess);

    // renderGraph 前向引用（interaction 早于 graph 创建，但依赖 renderGraphCallback）
    let renderGraphFn: RenderGraphAccess['renderGraphCallback'] = () => {};
    const renderGraphAccess: RenderGraphAccess = {
      renderGraphCallback: (data, renderComplete) => renderGraphFn(data, renderComplete),
    };

    // 交互 / 时间轴 / Tooltip / Graph — 整包传入，由各 composable 按需取字段
    const interaction = useTopoInteraction(state, data, graphAccess, tooltipAccess, renderGraphAccess, emit);
    const timeline = useTopoTimeline(state, data, graphAccess, emit);
    const tooltip = useTopoTooltip(state, data, interaction, state.g6TooltipRef, graphAccess);
    const { initGraph, renderGraph, cleanupGraph } = useTopoGraph(state, data, interaction, timeline, tooltip);

    // 赋值前向引用（renderGraph 在 useTopoGraph 返回后才可用）
    renderGraphFn = renderGraph;

    /** 纯 emit 透传（留在主文件） */
    const handleToDetail = (node: ITopoNode) => emit('toDetail', node);

    const refresh = () => emit('refresh');

    onMounted(() => {
      if (state.topoStatus.value === 'normal') {
        data.registerInitGraphCallback(initGraph);
        data.getGraphData();
      }
    });

    watch(
      () => state.topoStatus.value,
      val => {
        if (val === 'normal') {
          data.registerInitGraphCallback(initGraph);
          data.getGraphData();
        }
      }
    );

    onUnmounted(() => {
      cleanupGraph();
      data.clearRefreshTimeout();
      timeline.cleanupTimeline();
      data.cleanupData();
    });

    /** 右侧资源拓扑、节点/边概览侧滑同时打开时，关闭左侧侧滑 */
    watch(
      () => [state.showServiceOverview.value, state.showResourceGraph.value],
      ([showService, showResource]) => {
        if (showService && showResource) {
          emit('closeCollapse', true);
        }
        if (!showService) {
          state.resourceEdgeId.value = '';
        }
      }
    );

    /** 左侧菜单选中联动 */
    watch(
      () => props.selectNode,
      val => {
        if (val.length) {
          const graph = state.graphInstanceRef.value;
          if (!graph) return;
          /** 清除之前节点状态 */
          // biome-ignore lint/complexity/noForEach: <explanation>
          graph.findAllByState('node', 'running').forEach?.(node => {
            graph.setItemState(node, 'running', false);
          });
          interaction.navSelectNode.value?.map?.((item, index) => {
            /** 多个节点只设置第一个节点为资源图节点 */
            if (index === 0) {
              if (item.entityId !== state.nodeEntityId.value) {
                state.showResourceGraph.value = false;
                state.showServiceOverview.value = false;
                state.resourceNodeId.value = item.id;
                state.nodeEntityId.value = item.entityId;
                state.nodeEntityName.value = item.entity_name;
              }
              data.moveToCenterIfNeeded(
                graph,
                state.resourceNodeId.value,
                state.graphRef.value!.clientWidth,
                state.graphRef.value!.clientHeight
              );
            }
            graph.setItemState(graph.findById(item.id), 'running', true);
          });
        }
      }
    );

    /** 右侧资源拓扑、节点/边概览侧滑同时打开时，打开左侧侧滑，关闭节点/边概览侧滑 */
    watch(
      () => props.isCollapsed,
      val => {
        if (!val && state.showServiceOverview.value && state.showResourceGraph.value) {
          state.showServiceOverview.value = false;
        }
      }
    );

    /** playing 期间关闭 tooltip（包含聚合节点 Popover 与 G6 tooltip） */
    watch(
      () => state.isPlay.value,
      val => {
        if (val) {
          interaction.handleHideTooltips();
        }
      }
    );

    return {
      // state（模板所需）
      isPlay: state.isPlay,
      nodeEntityId: state.nodeEntityId,
      topoTools: state.topoTools,
      showResourceGraph: state.showResourceGraph,
      showServiceOverview: state.showServiceOverview,
      timelinePosition: state.timelinePosition,
      topoGraphRef: state.topoGraphRef,
      tooltipsEdge: state.tooltipsEdge,
      edgeDetail: state.edgeDetail,
      isClickEdgeItem: state.isClickEdgeItem,
      graphRef: state.graphRef,
      loading: state.loading,
      zoomValue: state.zoomValue,
      resourceGraphRef: state.resourceGraphRef,
      tooltipCompRef: state.tooltipCompRef,
      wrapRef: state.wrapRef,
      showLegend: state.showLegend,
      tooltipsModel: state.tooltipsModel,
      nodeDetail: state.nodeDetail,
      feedbackCauseShow: state.feedbackCauseShow,
      feedbackModel: state.feedbackModel,
      resourceNodeId: state.resourceNodeId,
      tooltipsType: state.tooltipsType,
      detailType: state.detailType,
      errorData: state.errorData,
      nodeEntityName: state.nodeEntityName,
      detailInfo: state.detailInfo,
      getTopoWidth: state.getTopoWidth,
      curLinkedEdges: state.curLinkedEdges,
      refreshTime: state.refreshTime,
      showViewResource: state.showViewResource,
      topoStatus: state.topoStatus,
      bkzIds: state.bkzIds,
      dataAccessSpaceList: state.dataAccessSpaceList,
      incidentDetailData: state.incidentDetailData,
      t: state.t,
      // data
      topoRawDataCache: data.topoRawDataCache,
      handleChangeRefleshTime: data.handleChangeRefleshTime,
      // interaction
      handleHideTooltips: interaction.handleHideTooltips,
      handleRootToSpan: interaction.handleRootToSpan,
      handleFeedBackChange: interaction.handleFeedBackChange,
      handleFeedBack: interaction.handleFeedBack,
      handleShowLegend: interaction.handleShowLegend,
      handleViewResource: interaction.handleViewResource,
      handleViewServiceFromResource: interaction.handleViewServiceFromResource,
      handleViewServiceFromTop: interaction.handleViewServiceFromTop,
      handleViewServiceFromTopo: interaction.handleViewServiceFromTopo,
      handleUpdateZoom: interaction.handleUpdateZoom,
      handleZoomChange: interaction.handleZoomChange,
      handleResetZoom: interaction.handleResetZoom,
      handleUpdateAggregateConfig: interaction.handleUpdateAggregateConfig,
      handleToDetailSlider: interaction.handleToDetailSlider,
      setHighlightEdge: interaction.setHighlightEdge,
      handleToDetailTab: interaction.handleToDetailTab,
      goToTracePage: interaction.goToTracePage,
      handleCollapseChange: interaction.handleCollapseChange,
      handleHighlightEdge: interaction.handleHighlightEdge,
      // timeline
      handleTimelineChange: timeline.handleTimelineChange,
      handlePlay: timeline.handlePlay,
      handleResetPlay: timeline.handleResetPlay,
      // 主文件纯 emit
      handleToDetail,
      refresh,
    };
  },
  render() {
    return (
      <div
        id='failure-topo'
        ref='wrapRef'
        class={[
          'failure-topo',
          this.isPlay && 'failure-topo-play',
          this.topoStatus === 'empty' && 'failure-topo-empty',
        ]}
      >
        {this.topoStatus === null ? null : this.topoStatus === 'empty' && this.dataAccessSpaceList?.length ? (
          <DataAccess
            showEnableButton={false}
            spaceList={this.dataAccessSpaceList}
            wxCsLink={this.incidentDetailData.wx_cs_link}
            isDarkTheme
          />
        ) : (
          <>
            <TopoTools
              ref='topoTools'
              v-model:showResource={this.showResourceGraph}
              v-model:showService={this.showServiceOverview}
              timelinePlayPosition={this.timelinePosition}
              topoRawDataList={this.topoRawDataCache.diff}
              onChangeRefleshTime={this.handleChangeRefleshTime}
              onPlay={this.handleResetPlay}
              onShowService={this.handleViewServiceFromTop}
              onTimelineChange={this.handleTimelineChange}
              onUpdate:AggregationConfig={this.handleUpdateAggregateConfig}
            />
            <Loading
              class='failure-topo-loading'
              color='#292A2B'
              loading={this.loading}
            >
              <div
                ref='topoGraphRef'
                class='topo-graph-wrapper'
              >
                <div
                  style={{ width: this.getTopoWidth }}
                  class='topo-graph-wrapper-padding'
                >
                  {this.errorData.isError || this.errorData.isNoData ? (
                    <ExceptionComp
                      errorMsg={this.errorData.msg}
                      imgHeight={100}
                      isDarkTheme={true}
                      isError={this.errorData.isError}
                      title={this.errorData.isError ? this.t('查询异常') : this.t('暂无数据')}
                    />
                  ) : (
                    <>
                      <div
                        id='topo-graph'
                        ref='graphRef'
                        class='topo-graph'
                      />
                      <div class='failure-topo-graph-zoom'>
                        <Popover
                          extCls='failure-topo-graph-legend-popover'
                          v-slots={{
                            content: <LegendPopoverContent />,
                            default: (
                              <div
                                class={[
                                  'failure-topo-graph-legend',
                                  this.showLegend && 'failure-topo-graph-legend-active',
                                ]}
                                v-bk-tooltips={{
                                  content: this.t('显示图例'),
                                  disabled: this.showLegend,
                                  boundary: this.wrapRef,
                                }}
                                onClick={this.handleShowLegend}
                              >
                                <i class='icon-monitor icon-legend' />
                              </div>
                            ),
                          }}
                          always={true}
                          arrow={false}
                          boundary='body'
                          disabled={!this.showLegend}
                          isShow={this.showLegend}
                          offset={{ crossAxis: 90, mainAxis: 10 }}
                          placement='top'
                          renderType='auto'
                          theme='dark common-table'
                          trigger='manual'
                          zIndex={100}
                        />
                        <span class='failure-topo-graph-line' />
                        <div class='failure-topo-graph-zoom-slider'>
                          <div
                            class={['failure-topo-graph-setting', { disabled: this.isPlay }]}
                            onClick={this.handleUpdateZoom.bind(this, -2)}
                          >
                            <i class='icon-monitor icon-minus-line' />
                          </div>
                          <Slider
                            class='slider'
                            v-model={this.zoomValue}
                            disable={this.isPlay}
                            maxValue={20}
                            minValue={2}
                            onChange={this.handleZoomChange}
                            onUpdate:modelValue={this.handleZoomChange}
                          />
                          <div
                            class={['failure-topo-graph-setting', { disabled: this.isPlay }]}
                            onClick={this.handleUpdateZoom.bind(this, 2)}
                          >
                            <i class='icon-monitor icon-plus-line' />
                          </div>
                        </div>
                        <span class='failure-topo-graph-line' />
                        <div
                          class={['failure-topo-graph-proportion', { disabled: this.isPlay }]}
                          v-bk-tooltips={{ content: this.t('重置比例'), boundary: this.wrapRef, zIndex: 999999 }}
                          onClick={this.handleResetZoom}
                        >
                          <i class='icon-monitor icon-mc-restoration-ratio' />
                        </div>
                      </div>
                    </>
                  )}
                </div>
                {this.showResourceGraph && !this.isPlay && (
                  <ResourceGraph
                    ref='resourceGraphRef'
                    entityId={this.nodeEntityId}
                    entityName={this.nodeEntityName}
                    modelData={this.topoRawDataCache.complete}
                    resourceNodeId={this.resourceNodeId}
                    onCollapseResource={this.handleCollapseChange}
                    onHideToolTips={this.handleHideTooltips}
                    onViewService={this.handleViewServiceFromResource}
                  />
                )}
                {this.showServiceOverview && !this.isPlay && (
                  <FailureTopoDetail
                    edge={this.edgeDetail}
                    isClickEdgeItem={this.isClickEdgeItem}
                    linkedEdges={this.curLinkedEdges}
                    model={this.nodeDetail}
                    refreshTime={this.refreshTime}
                    showServiceOverview={this.showServiceOverview}
                    showViewResource={this.showViewResource}
                    type={this.detailType}
                    onClearHighlightEdge={this.setHighlightEdge.bind(this)}
                    onCollapseService={this.handleCollapseChange}
                    onFeedBack={this.handleFeedBack}
                    onHighlightEdge={this.handleHighlightEdge}
                    onToDetail={this.handleToDetail}
                    onToDetailSlider={this.handleToDetailSlider}
                    onToDetailTab={this.handleToDetailTab}
                    onToTracePage={this.goToTracePage}
                  />
                )}
              </div>
            </Loading>
          </>
        )}
        <FeedbackCauseDialog
          data={this.feedbackModel}
          visible={this.feedbackCauseShow}
          onEditSuccess={this.handleFeedBackChange}
          onRefresh={this.refresh}
          onUpdate:isShow={(val: boolean) => {
            this.feedbackCauseShow = val;
          }}
        />
        <div style='display: none'>
          <FailureTopoTooltips
            ref='tooltipCompRef'
            edge={this.tooltipsEdge}
            model={this.tooltipsModel}
            type={this.tooltipsType}
            onHide={this.handleHideTooltips}
            onViewResource={this.handleViewResource}
            onViewService={this.handleViewServiceFromTopo}
          />
        </div>
        <div
          id='combo-label-tooltip'
          class='combo-label-tooltip'
        />
        <div
          id='node-detail-tips'
          class='node-detail-tips'
        />
      </div>
    );
  },
});
