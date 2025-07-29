/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { defineComponent, nextTick, onBeforeUnmount, ref, shallowRef, Teleport, watch } from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Exception, Popover, ResizeLayout } from 'bkui-vue';
import { traceDiagram } from 'monitor-api/modules/apm_trace';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import { getSingleDiffColor } from '../../../utils/compare';
import GraphTools from '../flame-graph/graph-tools/graph-tools';
import ViewLegend from '../view-legend/view-legend';
import FlameFilterList from './flame-filter-list';
import {
  type BaseDataType,
  type IAxisRect,
  type IBaseTraceInfo,
  type ICommonMenuItem,
  type IContextMenuRect,
  type IOtherData,
  type ITipsDetail,
  type IZoomRect,
  CommonMenuList,
  RootId,
} from './types';
import { FlameChart } from './use-flame';

import type { HierarchyNode } from 'd3-hierarchy';

import './flame-graph.scss';
// 8b30e0f74e96efe07bb033c2d74e806
const usFormat = getValueFormat('µs');
const boundryBody = true;
const MaxScale = 1000;
const MinScale = 100;
const scaleStep = 20;
const paddingLeft = 6;

export default defineComponent({
  name: 'FlameGraph',
  props: {
    traceId: {
      type: String,
      required: true,
    },
    appName: {
      type: String,
      required: true,
    },
    diffTraceId: {
      type: String,
      default: '',
    },
    filterKeywords: {
      type: Array as () => string[],
      default: () => [] as string[],
    },
    textDirection: {
      type: String as () => 'ltr' | 'rtl',
      default: 'ltr',
    },
    filters: {
      type: Array,
      required: false,
    },
  },
  emits: ['update:loading', 'showSpanDetail', 'diffTraceSuccess'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const chartRef = ref<HTMLElement>(null);
    const wrapperRef = ref<HTMLElement>(null);
    const flameToolsPopoverContent = ref<HTMLElement>(null);
    const showException = ref(false);
    const tipDetail = shallowRef<ITipsDetail>({});
    const contextMenuRect = ref<IContextMenuRect>({
      left: 0,
      top: 0,
      spanId: '',
      spanName: '',
    });
    const axisRect = shallowRef<IAxisRect>({ left: 0, bottom: 0, title: '', visibility: 'hidden' });
    const zoomRect = ref<IZoomRect>({ left: 0, width: 0 });
    const graphToolsRect = ref<Partial<DOMRect>>({ left: 0, top: 0, width: 120, height: 300 });
    /** 是否显示图例 */
    const showLegend = ref(false);
    let graphInstance: FlameChart<BaseDataType> = null;
    let svgRect: Partial<DOMRect> = {};
    const filterData = shallowRef();
    const filterMaxHeight = ref(0);
    // 放大系数
    const scaleValue = ref(100);
    watch(
      () => props.textDirection,
      () => {
        graphInstance?.setTextDirection(props.textDirection);
      }
    );
    watch(
      [() => props.traceId, () => props.appName, () => props.diffTraceId, () => props.filters],
      debounce(16, async () => {
        filterData.value = null;
        contextMenuRect.value.left = -1;
        emit('update:loading', true);
        showException.value = false;
        try {
          const data = await traceDiagram(
            {
              trace_id: props.traceId,
              app_name: props.appName,
              diagram_type: 'flamegraph',
              show_attrs: 0,
              diff_trace_id: props.diffTraceId,
              displays: props.filters.filter(item => item !== 'duration'),
            },
            {
              needCancel: true,
            }
          ).catch(() => false);
          if (data?.diagram_data?.flame_data?.length) {
            if (props.diffTraceId) {
              emit('diffTraceSuccess');
            }
            showException.value = false;
            await nextTick();
            filterData.value = data.diagram_data.aggregations_data ?? null;
            initScale();
            filterMaxHeight.value = wrapperRef.value?.getBoundingClientRect().height;
            if (!chartRef.value?.clientWidth) return;
            graphInstance = new FlameChart(
              initGraphData(data.diagram_data.flame_data, data.trace_info),
              {
                w: chartRef.value.clientWidth - (filterData.value ? 350 : 0) - paddingLeft * 2,
                c: 20,
                minHeight: window.innerHeight - wrapperRef.value?.getBoundingClientRect().top - 40,
                direction: props.textDirection,
                keywords: props.filterKeywords,
                getFillColor: (d: BaseDataType) => {
                  if (d.id === RootId) return 'rgb(223,133,32)';
                  return props.diffTraceId && d?.diff_info ? getSingleDiffColor(d.diff_info) : '';
                },
                onDetail: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c: IOtherData) => {
                  if (!d) {
                    tipDetail.value = {};
                    return;
                  }
                  const { text, suffix } = usFormat(d.data.end_time - d.data.start_time);
                  let diffDuration = '';
                  let diffValue = 0;
                  if (props.diffTraceId && d.data?.diff_info) {
                    const { text: diffText, suffix: diffSuffix } = usFormat(d.data.diff_info.comparison);
                    diffDuration = diffText + diffSuffix;
                    diffValue =
                      d.data.diff_info.comparison === 0 || d.data.diff_info.mark === 'unchanged'
                        ? 0
                        : +(
                            ((d.data.diff_info.baseline - d.data.diff_info.comparison) * 100) /
                            d.data.diff_info.comparison
                          ).toFixed(2);
                  }
                  let axisLeft = e.pageX - (boundryBody ? 0 : svgRect.left);
                  let axisTop = e.pageY - (boundryBody ? 0 : svgRect.top);
                  if (axisLeft + 240 > window.innerWidth) {
                    axisLeft = axisLeft - 220 - 16;
                  } else {
                    axisLeft = axisLeft + 16;
                  }
                  if (axisTop + 120 > window.innerHeight) {
                    axisTop = axisTop - 120;
                  } else {
                    axisTop = axisTop;
                  }
                  tipDetail.value = {
                    left: axisLeft,
                    top: axisTop,
                    id: d.data.id,
                    title: d.data.name,
                    proportion: (((d.data.end_time - d.data.start_time) * 100) / c.rootValue)
                      .toFixed(4)
                      .replace(/[0]+$/g, ''),
                    duration: text + suffix,
                    diffDuration,
                    diffValue,
                    mark: d.data.diff_info?.mark,
                  };
                },
                onContextMenu: (e: MouseEvent, d: HierarchyNode<BaseDataType>) => {
                  let axisLeft = e.pageX - svgRect.x;
                  if (axisLeft + 180 > svgRect.width) {
                    axisLeft = axisLeft - 160 - 16;
                  } else {
                    axisLeft = axisLeft + 16;
                  }
                  const top = e.pageY - svgRect.y + 16;
                  tipDetail.value = {};
                  contextMenuRect.value = { left: axisLeft, top, spanId: d.data.id, spanName: d.data.name };
                },
                onMouseMove: (e: MouseEvent, c: IOtherData) => {
                  const axisLeft = e.pageX - (boundryBody ? 0 : svgRect.left);
                  const { text, suffix } = usFormat(c.xAxisValue);
                  axisRect.value = {
                    left: axisLeft,
                    top: svgRect.top - paddingLeft,
                    bottom: svgRect.bottom + paddingLeft,
                    title: text + suffix,
                    visibility: axisLeft < svgRect.x || axisLeft > svgRect.width + svgRect.x ? 'hidden' : 'visible',
                  };
                },
                onMouseOut: () => {
                  axisRect.value = { left: 0, title: '', visibility: 'hidden' };
                  tipDetail.value = {};
                },
                onMouseDown: (event: MouseEvent) => {
                  function mousemove(e: MouseEvent) {
                    const width = e.pageX - event.pageX;
                    if (width > 0) {
                      zoomRect.value = {
                        left: Math.min(event.pageX - svgRect.x, svgRect.width) + paddingLeft,
                        width: Math.min(width, svgRect.width - event.pageX + svgRect.x),
                      };
                    } else {
                      zoomRect.value = {
                        left: Math.max(e.pageX - svgRect.x, 0) + paddingLeft,
                        width: Math.min(Math.abs(width), event.pageX - svgRect.x),
                      };
                    }
                  }
                  function mouseup() {
                    initScale();
                    graphInstance.timeZoomGraph(zoomRect.value.left - paddingLeft, zoomRect.value.width);
                    document.removeEventListener('mousemove', mousemove);
                    document.removeEventListener('mouseup', mouseup);
                    zoomRect.value = {
                      left: 0,
                      width: 0,
                    };
                  }
                  document.addEventListener('mousemove', mousemove);
                  document.addEventListener('mouseup', mouseup);
                },
              },
              chartRef.value
            );
            setTimeout(() => {
              setSvgRect();
              filterMaxHeight.value = wrapperRef.value?.getBoundingClientRect().height;
              addListener(wrapperRef.value!, handleResize);
            }, 750);
            showException.value = false;
            nextTick(() => {
              emit('update:loading', false);
            });
            return;
          }
          showException.value = true;
          emit('update:loading', false);
        } catch (e) {
          console.error(e);
          emit('update:loading', false);
          showException.value = true;
        }
      }),
      { immediate: true }
    );
    watch(
      () => props.filterKeywords,
      () => {
        graphInstance?.filterGraph(props.filterKeywords);
      }
    );
    onBeforeUnmount(() => {
      wrapperRef.value && removeListener(wrapperRef.value!, handleResize);
      emit('update:loading', false);
    });
    /**
     *
     * @param data flame graph data
     * @param traceInfo trace info
     * @returns flame graph data
     * @description: add root node
     */
    function addRootNode(data: BaseDataType[], traceInfo: IBaseTraceInfo): BaseDataType {
      let minStartTime = traceInfo?.trace_start_time ?? 0;
      let minEndTime = traceInfo?.trace_start_time + traceInfo?.trace_duration ?? 0;
      if (!traceInfo) {
        minStartTime = Math.min(...data.map(item => item.start_time));
        minEndTime = Math.max(...data.map(item => item.end_time));
      }
      const root = {
        name: 'total',
        id: RootId,
        start_time: minStartTime,
        end_time: minEndTime,
      };
      return {
        ...root,
        children: data,
      };
    }
    /**
     *
     * @param data flame graph data
     * @param traceInfo trace info
     * @returns flame graph data
     */
    function initGraphData(data: BaseDataType[], traceInfo: IBaseTraceInfo) {
      const main = addRootNode(
        data.filter(item => !item.last_sibling_id),
        traceInfo
      );
      const threads = data.filter(item => item.last_sibling_id);
      return {
        main,
        threads,
      };
    }
    /**
     * @description: set svg rect
     */
    function setSvgRect() {
      svgRect = chartRef.value.querySelector('svg').getBoundingClientRect();
      graphToolsRect.value = {
        left: svgRect.x + 4,
      };
    }
    /**
     * @description: resize graph
     */
    function handleResize() {
      if (!wrapperRef.value) return;
      const rect = wrapperRef.value.getBoundingClientRect();
      const { width } = rect;
      graphInstance.resizeGraph(width - 12, window.innerHeight - rect.top - 40);
      filterMaxHeight.value = rect.height;
      setSvgRect();
    }
    /**
     * @description: click context menu
     * @param {ICommonMenuItem} item menu item
     * @return {*}
     */
    function handleContextMenuClick(item: ICommonMenuItem) {
      contextMenuRect.value.left = -1;
      if (item.id === 'span') {
        return contextMenuRect.value.spanId && emit('showSpanDetail', contextMenuRect.value.spanId);
      }
      if (item.id === 'reset') {
        initScale();
        return graphInstance?.resetGraph();
      }
      if (item.id === 'highlight') {
        graphInstance.highlightNode(contextMenuRect.value.spanName);
      }
    }
    /**
     * @description: click wrapper to hide context menu
     */
    function handleClickWrapper() {
      contextMenuRect.value.left = -1;
    }
    /**
     *
     * @param v scale value
     * @description: scale value change
     */
    function handlesSaleValueChange(v: number) {
      scaleValue.value = v;
      graphInstance.scaleGraph(v);
    }
    /**
     * @description: store image
     */
    function handleStoreImg() {
      const svgDom = chartRef.value.querySelector('svg');
      convertSvgToPngAndDownload(svgDom, `${props.appName}_${props.traceId}.png`);
    }
    /**
     *
     * @param svgElement svg element
     * @param fileName file name
     * @description: convert svg to png and download
     */
    function convertSvgToPngAndDownload(svgElement: SVGSVGElement, fileName: string) {
      // 创建一个新的canvas元素
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');

      // 获取SVG DOM的尺寸
      const svgRect = svgElement.getBoundingClientRect();
      const { width } = svgRect;
      const { height } = svgRect;

      // 设置canvas的尺寸与SVG相同
      canvas.width = width;
      canvas.height = height;

      // 创建一个新的Image元素
      const img = new Image();

      // 将SVG转换为DataURL
      const svgString = new XMLSerializer().serializeToString(svgElement);
      const svgDataUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`;

      // 加载SVG图像
      img.onload = function () {
        // 在canvas上绘制SVG图像
        ctx.drawImage(img, 0, 0, width, height);

        // 将canvas转换为PNG图像的数据URL
        const dataURL = canvas.toDataURL('image/png');

        // 创建下载链接
        const downloadLink = document.createElement('a');
        downloadLink.href = dataURL;

        // 设置下载链接的属性
        downloadLink.download = fileName; // 设置文件名
        downloadLink.target = '_blank'; // 设置在新标签页中打开

        // 模拟点击下载链接以下载PNG图像
        downloadLink.click();
      };

      // 加载SVG图像
      img.src = svgDataUrl;
    }

    /**
     * @description: init scale value
     */
    function initScale() {
      scaleValue.value = 100;
    }
    /** 展示图例 */
    const handleShowLegend = () => {
      showLegend.value = !showLegend.value;
    };
    return {
      chartRef,
      wrapperRef,
      tipDetail,
      zoomRect,
      axisRect,
      filterMaxHeight,
      filterData,
      graphToolsRect,
      scaleValue,
      showException,
      contextMenuRect,
      handleContextMenuClick,
      handleClickWrapper,
      handleStoreImg,
      handlesSaleValueChange,
      flameToolsPopoverContent,
      showLegend,
      handleShowLegend,
      t,
    };
  },
  render() {
    if (this.showException)
      return (
        <Exception
          description={this.t('暂无数据')}
          type='empty'
        />
      );
    return (
      <ResizeLayout
        style='height: 100%'
        class={this.filterData ? '' : 'hide-aside'}
        initialDivide={this.filterData ? '350px' : '0px'}
        placement='right'
      >
        {{
          main: () => (
            <div
              ref='wrapperRef'
              class='flame-graph-wrapper'
              tabindex={1}
              onBlur={this.handleClickWrapper}
              onClick={this.handleClickWrapper}
            >
              <div
                ref='chartRef'
                class='flame-graph'
              />
              <Teleport to='body'>
                <div
                  style={{
                    left: `${this.tipDetail.left}px`,
                    top: `${this.tipDetail.top + 16}px`,
                    display: this.tipDetail.title ? 'block' : 'none',
                  }}
                  class='flame-graph-tips'
                >
                  {this.tipDetail.title && [
                    <div class='funtion-name'>{this.tipDetail.title}</div>,
                    <table class='tips-table'>
                      {this.diffTraceId && (
                        <thead>
                          <th />
                          <th>{this.t('当前')}</th>
                          {this.tipDetail.id !== RootId && [<th>{this.t('参照')}</th>, <th>{this.t('差异')}</th>]}
                        </thead>
                      )}
                      <tbody>
                        {!this.diffTraceId && (
                          <tr>
                            <td>{this.t('占比')}</td>
                            <td>{this.tipDetail.proportion}%</td>
                          </tr>
                        )}
                        <tr>
                          <td>{this.t('耗时')}</td>
                          <td>{this.tipDetail.duration}</td>
                          {this.diffTraceId &&
                            this.tipDetail.id !== RootId && [
                              <td>{this.tipDetail.diffDuration ?? '--'}</td>,
                              <td>
                                {this.tipDetail.mark === 'added' ? (
                                  <span class='tips-added'>{this.tipDetail.mark}</span>
                                ) : (
                                  `${this.tipDetail.diffValue}%`
                                )}
                              </td>,
                            ]}
                        </tr>
                      </tbody>
                    </table>,
                    <div class='tips-info'>
                      <span class='icon-monitor icon-mc-mouse tips-info-icon' />
                      {this.t('鼠标右键有更多菜单')}
                    </div>,
                  ]}
                </div>
              </Teleport>
              <ul
                style={{
                  left: `${this.contextMenuRect.left}px`,
                  top: `${this.contextMenuRect.top}px`,
                  visibility: this.contextMenuRect.left > 0 ? 'visible' : 'hidden',
                }}
                class='flame-graph-menu'
              >
                {CommonMenuList.map(item => (
                  <li
                    key={item.id}
                    class='menu-item'
                    onClick={() => this.handleContextMenuClick(item)}
                  >
                    <i class={`menu-item-icon icon-monitor ${item.icon}`} />
                    <span class='menu-item-text'>{item.name}</span>
                  </li>
                ))}
              </ul>
              <Teleport to='body'>
                <div
                  style={{
                    left: `${this.axisRect.left || 0}px`,
                    top: `${this.axisRect.top || 0}px`,
                    bottom: `${this.axisRect.bottom || 0}px`,
                    visibility: this.axisRect.visibility,
                  }}
                  class='flame-graph-axis'
                >
                  <span class='axis-label'>{this.axisRect.title}</span>
                </div>
              </Teleport>
              <div
                style={{
                  left: `${this.zoomRect?.left || 0}px`,
                  width: `${this.zoomRect?.width || 0}px`,
                }}
                class='flame-graph-zoom'
              />
              {/* <GraphTools
                style={{
                  left: `${this.graphToolsRect.left}px`,
                  display: this.graphToolsRect.left > 0 ? 'flex' : 'none'
                }}
                scaleValue={this.scaleValue}
                maxScale={MaxScale}
                minScale={MinScale}
                scaleStep={scaleStep}
                showThumbnail={false}
                onStoreImg={this.handleStoreImg}
                onScaleChange={this.handlesSaleValueChange}
              /> */}
              <Popover
                width={this.graphToolsRect.width}
                height={this.graphToolsRect.height}
                extCls='flame-graph-tools-popover'
                allowHtml={false}
                arrow={false}
                boundary={'parent'}
                content={this.flameToolsPopoverContent}
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
                      style={{
                        left: `${this.graphToolsRect.left}px`,
                        display: this.graphToolsRect.left > 0 ? 'flex' : 'none',
                      }}
                      class='topo-graph-tools'
                      legendActive={this.showLegend}
                      maxScale={MaxScale}
                      minScale={MinScale}
                      scaleStep={scaleStep}
                      scaleValue={this.scaleValue}
                      showThumbnail={false}
                      onScaleChange={this.handlesSaleValueChange}
                      onShowLegend={this.handleShowLegend}
                      onStoreImg={this.handleStoreImg}
                    />
                  ),
                  content: () => (
                    <div
                      ref='flameToolsPopoverContent'
                      class='flame-tools-popover-content'
                    >
                      <ViewLegend />
                    </div>
                  ),
                }}
              </Popover>
            </div>
          ),
          aside: () => (
            <FlameFilterList
              style={{ display: this.filterData ? 'block' : 'none' }}
              class='flame-graph-aside'
              data={this.filterData}
              maxHeight={this.filterMaxHeight}
            />
          ),
        }}
      </ResizeLayout>
    );
  },
});
