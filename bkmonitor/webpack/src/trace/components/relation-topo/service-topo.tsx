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

import { computed, defineComponent, nextTick, ref, watch } from 'vue';

import { Edge, ViewportTransform, VueFlow, useVueFlow } from '@vue-flow/core';
import { MiniMap } from '@vue-flow/minimap';
import { Popover } from 'bkui-vue';

import { useLayout, useScreenshot } from '../../hooks/vue-flow-hooks';
import GraphTools from '../../plugins/charts/flame-graph/graph-tools/graph-tools';
import ViewLegend from '../../plugins/charts/view-legend/view-legend';
import { useTraceStore } from '../../store/modules/trace';
import EdgeLabelCustom from './edge-label-custom';

import './service-topo.scss';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/minimap/dist/style.css';

enum ENodeType {
  component = 'component',
  interface = 'interface',
  service = 'service',
}

export default defineComponent({
  name: 'ServiceTopo',
  setup() {
    // hooks
    const store = useTraceStore();
    const { fitView, setViewport, getViewport, onEdgeClick, findEdge, vueFlowRef } = useVueFlow();
    const { layout } = useLayout();
    const { capture } = useScreenshot();

    // dom
    const graphContainer = ref<Element>();
    const topoGraphContent = ref<Element>();

    // data
    const emptyText = ref<string>('加载中...');
    const empty = ref<boolean>(false);
    const serviceTopoData = computed(() => store.traceData.streamline_service_topo);
    // 当前选中节点
    const selectedNodeKey = ref('');
    /** 是否显示耗时 */
    const isShowDuration = computed(() => store.traceViewFilters.includes('duration'));

    // 拓扑图数据
    const nodes = ref([]);
    const edges = ref<Edge[]>([]);
    /** 是否显示缩略图 */
    const showThumbnail = ref<boolean>(true);
    /** 是否显示图例 */
    const showLegend = ref<boolean>(false);
    // 缩放比例
    const zoomValue = ref(80);
    const graphToolsRect = ref({ width: 0, height: 0 });

    watch(
      () => serviceTopoData.value,
      data => {
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
            spans: item.spans || [],
          },
          label: item.num_of_operations > 1 ? String(item.num_of_operations) : '',
          labelBgPadding: [4, 0] as [number, number],
          style: {
            stroke: '#C4C6CC',
            strokeWidth: 1,
          },
          markerEnd: 'custom-marker-arrowhead',
        }));
      },
      { immediate: true }
    );

    /**
     * @description 自动布局节点位置
     * @param direction
     */
    function layoutGraph(direction: string) {
      nodes.value = layout(nodes.value, edges.value, direction);
      nextTick(() => {
        fitView();
        const wrapWidth = graphContainer.value.clientWidth;
        const positionXs = nodes.value.map(item => item.position.x);
        const positionXSort = positionXs.sort((a, b) => a - b);
        const x =
          wrapWidth / 2 -
          ((positionXSort[positionXSort.length - 1] - positionXSort[0]) / 2 + positionXSort[0]) +
          positionXSort[0] -
          32;
        setViewport({
          zoom: (zoomValue.value + 20) / 100,
          x: x,
          y: 16,
        });
        /** 边点击事件 */
        onEdgeClick(({ edge }) => {
          resetEdgeStyle();
          edge.animated = true;
          edge.markerEnd = 'custom-marker-arrowhead--selected';
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
      capture(vueFlowRef.value, { shouldDownload: true });
    }
    /**
     *  @description 视窗变化结束
     * @param value
     */
    function handleViewportChangeEnd(value: ViewportTransform) {
      zoomValue.value = Math.round(value.zoom * 100) - 20;
    }

    /**
     * @description 节点点击事件
     * @param node
     */
    function handleNodeClick(node) {
      selectedNodeKey.value = node.data.key;
      setEdgeSelected([node.data.key]);
    }

    function setEdgeSelected(targetKeys: string[]) {
      resetEdgeStyle();
      const sets = new Set(targetKeys);
      edges.value.forEach(e => {
        const edge = findEdge(e.id);
        const has = sets.has(e.target);
        edge.selected = has;
        edge.animated = has;
        if (has) {
          edge.markerEnd = 'custom-marker-arrowhead--selected';
        }
      });
    }

    /** 重置所有边的样式 */
    function resetEdgeStyle() {
      edges.value.forEach(e => {
        const edge = findEdge(e.id);
        edge.animated = false;
        edge.markerEnd = 'custom-marker-arrowhead';
      });
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
      graphToolsRect,
      isShowDuration,
      selectedNodeKey,
      layoutGraph,
      handleGraphZoom,
      handleShowLegend,
      handleShowThumbnail,
      downloadAsImage,
      handleViewportChangeEnd,
      handleNodeClick,
    };
  },

  render() {
    return (
      <div class='service-topo-component'>
        {this.empty && <div class='empty-chart'>{this.emptyText}</div>}
        <Popover
          width={this.graphToolsRect.width}
          height={this.graphToolsRect.height}
          extCls='topo-thumbnail-popover'
          allowHtml={false}
          arrow={false}
          boundary={'parent'}
          content={this.topoGraphContent}
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
                ></polyline>
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
                ></polyline>
              </marker>
            </defs>
          </svg>
          <VueFlow
            edges={this.edges}
            maxZoom={1.2}
            minZoom={0.2}
            nodes={this.nodes}
            onNodesInitialized={() => this.layoutGraph('TB')}
            onViewportChangeEnd={this.handleViewportChangeEnd}
          >
            {(() => ({
              [`node-${ENodeType.interface}`]: data => (
                <div
                  style={{
                    borderLeftColor: data.data.color,
                  }}
                  class={['node-interface', { selected: data.data.key === this.selectedNodeKey }]}
                  onClick={() => this.handleNodeClick(data)}
                >
                  <div
                    style={{
                      'background-image': `url(${data.data.icon})`,
                    }}
                    class='node-interface-icon'
                  ></div>
                  <div class='node-interface-name'>{data.data.display_name}</div>
                </div>
              ),
              [`node-${ENodeType.service}`]: data => (
                <div
                  class={['node-service', { selected: data.data.key === this.selectedNodeKey }]}
                  onClick={() => this.handleNodeClick(data)}
                >
                  <div class='node-service-top'>
                    <div
                      style={{
                        'background-image': `url(${data.data.icon})`,
                      }}
                      class='node-service-icon'
                    ></div>
                  </div>
                  <div class='node-service-bottom'>{data.data.display_name}</div>
                </div>
              ),
              [`node-${ENodeType.component}`]: data => (
                <div
                  class={['node-service', { selected: data.data.key === this.selectedNodeKey }]}
                  onClick={() => this.handleNodeClick(data)}
                >
                  <div class='node-service-top'>
                    <div
                      style={{
                        'background-image': `url(${data.data.icon})`,
                      }}
                      class='node-service-icon'
                    ></div>
                  </div>
                  <div class='node-service-bottom'>{data.data.display_name}</div>
                </div>
              ),
              'edge-label-custom': edgeProps => (
                <EdgeLabelCustom
                  {...edgeProps}
                  isShowDuration={this.isShowDuration}
                ></EdgeLabelCustom>
              ),
              default: () => [
                this.showThumbnail && (
                  <MiniMap
                    width={225}
                    height={148}
                    maskColor={'#ffffff'}
                    pannable={true}
                  ></MiniMap>
                ),
              ],
            }))()}
          </VueFlow>
        </div>
      </div>
    );
  },
});
