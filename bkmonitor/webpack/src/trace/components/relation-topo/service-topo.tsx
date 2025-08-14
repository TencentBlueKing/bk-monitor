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

import { type PropType, defineComponent, nextTick, ref, watch } from 'vue';

import { type Edge, type ViewportTransform, useVueFlow, VueFlow } from '@vue-flow/core';
import { Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { random } from 'monitor-common/utils';

import { useLayout, useScreenshot } from '../../hooks/vue-flow-hooks';
import GraphTools from '../../plugins/charts/flame-graph/graph-tools/graph-tools';
import ViewLegend from '../../plugins/charts/view-legend/view-legend';
import { useTraceStore } from '../../store/modules/trace';
import EdgeLabelCustom from './edge-label-custom';
import ServiceTopoMiniMap from './service-topo-mini-map';

import type { IServiceSpanListItem } from '../../typings/trace';

import './service-topo.scss';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
enum ENodeType {
  component = 'component',
  interface = 'interface',
  service = 'service',
}
interface IServiceTopoData {
  edges: {
    key: string;
    num_of_operations: number;
    source: string;
    spans: IServiceSpanListItem[];
    target: string;
  }[];
  nodes: {
    display_name: string;
    key: string;
    node_type: ENodeType;
    spans: IServiceSpanListItem[];
  }[];
}

export default defineComponent({
  name: 'ServiceTopo',
  props: {
    serviceTopoData: {
      type: Object as PropType<IServiceTopoData>,
      default: () => null,
    },
    isShowDuration: {
      type: Boolean,
      default: false,
    },
    classify: {
      type: Object as PropType<Record<string, string>>,
      default: () => null,
    },
  },
  emits: ['clickItem'],
  setup(props, { emit }) {
    const store = useTraceStore();
    // hooks
    const { setViewport, fitView, getViewport, onEdgeClick, findEdge, vueFlowRef, onPaneClick, getSelectedEdges } =
      useVueFlow();
    const { layout } = useLayout();
    const { capture } = useScreenshot();

    // dom
    const graphContainer = ref<Element>();
    const topoGraphContent = ref<Element>();
    const emptyText = ref<string>('加载中...');
    const empty = ref<boolean>(true);
    // 当前选中节点
    const selectedNodeKey = ref('');

    // 拓扑图数据
    const nodes = ref([]);
    const edges = ref<Edge[]>([]);
    /** 是否显示缩略图 */
    const showThumbnail = ref<boolean>(true);
    /** 是否显示图例 */
    const showLegend = ref<boolean>(false);
    // 缩放比例
    const zoomValue = ref(80);
    /** 缩放倍数 */
    const scale = ref(1);

    const vueFlowKey = ref(random(8));

    const miniMapWrapWidth = 225;
    const miniMapWrapHeight = 148;

    watch(
      () => props.serviceTopoData,
      data => {
        if (!data) {
          return;
        }
        empty.value = false;
        nodes.value = data.nodes.map(item => ({
          id: item.key,
          type: item.node_type,
          position: { x: 0, y: 0 },
          data: {
            ...item,
          },
        }));
        edges.value = data.edges.map(item => ({
          type: 'label-custom',
          id: item.key,
          source: item.source,
          target: item.target,
          data: {
            ...item,
          },
          selected: false,
          label: String(item.num_of_operations),
          labelBgPadding: [4, 0] as [number, number],
          style: {
            stroke: '#C4C6CC',
            strokeWidth: 1,
          },
          markerEnd: 'custom-marker-arrowhead',
        }));
        vueFlowKey.value = random(8);
      },
      { immediate: true }
    );

    watch(
      () => props.classify,
      classify => {
        const zoomUpdate = () => {
          nextTick(() => {
            const params = getViewport();
            zoomValue.value = zoomValueFormat(params.zoom);
          });
        };
        setTimeout(() => {
          if (classify) {
            selectedNodeKey.value = '';
            if (classify.type === 'service') {
              const filterValue = classify.filter_value;
              nodes.value.some(item => {
                if (item.id === filterValue) {
                  handleNodeClick(item);
                  fitView({
                    nodes: [item.id],
                  });
                  zoomUpdate();
                  return true;
                }
                return false;
              });
            } else if (classify.type === 'max_duration') {
              const filterValue = classify.filter_value;
              edges.value.some(item => {
                return item.data.spans.some(s => {
                  if (filterValue === s.duration) {
                    setEdgeSelected([item.id]);
                    handleEditSpanList(item.data.spans);
                    fitView({
                      nodes: [item.target],
                    });
                    zoomUpdate();
                    return true;
                  }
                  return false;
                });
              });
            } else if (classify.type === 'error') {
              // 从original_data 找出错误的span
              const errIdSet = new Set();
              store.traceData.original_data.forEach(item => {
                if (item?.status?.code === 2 && item.span_id) {
                  errIdSet.add(item.span_id);
                }
              });
              // 选中所有包含错误span的线
              const edgeSet = new Set();
              const selectedSpans = [];
              let targetKey = '';
              edges.value.forEach(item => {
                item.data.spans.forEach(s => {
                  if (errIdSet.has(s.span_id)) {
                    edgeSet.add(item.id);
                    selectedSpans.push(s);
                    if (!targetKey) {
                      targetKey = item.target;
                    }
                  }
                });
              });
              setEdgeSelected(Array.from(edgeSet) as string[]);
              handleEditSpanList(selectedSpans);
              if (targetKey) {
                fitView({
                  nodes: [targetKey],
                });
                zoomUpdate();
              }
            }
          }
        }, 100);
      }
    );

    /**
     * @description 格式化缩放值
     * @param value
     * @returns
     */
    function zoomValueFormat(value: number) {
      return Math.round(value * 100) - 20;
    }

    /**
     * @description 自动布局节点位置
     * @param direction
     */
    function layoutGraph(direction: string) {
      nodes.value = layout(nodes.value, edges.value, direction, 100);
      nextTick(() => {
        const wrapWidth = graphContainer.value.clientWidth;
        const rootX = nodes.value.filter(item => !!item?.data?.is_root)?.[0]?.position?.x || 0;
        const x = wrapWidth / 2 - rootX - 56;
        setViewport({
          x,
          y: 16,
          zoom: (zoomValue.value + 20) / 100,
        });

        const rootNode = nodes.value.find(item => item.data.is_root);
        const firstEdge = edges.value.find(item => item.source === rootNode?.id);
        if (firstEdge) {
          setEdgeSelected([firstEdge.id]);
          handleEditSpanList(firstEdge.data.spans);
        }

        /** 边点击事件 */
        onEdgeClick(({ edge }) => {
          selectedNodeKey.value = '';
          setEdgeSelected([edge.id]);
          handleEditSpanList(edge.data.spans);
          emit('clickItem', [edge.id]);
        });

        onPaneClick(() => {
          const ids = getSelectedEdges.value.map(item => item.id);
          nextTick(() => {
            setEdgeSelected(ids);
          });
        });
      });
    }

    /**
     * @description 处理缩放
     * @param ratio
     */
    function handleGraphZoom(ratio: number) {
      zoomValue.value = ratio;
      const params = getViewport();
      setViewport({
        ...params,
        zoom: (ratio + 20) / 100,
      });
    }
    /**
     * @description 图例显示隐藏
     */
    function handleShowLegend() {
      showLegend.value = !showLegend.value;
      showThumbnail.value = false;
    }
    /**
     * @description minimap 显示隐藏
     */
    function handleShowThumbnail() {
      showThumbnail.value = !showThumbnail.value;
      showLegend.value = false;
    }
    /**
     * @description 下载图片
     */
    function downloadAsImage() {
      if (!vueFlowRef.value) {
        console.warn('VueFlow element not found');
        return;
      }
      const fileName = `${dayjs.tz().format('YYYY-MM-DD HH:mm:ss')}`;
      capture(vueFlowRef.value, { shouldDownload: true, fileName });
    }
    /**
     *  @description 视窗变化结束
     * @param value
     */
    function handleViewportChangeEnd(value: ViewportTransform) {
      zoomValue.value = zoomValueFormat(value.zoom);
    }
    /**
     * 视口变化
     * @param value 视口变化参数
     */
    function handleViewportChange(value: ViewportTransform) {
      scale.value = value.zoom;
    }

    /**
     * @description 节点点击事件
     * @param node
     */
    function handleNodeClick(node, _e?: Event) {
      _e?.stopPropagation();
      selectedNodeKey.value = node.data.key;
      const edgesIds = edges.value.filter(e => e.target === node.data.key).map(e => e.id);
      setEdgeSelected(edgesIds);
      handleEditSpanList(node.data.spans);
    }

    function handleEditSpanList(spanList = []) {
      store.setServiceSpanList(spanList);
    }

    /**
     * 设置边的选中状态
     * @param ids 需要选中的边id
     */
    function setEdgeSelected(ids: string[] = []) {
      const sets = new Set(ids);
      edges.value.forEach(e => {
        const edge = findEdge(e.id);
        const has = sets.has(e.id);
        edge.selected = has;
        edge.animated = has;
        edge.markerEnd = has ? 'custom-marker-arrowhead--selected' : 'custom-marker-arrowhead';
      });
    }

    function handlePanelClick(edgeId: string) {
      selectedNodeKey.value = '';
      const spans = edges.value.find(item => item.id === edgeId)?.data?.spans || [];
      setEdgeSelected([edgeId]);
      handleEditSpanList(spans);
      emit('clickItem', [edgeId]);
    }
    function handleNodeClickProxy(node, _e?: Event) {
      handleNodeClick(node, _e);
      emit('clickItem', [node.data.key]);
    }

    return {
      emptyText,
      empty,
      graphContainer,
      nodes,
      edges,
      showThumbnail,
      showLegend,
      topoGraphContent,
      zoomValue,
      scale,
      selectedNodeKey,
      vueFlowKey,
      miniMapWrapWidth,
      miniMapWrapHeight,
      layoutGraph,
      handleGraphZoom,
      handleShowLegend,
      handleShowThumbnail,
      downloadAsImage,
      handleViewportChangeEnd,
      handleNodeClick,
      handleViewportChange,
      handlePanelClick,
      handleNodeClickProxy,
    };
  },

  render() {
    return (
      <div class='service-topo-component'>
        {this.empty && <div class='empty-chart'>{this.emptyText}</div>}
        <Popover
          extCls='topo-thumbnail-popover'
          allowHtml={false}
          arrow={false}
          boundary={'parent'}
          content={this.topoGraphContent as any}
          isShow={this.showLegend}
          placement='top-start'
          renderType='auto'
          theme='light'
          trigger='manual'
          zIndex={1001}
        >
          {{
            default: () => (
              <GraphTools
                class='topo-graph-tools'
                legendActive={this.showLegend}
                minScale={10}
                scaleStep={10}
                scaleValue={this.zoomValue}
                thumbnailActive={this.showThumbnail}
                onScaleChange={this.handleGraphZoom}
                onShowLegend={this.handleShowLegend}
                onShowThumbnail={this.handleShowThumbnail}
                onStoreImg={this.downloadAsImage}
              />
            ),
            content: () => (
              <div
                ref='topoGraphContent'
                class='topo-graph-content'
              >
                {this.showLegend && <ViewLegend />}
              </div>
            ),
          }}
        </Popover>
        <div
          ref='graphContainer'
          class='graph-container'
        >
          <svg
            style='position: absolute;'
            width='0'
            height='0'
          >
            <defs>
              <marker
                id='custom-marker-arrowhead'
                class='custom-marker-arrowhead'
                markerHeight='12.5'
                markerWidth='12.5'
                orient='auto'
                refX='0'
                refY='0'
                viewBox='-10 -10 20 20'
              >
                <polyline
                  fill='#626973'
                  points='-7.5,-6 0,0 -7.5,6 -7.5,-6'
                  stroke='#626973'
                  stroke-linecap='round'
                  stroke-linejoin='round'
                  stroke-width='1'
                />
              </marker>
              <marker
                id='custom-marker-arrowhead--selected'
                class='custom-marker-arrowhead--selected'
                markerHeight='12.5'
                markerWidth='12.5'
                orient='auto'
                refX='0'
                refY='0'
                viewBox='-10 -10 20 20'
              >
                <polyline
                  fill='#4ba0f3'
                  points='-7.5,-6 0,0 -7.5,6 -7.5,-6'
                  stroke='#4ba0f3'
                  stroke-linecap='round'
                  stroke-linejoin='round'
                  stroke-width='1'
                />
              </marker>
            </defs>
          </svg>
          <VueFlow
            key={this.vueFlowKey}
            edges={this.edges}
            maxZoom={1.2}
            minZoom={0.2}
            nodes={this.nodes}
            onNodesInitialized={() => this.layoutGraph('TB')}
            onViewportChange={this.handleViewportChange}
            onViewportChangeEnd={this.handleViewportChangeEnd}
          >
            {(() => ({
              [`node-${ENodeType.interface}`]: data => (
                <div
                  style={{
                    borderLeftColor: data.data.color,
                  }}
                  class={['node-interface', { selected: data.data.key === this.selectedNodeKey }]}
                  onClick={e => this.handleNodeClickProxy(data, e)}
                >
                  <div
                    style={{
                      'background-image': `url(${data.data.icon})`,
                    }}
                    class='node-interface-icon'
                  />
                  <div
                    class='node-interface-name'
                    title={data.data.display_name}
                  >
                    {data.data.display_name}
                  </div>
                </div>
              ),
              [`node-${ENodeType.service}`]: data => (
                <div
                  class={['node-service', { selected: data.data.key === this.selectedNodeKey }]}
                  onClick={e => this.handleNodeClickProxy(data, e)}
                >
                  <div class='node-service-top'>
                    <div
                      style={{
                        'background-image': `url(${data.data.icon})`,
                      }}
                      class='node-service-icon'
                    />
                  </div>
                  <div class='node-service-bottom'>{data.data.display_name}</div>
                </div>
              ),
              [`node-${ENodeType.component}`]: data => (
                <div
                  class={['node-service', { selected: data.data.key === this.selectedNodeKey }]}
                  onClick={e => this.handleNodeClickProxy(data, e)}
                >
                  <div class='node-service-top'>
                    <div
                      style={{
                        'background-image': `url(${data.data.icon})`,
                      }}
                      class='node-service-icon'
                    />
                  </div>
                  <div class='node-service-bottom'>{data.data.display_name}</div>
                </div>
              ),
              'edge-label-custom': edgeProps => (
                <EdgeLabelCustom
                  {...edgeProps}
                  isShowDuration={this.isShowDuration}
                  onPanelClick={this.handlePanelClick}
                />
              ),
              default: () => [
                this.showThumbnail && (
                  <ServiceTopoMiniMap
                    width={this.miniMapWrapWidth}
                    height={this.miniMapWrapHeight}
                  />
                ),
              ],
            }))()}
          </VueFlow>
        </div>
      </div>
    );
  },
});
