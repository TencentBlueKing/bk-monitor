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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { copyText, Debounce } from 'monitor-common/utils/utils';
import {
  type ProfileDataUnit,
  parseProfileDataTypeValue,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/utils';

import { getValueFormat } from '../../../../monitor-echarts/valueFormats';
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
} from '../../../typings';
import { FlameChart } from './use-flame';
import { COMPARE_DIFF_COLOR_LIST, getSingleDiffColor } from './utils';

import type { HierarchyNode } from 'd3-hierarchy';

import './frame-graph.scss';

interface IFlameGraphEvent {
  onUpdateHighlightId: number;
  onUpdateHighlightName: string;
  onDiffTraceSuccess: () => void;
  onShowSpanDetail: () => void;
  onUpdateLoading: () => void;
}

interface IFlameGraphProps {
  appName?: string;
  bizId?: number;
  data: BaseDataType;
  diffTraceId?: string;
  end?: number;
  filterKeywords?: string[];
  highlightId?: number;
  highlightName?: string;
  isCompared?: boolean;
  profileId?: string;
  showGraphTools?: boolean;
  start?: number;
  textDirection?: 'ltr' | 'rtl';
  unit: ProfileDataUnit;
}

const usFormat = getValueFormat('µs');
const boundryBody = true;
const paddingLeft = 16;

@Component
export default class ProfilingFlameGraph extends tsc<IFlameGraphProps, IFlameGraphEvent> {
  @Ref() chartRef: HTMLElement;
  @Ref() wrapperRef: HTMLElement;
  @Ref() flameToolsPopoverContent: HTMLElement;

  @Prop({ required: true, type: Object as () => BaseDataType }) data: BaseDataType;
  @Prop({ default: '', type: String }) appName: string;
  @Prop({ default: '', type: String }) diffTraceId: string;
  @Prop({ default: () => [] as string[], type: Array }) filterKeywords: [];
  @Prop({ default: 'ltr', type: String }) textDirection: 'ltr' | 'rtl';
  @Prop({ default: '', type: String }) profileId: string;
  @Prop({ default: 0, type: Number }) start: number;
  @Prop({ default: 0, type: Number }) end: number;
  @Prop({ default: 0, type: Number }) bizId: number;
  @Prop({ default: true, type: Boolean }) showGraphTools: boolean;
  @Prop({ default: -1, type: Number }) highlightId: number;
  @Prop({ default: '', type: String }) highlightName: string;
  @Prop({ default: false, type: Boolean }) isCompared: boolean;
  @Prop({ default: 'nanoseconds', type: String }) unit: ProfileDataUnit;

  showException = true;
  showDiffLegend = false;
  tipDetail: ITipsDetail = {};
  contextMenuRect: IContextMenuRect = {
    left: 0,
    top: 0,
    spanId: '',
    spanName: '',
  };

  axisRect: IAxisRect = { left: 0, bottom: 0, title: '', visibility: 'hidden' };
  zoomRect: IZoomRect = { left: 0, width: 0 };
  graphToolsRect: Partial<DOMRect> = { left: 0, top: 0, width: 120, height: 300 };
  /** 是否显示图例 */
  showLegend = false;
  // graphInstance: FlameChart<BaseDataType> = null;
  graphInstance = null;
  svgRect: DOMRect = null;
  // 放大系数
  scaleValue = 100;
  localIsCompared = false;

  @Emit('updateLoading')
  handleUpdateloadingChange(val) {
    return val;
  }

  @Emit('diffTraceSuccess')
  handleDiffTraceSuccessChange() {}

  get diffPercentList() {
    return COMPARE_DIFF_COLOR_LIST.map(val => `${val.value}%`);
  }

  get flameInstance() {
    const { data, appName } = this;
    return { data, appName };
  }

  @Watch('textDirection')
  handleTextDirectionChange() {
    this.graphInstance?.setTextDirection(this.textDirection);
  }

  @Debounce(16)
  @Watch('flameInstance', { immediate: true })
  async handleFlameInstanceChange() {
    this.contextMenuRect.left = -1;
    this.handleUpdateloadingChange(true);
    this.showException = false;
    try {
      if (this.data) {
        if (this.diffTraceId) {
          this.handleDiffTraceSuccessChange();
        }
        this.showException = false;
        await this.$nextTick();
        if (!this.chartRef?.clientWidth) return;
        this.localIsCompared = this.isCompared;
        this.graphInstance = new FlameChart(
          this.initGraphData(this.data),
          {
            w: this.chartRef.clientWidth - paddingLeft * 2,
            c: 20,
            // minHeight: window.innerHeight - this.wrapperRef?.getBoundingClientRect().top - 40,
            minHeight: this.wrapperRef?.getBoundingClientRect().height - 40,
            direction: this.textDirection,
            keywords: this.filterKeywords,
            unit: this.unit,
            getFillColor: (d: BaseDataType) => {
              if (d.id === RootId) return 'rgb(223,133,32)';
              return this.isCompared && d?.diff_info ? getSingleDiffColor(d.diff_info) : '';
            },
            onDetail: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c: IOtherData) => {
              if (!d) {
                this.tipDetail = {};
                return;
              }
              let detailsData;
              let dataText;
              const { value: dataValue, text: profileText } = parseProfileDataTypeValue(d.data.value, this.unit, true);
              detailsData = dataValue;
              dataText = profileText;

              let diffData;
              let diffValue = 0;
              if (this.isCompared && d.data?.diff_info) {
                const { value: diffProfileValue } = parseProfileDataTypeValue(d.data.diff_info.comparison, this.unit);
                diffData = diffProfileValue;
                diffValue =
                  d.data.diff_info.comparison === 0 || d.data.diff_info.mark === 'unchanged'
                    ? 0
                    : d.data.diff_info.diff;
                // : +(
                //     ((d.data.diff_info.baseline - d.data.diff_info.comparison) * 100) /
                //     d.data.diff_info.comparison
                //   ).toFixed(2);
              }
              let axisLeft = e.pageX - (boundryBody ? 0 : this.svgRect.left);
              let axisTop = e.pageY - (boundryBody ? 0 : this.svgRect.top);
              if (axisLeft + 360 > window.innerWidth) {
                axisLeft = axisLeft - 340 - 16;
              } else {
                axisLeft = axisLeft + 16;
              }
              if (axisTop + 180 > window.innerHeight) {
                axisTop = axisTop - 180;
              }
              this.tipDetail = {
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
              let axisLeft = e.pageX - this.svgRect.x;
              if (axisLeft + 180 > this.svgRect.width) {
                axisLeft = axisLeft - 160 - 16;
              } else {
                axisLeft = axisLeft + 16;
              }
              const top = e.pageY - this.svgRect.y + 16;
              this.tipDetail = {};
              this.contextMenuRect = { left: axisLeft, top, spanId: d.data.id, spanName: d.data.name };
            },
            onMouseMove: (e: MouseEvent, c: IOtherData) => {
              const axisLeft = e.pageX - (boundryBody ? 0 : this.svgRect.left);
              const { text, suffix } = usFormat(c.xAxisValue);
              this.axisRect = {
                left: axisLeft,
                top: this.svgRect.top - paddingLeft,
                bottom: this.svgRect.bottom + paddingLeft,
                title: text + suffix,
                visibility:
                  axisLeft < this.svgRect.x || axisLeft > this.svgRect.width + this.svgRect.x ? 'hidden' : 'visible',
              };
            },
            onMouseOut: () => {
              this.axisRect = { left: 0, title: '', visibility: 'hidden' };
              this.tipDetail = {};
            },
            onMouseDown: () => {},
          },
          this.chartRef
        );
        setTimeout(() => {
          this.setSvgRect();
          addListener(this.wrapperRef!, this.handleResize);
        }, 750);
        this.showException = false;
        this.$nextTick(() => {
          this.handleUpdateloadingChange(false);
        });
        return;
      }
      this.showException = true;
      this.handleUpdateloadingChange(false);
    } catch (e) {
      console.error(e);
      this.handleUpdateloadingChange(false);
      this.showException = true;
    }
  }

  @Watch('filterKeywords')
  handleFilterKeywordsChange() {
    this.graphInstance?.filterGraph(this.filterKeywords);
  }

  @Watch('highlightId')
  handleHighlightIdChange() {
    this.graphInstance?.highlightNodeId(this.highlightId);
  }
  @Watch('highlightName')
  handleHighlightNameChange() {
    this.graphInstance?.highlightNode(this.highlightName);
  }

  beforeDestroy() {
    this.wrapperRef && removeListener(this.wrapperRef!, this.handleResize);
    this.handleUpdateloadingChange(false);
  }

  /**
   *
   * @param data flame graph data
   * @param traceInfo trace info
   * @returns flame graph data
   */
  initGraphData(data: BaseDataType) {
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
  setSvgRect() {
    this.svgRect = this.chartRef.querySelector('svg').getBoundingClientRect();
    this.graphToolsRect = {
      left: this.svgRect.x + 4,
    };
  }
  /**
   * @description: resize graph
   */
  handleResize() {
    if (!this.wrapperRef) return;
    const rect = this.wrapperRef.getBoundingClientRect();
    const { width } = rect;
    // graphInstance.resizeGraph(width - 12, window.innerHeight - rect.top - 40);
    this.graphInstance.resizeGraph(width - 32, this.wrapperRef?.getBoundingClientRect().height - 40);
    this.setSvgRect();
  }
  /**
   * @description: click context menu
   * @param {ICommonMenuItem} item menu item
   * @return {*}
   */
  handleContextMenuClick(item: ICommonMenuItem) {
    this.contextMenuRect.left = -1;
    if (item.id === 'copy') {
      let hasErr = false;
      copyText(this.contextMenuRect.spanName, (errMsg: string) => {
        this.$bkMessage({
          message: errMsg,
          theme: 'error',
        });
        hasErr = !!errMsg;
      });
      if (!hasErr) this.$bkMessage({ theme: 'success', message: this.$t('复制成功') });
    }
    if (item.id === 'reset') {
      this.initScale();
      this.$emit('updateHighlightId', -1);
      return this.graphInstance?.resetGraph();
    }
    if (item.id === 'highlight') {
      this.graphInstance.highlightNode(this.contextMenuRect.spanName);
      this.$emit('updateHighlightName', this.contextMenuRect.spanName);
    }
  }
  /**
   * @description: click wrapper to hide context menu
   */
  handleClickWrapper() {
    this.contextMenuRect.left = -1;
  }
  /**
   *
   * @param v scale value
   * @description: scale value change
   */
  handlesSaleValueChange(v: number) {
    this.scaleValue = v;
    this.graphInstance.scaleGraph(v);
  }
  /**
   * @description: store image
   */
  handleStoreImg() {
    const svgDom = this.chartRef.querySelector('svg');
    this.convertSvgToPngAndDownload(svgDom, `${this.appName}.png`);
  }
  /**
   *
   * @param svgElement svg element
   * @param fileName file name
   * @description: convert svg to png and download
   */
  convertSvgToPngAndDownload(svgElement: SVGSVGElement, fileName: string) {
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
  initScale() {
    this.scaleValue = 100;
  }
  /** 展示图例 */
  handleShowLegend = () => {
    this.showLegend = !this.showLegend;
  };

  render() {
    if (this.showException)
      return (
        <bk-exception
          description={this.$t('暂无数据')}
          scene='part'
          type='empty'
        />
      );
    return (
      <div style='height: fit-content; flex: 1'>
        <div class='selector-list-slot'>
          {this.localIsCompared && (
            <div
              key='compareLegend'
              class='profiling-compare-legend'
            >
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
                  key={'funtion-name'}
                  class='funtion-name'
                >
                  {this.tipDetail.title}
                </div>,
                <table
                  key={'tips-table'}
                  class='tips-table'
                >
                  {this.localIsCompared && (
                    <thead>
                      <th />
                      <th>{window.i18n.t('当前')}</th>
                      {this.tipDetail.id !== RootId && [
                        <th key={'参照'}>{window.i18n.t('参照')}</th>,
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
                  key={'tips-info'}
                  class='tips-info'
                >
                  <span class='icon-monitor icon-mc-mouse tips-info-icon' />
                  {window.i18n.t('鼠标右键有更多菜单')}
                </div>,
              ]}
            </div>
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
            <div
              style={{
                left: `${this.zoomRect?.left || 0}px`,
                width: `${this.zoomRect?.width || 0}px`,
              }}
              class='flame-graph-zoom'
            />
          </div>
        </div>
      </div>
    );
  }
}
