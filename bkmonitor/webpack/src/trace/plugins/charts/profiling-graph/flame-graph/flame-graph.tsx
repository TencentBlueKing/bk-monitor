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
import { computed, defineComponent, nextTick, onBeforeUnmount, ref, shallowRef, Teleport, toRaw, watch } from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Exception, Message, Popover } from 'bkui-vue';
import { query } from 'monitor-api/modules/apm_profile';
import { copyText } from 'monitor-common/utils/utils';
import { FlameChart } from 'monitor-ui/chart-plugins/plugins/profiling-graph/flame-graph/use-flame';
import {
  type ProfileDataUnit,
  parseProfileDataTypeValue,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/utils';
import {
  type BaseDataType,
  type IAxisRect,
  type ICommonMenuItem,
  type IContextMenuRect,
  type IOtherData,
  type ITipsDetail,
  type IZoomRect,
  CommonMenuList,
  RootId,
} from 'monitor-ui/chart-plugins/typings/flame-graph';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import { COMPARE_DIFF_COLOR_LIST, getSingleDiffColor } from '../../../../utils/compare';
import GraphTools from '../../flame-graph/graph-tools/graph-tools';
import ViewLegend from '../../view-legend/view-legend';

import type { HierarchyNode } from 'd3-hierarchy';

import '../../flame-graph-v2/flame-graph.scss';
import './flame-graph.scss';

const usFormat = getValueFormat('µs');
const boundryBody = true;
const MaxScale = 1000;
const MinScale = 100;
const scaleStep = 20;
const paddingLeft = 16;

export default defineComponent({
  name: 'FlameGraph',
  props: {
    data: {
      type: Object as () => BaseDataType,
      default: () => {},
    },
    appName: {
      type: String,
      default: '',
    },
    serviceName: {
      type: String,
      default: '',
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
    profileId: {
      type: String,
      default: '',
    },
    start: {
      type: Number,
      default: 0,
    },
    end: {
      type: Number,
      default: 0,
    },
    bizId: {
      type: [Number, String],
      default: '',
    },
    showGraphTools: {
      type: Boolean,
      default: true,
    },
    highlightId: {
      type: Number,
      default: -1,
    },
    highlightName: {
      type: String,
      default: '',
    },
    isCompared: {
      type: Boolean,
      default: false,
    },
    unit: {
      type: String as () => ProfileDataUnit,
      default: 'nanoseconds',
    },
  },
  emits: ['update:loading', 'showSpanDetail', 'diffTraceSuccess', 'updateHighlightId', 'updateHighlightName'],
  setup(props, { emit, expose }) {
    const { t } = useI18n();
    const chartRef = ref<HTMLElement>(null);
    const wrapperRef = ref<HTMLElement>(null);
    const flameToolsPopoverContent = ref<HTMLElement>(null);
    const showException = ref(true);
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
    let svgRect: DOMRect = null;
    // 放大系数
    const scaleValue = ref(100);
    const localIsCompared = ref(false);

    const diffPercentList = computed(() =>
      COMPARE_DIFF_COLOR_LIST.map(val => `${val.value > 0 ? '+' : ''}${val.value}%`)
    );

    watch(
      () => props.textDirection,
      () => {
        graphInstance?.setTextDirection(props.textDirection);
      }
    );
    watch(
      [() => props.data, props.appName],
      debounce(16, async () => {
        contextMenuRect.value.left = -1;
        emit('update:loading', true);
        showException.value = false;
        try {
          const { bizId, appName, serviceName, start, end, profileId } = props;
          const data = props.data
            ? props.data
            : ((
                await query(
                  {
                    bk_biz_id: bizId,
                    app_name: appName,
                    service_name: serviceName,
                    start,
                    end,
                    profile_id: profileId,
                    diagram_types: ['flamegraph'],
                  },
                  {
                    needCancel: true,
                  }
                ).catch(() => false)
              )?.flame_data ?? false);

          if (data) {
            if (props.diffTraceId) {
              emit('diffTraceSuccess');
            }
            showException.value = false;
            await nextTick();
            initScale();
            if (!chartRef.value?.clientWidth) return;
            localIsCompared.value = props.isCompared;
            graphInstance = new FlameChart(
              initGraphData(props.data ? toRaw(data) : data),
              {
                w: chartRef.value.clientWidth - paddingLeft * 2,
                c: 20,
                // minHeight: window.innerHeight - wrapperRef.value?.getBoundingClientRect().top - 40,
                minHeight: wrapperRef.value?.getBoundingClientRect().height - 40,
                direction: props.textDirection,
                keywords: props.filterKeywords,
                unit: props.unit,
                getFillColor: (d: BaseDataType) => {
                  if (d.id === RootId) return 'rgb(223,133,32)';
                  return props.isCompared && d?.diff_info ? getSingleDiffColor(d.diff_info) : '';
                },
                onDetail: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c: IOtherData) => {
                  if (!d) {
                    tipDetail.value = {};
                    return;
                  }
                  let detailsData;
                  let dataText;
                  const { value: dataValue, text: profileText } = parseProfileDataTypeValue(
                    d.data.value,
                    props.unit,
                    true
                  );
                  detailsData = dataValue;
                  dataText = profileText;

                  let diffData;
                  let diffValue = 0;
                  if (props.isCompared && d.data?.diff_info) {
                    const { value: diffProfileValue } = parseProfileDataTypeValue(
                      d.data.diff_info.comparison,
                      props.unit
                    );
                    diffData = diffProfileValue;
                    diffValue =
                      d.data.diff_info.comparison === 0 || d.data.diff_info.mark === 'unchanged'
                        ? 0
                        : d.data.diff_info.diff;
                    // +(
                    //     ((d.data.diff_info.baseline - d.data.diff_info.comparison) * 100) /
                    //     d.data.diff_info.comparison
                    //   ).toFixed(2);
                  }
                  let axisLeft = e.pageX - (boundryBody ? 0 : svgRect.left);
                  let axisTop = e.pageY - (boundryBody ? 0 : svgRect.top);
                  if (axisLeft + 360 > window.innerWidth) {
                    axisLeft = axisLeft - 340 - 16;
                  } else {
                    axisLeft = axisLeft + 16;
                  }
                  if (axisTop + 180 > window.innerHeight) {
                    axisTop = axisTop - 180;
                  }
                  tipDetail.value = {
                    left: axisLeft,
                    top: axisTop,
                    id: d.data.id,
                    title: d.data.name,
                    proportion: ((d.data.value * 100) / c.rootValue).toFixed(4).replace(/[0]+$/g, ''),
                    data: detailsData,
                    dataText,
                    diffData,
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
                onMouseDown: () => {
                  // function mousemove(e: MouseEvent) {
                  //   const width = e.pageX - event.pageX;
                  //   if (width > 0) {
                  //     zoomRect.value = {
                  //       left: Math.min(event.pageX - svgRect.x, svgRect.width) + paddingLeft,
                  //       width: Math.min(width, svgRect.width - event.pageX + svgRect.x)
                  //     };
                  //   } else {
                  //     zoomRect.value = {
                  //       left: Math.max(e.pageX - svgRect.x, 0) + paddingLeft,
                  //       width: Math.min(Math.abs(width), event.pageX - svgRect.x)
                  //     };
                  //   }
                  // }
                  // function mouseup() {
                  //   initScale();
                  //   graphInstance.timeZoomGraph(zoomRect.value.left - paddingLeft, zoomRect.value.width);
                  //   document.removeEventListener('mousemove', mousemove);
                  //   document.removeEventListener('mouseup', mouseup);
                  //   zoomRect.value = {
                  //     left: 0,
                  //     width: 0
                  //   };
                  // }
                  // document.addEventListener('mousemove', mousemove);
                  // document.addEventListener('mouseup', mouseup);
                },
              },
              chartRef.value
            );
            setTimeout(() => {
              setSvgRect();
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
    watch(
      () => props.highlightId,
      () => {
        graphInstance?.highlightNodeId(props.highlightId);
      }
    );
    watch(
      () => props.highlightName,
      () => {
        graphInstance?.highlightNode(props.highlightName);
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
     */
    function initGraphData(data: BaseDataType) {
      const main = data;
      const threads = [];
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
      // graphInstance.resizeGraph(width - 12, window.innerHeight - rect.top - 40);
      graphInstance.resizeGraph(width - 32, wrapperRef.value?.getBoundingClientRect().height - 40);
      setSvgRect();
    }
    /**
     * @description: click context menu
     * @param {ICommonMenuItem} item menu item
     * @return {*}
     */
    function handleContextMenuClick(item: ICommonMenuItem) {
      contextMenuRect.value.left = -1;
      if (item.id === 'copy') {
        let hasErr = false;
        copyText(contextMenuRect.value.spanName, (errMsg: string) => {
          Message({
            message: errMsg,
            theme: 'error',
          });
          hasErr = !!errMsg;
        });
        if (!hasErr) Message({ theme: 'success', message: t('复制成功') });

        return;
      }
      if (item.id === 'reset') {
        initScale();
        emit('updateHighlightId', -1);
        return graphInstance?.resetGraph();
      }
      if (item.id === 'highlight') {
        graphInstance.highlightNode(contextMenuRect.value.spanName);
        emit('updateHighlightName', contextMenuRect.value.spanName);
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
      convertSvgToPngAndDownload(svgDom, `${props.appName}.png`);
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
      img.onload = () => {
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

    expose({
      handleStoreImg,
    });

    return {
      chartRef,
      wrapperRef,
      tipDetail,
      zoomRect,
      axisRect,
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
      diffPercentList,
      localIsCompared,
      t,
    };
  },
  render() {
    if (this.showException)
      return (
        <Exception
          style='flex: 1'
          description={this.t('暂无数据')}
          type='empty'
        />
      );
    return (
      <div style='height: fit-content; flex: 1'>
        {this.localIsCompared && (
          <div class='profiling-compare-legend'>
            <span class='tag tag-new'>added</span>
            <div class='percent-queue'>
              {this.diffPercentList.map((item, index) => (
                <span
                  key={index}
                  class={`percent-tag tag-${index + 1}`}
                >
                  {item}
                </span>
              ))}
            </div>
            <span class='tag tag-removed'>removed</span>
          </div>
        )}
        <div
          key='wrapperRef'
          ref='wrapperRef'
          class={`flame-graph-wrapper profiling-flame-graph ${this.localIsCompared ? 'has-diff-legend' : ''}`}
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
                <div
                  key='funtion-name'
                  class='funtion-name'
                >
                  {this.tipDetail.title}
                </div>,
                <table
                  key='tips-table'
                  class='tips-table'
                >
                  {this.localIsCompared && (
                    <thead>
                      <th />
                      <th>{window.i18n.t('当前')}</th>
                      {this.tipDetail.id !== RootId && [
                        <th key='参照'>{window.i18n.t('参照')}</th>,
                        <th key='差异'>{window.i18n.t('差异')}</th>,
                      ]}
                    </thead>
                  )}
                  <tbody>
                    {!this.localIsCompared && (
                      <tr>
                        <td>{window.i18n.t('占比')}</td>
                        <td>{this.tipDetail.proportion}%</td>
                      </tr>
                    )}
                    <tr>
                      <td>{this.tipDetail.dataText}</td>
                      <td>{this.tipDetail.data}</td>
                      {this.localIsCompared &&
                        this.tipDetail.id !== RootId && [
                          <td key={1}>{this.tipDetail.diffData ?? '--'}</td>,
                          <td key={2}>
                            {this.tipDetail.mark === 'added' ? (
                              <span class='tips-added'>{this.tipDetail.mark}</span>
                            ) : (
                              `${((this.tipDetail.diffValue as number) * 100).toFixed(2)}%`
                            )}
                          </td>,
                        ]}
                    </tr>
                  </tbody>
                </table>,
                <div
                  key='tips-info'
                  class='tips-info'
                >
                  <span class='icon-monitor icon-mc-mouse tips-info-icon' />
                  {window.i18n.t('鼠标右键有更多菜单')}
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
          {this.showGraphTools && (
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
                    showLegend={false}
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
          )}
        </div>
      </div>
    );
  },
});
