/* eslint-disable no-plusplus */
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
import { axisTop } from 'd3-axis';
import { easeCubic } from 'd3-ease';
import { hierarchy, HierarchyNode, HierarchyRectangularNode, partition } from 'd3-hierarchy';
import { NumberValue, scaleLinear } from 'd3-scale';
import { BaseType, select, Selection, ValueFn } from 'd3-selection';
import { curveCatmullRom, line } from 'd3-shape';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import 'd3-transition';

import {
  BaseDataType,
  BaseRect,
  ColorTypes,
  IFlameChartOptions,
  IFlameData,
  ILineData,
  IOtherData,
  RootId,
  ThreadPos
} from '../../../typings';

import { findChildById, findRegionById, getHashVal } from './utils';

const usFormat = getValueFormat('µs');
export class FlameChart<D extends BaseDataType> {
  w = 960;
  h = null;
  c = 16;
  transitionDuration = 750;
  minHeight = 200;
  keywords?: string[] = [];
  direction?: 'ltr' | 'rtl' = 'ltr';

  onDetail?: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c?: IOtherData) => void;
  onContextMenu?: (e: MouseEvent, d: HierarchyNode<BaseDataType>) => void;
  onMouseMove?: (e: MouseEvent, c?: IOtherData) => void;
  onMouseOut?: (e: MouseEvent) => void;
  onMouseDown?: (e: MouseEvent) => void;
  getFillColor?: (d: BaseDataType) => string;
  transitionEase = easeCubic; // tooltip offset
  iconSize = 12;
  zoomData: BaseRect = {};

  threadPosMap: Record<string, ThreadPos> = {};
  mainData: D = null;
  threadsData: D[] = [];
  lineMap: Map<string | number, ILineData<D>> = new Map();
  maxDepth = 0;
  isInviewNodeId = [];
  constructor(
    d: IFlameData<D>,
    options: IFlameChartOptions,
    public chartDom: HTMLElement
  ) {
    Object.assign(this, options);
    this.render(d);
  }
  /**
   *
   * @param d 数据
   * @description 渲染图表
   */
  render(d: IFlameData<D>) {
    const { main, threads, maxDepth } = this.initData(d);
    this.mainData = main;
    this.threadsData = threads;
    this.maxDepth = maxDepth;
    select(this.chartDom).selectAll('*').remove();
    select(this.chartDom)
      .append('svg:svg')
      .attr('xmlns', 'http://www.w3.org/2000/svg')
      .attr('xmlns:xlink', 'http://www.w3.org/1999/xlink')
      .attr('width', this.w)
      .attr('height', Math.max(this.minHeight, this.c * maxDepth))
      .attr('style', 'background-color: #f5f7fa;min-height: calc(100% - 10px);')
      .attr('class', `flame-graph-svg direction-${this.direction}`);
    this.zoomData = {
      value: this.mainData.value,
      clickDepth: 0,
      highlightName: '',
      highlightId: -1,
      keywords: this.keywords ?? []
    };
    this.getInViewNode();
    // 坐标轴渲染
    // this.renderAxis({});
    const preDepth = this.renderMainThread(main);
    this.renderThreads(threads, preDepth!);
    this.initEvent();
  }
  initEvent() {}
  zoomGraph(options: BaseRect) {
    const { value, clickDepth, highlightName, highlightId } = options;
    let preDepth = 1;
    preDepth = this.updateSelection(
      select(this.chartDom).select('g.main-thread') as Selection<BaseType, HierarchyNode<D>, null, undefined>,
      { preDepth, value, clickDepth, highlightName, highlightId }
    );
    this.threadsData.forEach(thread => {
      const threadPreDepth = this.updateSelection(
        select(this.chartDom).select(`g.thread-${thread.id}`) as Selection<BaseType, HierarchyNode<D>, null, undefined>,
        { preDepth: preDepth + 1, value, clickDepth, highlightName, highlightId }
      );
      if (threadPreDepth === preDepth + 1) {
        preDepth = threadPreDepth - 1;
      } else {
        preDepth = threadPreDepth;
      }
    });
    const x = scaleLinear([0, this.w]).domain([0, value]);
    select(this.chartDom)
      .select<SVGGElement>('g.x-axis')
      .call(
        axisTop(x)
          .ticks(10)
          .tickSizeOuter(0)
          .tickFormat((d: NumberValue) => {
            const { text, suffix } = usFormat(d.valueOf() - 0);
            return text + suffix;
          })
      );
    this.initEvent();
  }
  /**
   *
   * @param width 宽度
   * @param height 高度
   * @description 重置图表大小
   */
  resizeGraph(width: number, height: number) {
    this.w = width;
    select(this.chartDom)
      .select('svg')
      .attr('width', this.w)
      .attr('height', Math.max(this.minHeight, this.c * this.maxDepth, height));
    this.zoomGraph(this.zoomData);
    this.initEvent();
  }
  scaleGraph(scale: number) {
    const { value } = this.mainData;
    const scaleX = scaleLinear([100, 1000], [0, value]);
    const scaleValue = scaleX(scale);

    this.zoomData = {
      ...this.zoomData,
      value: value - scaleValue
    };

    this.zoomGraph(this.zoomData);
  }
  /**
   *
   * @param left
   * @param width
   */
  timeZoomGraph(left: number, width: number) {
    if (width < 1) return;
    const { value } = this.zoomData;
    const x = scaleLinear([0, this.w]).domain([0, value]);
    this.zoomData = {
      ...this.zoomData,
      value: x.invert(width * 2)
    };
    this.zoomGraph(this.zoomData);
  }
  /**
   *
   * @param direction left | right
   * @description 设置文字方向
   */
  setTextDirection(direction: 'ltr' | 'rtl') {
    select(this.chartDom).select('svg').attr('class', `flame-graph-svg direction-${direction}`);
    this.zoomGraph(this.zoomData);
  }
  /**
   * 重置图表
   */
  resetGraph() {
    this.zoomData = {
      ...this.zoomData,
      value: this.mainData.value,
      clickDepth: 0,
      highlightName: '',
      highlightId: -1
    };
    this.zoomGraph(this.zoomData);
  }
  filterGraph(keywords: string[] = []) {
    this.zoomData = {
      ...this.zoomData,
      keywords: keywords.map(k => k?.toLocaleLowerCase())
    };
    this.zoomGraph(this.zoomData);
  }
  /**
   *
   * @param highlightName 高亮节点名称
   * @description 高亮节点
   */
  highlightNode(highlightName: string) {
    this.zoomData.highlightName = highlightName;
    this.zoomGraph({
      ...this.zoomData,
      highlightName
    });
  }
  /**
   *
   * @param highlightId 高亮节点ID
   * @description 高亮节点
   */
  highlightNodeId(highlightId: number) {
    this.zoomData.highlightId = highlightId;
    this.zoomGraph({
      ...this.zoomData,
      highlightId
    });
  }
  /**
   *
   * @param data 主线程数据
   * @returns 主线程的selection depth
   * @description 渲染主线程
   */
  renderMainThread(data: D) {
    const mainThread = select(this.chartDom)
      .select('svg')
      .append('svg:g')
      .attr('class', 'main-thread')
      .datum(data)
      .datum((d: D) => hierarchy<D>(d, this.getChildren));
    return this.updateSelection(mainThread, { preDepth: 1 });
  }
  /**
   *
   * @param threads 线程数据
   * @param mainThreadDepth 主线程的depth
   * @description 渲染线程
   * @returns 线程的selection depth
   */
  renderThreads(threads: D[], mainThreadDepth: number) {
    let preDepth = mainThreadDepth;
    threads.forEach(thread => {
      const threadSelection = select(this.chartDom)
        .select('svg')
        .append('svg:g')
        .attr('class', `thread thread-${thread.id}`)
        .attr('preDepth', preDepth)
        .datum(thread)
        .datum((d: D) => hierarchy<D>(d, d => this.getChildren(d)));
      preDepth = this.updateSelection(threadSelection, { preDepth: preDepth + 1 });
    });
  }

  /**
   *
   * @param selection selection
   * @param param1
   * @returns
   */
  updateSelection(
    selection: Selection<BaseType, HierarchyNode<D>, null, undefined>,
    { preDepth, value = this.mainData.value, clickDepth = 0, highlightName = '', highlightId = -1 }: BaseRect
  ) {
    const x = scaleLinear([0, this.w]).domain([0, value]);
    const y = (x: number) => x * this.c;
    let currentDepth = preDepth;
    const threadLine = line<ThreadPos>()
      .x(d => d.x)
      .y(d => d.y)
      .curve(curveCatmullRom.alpha(0.88));
    selection
      .each((root: HierarchyNode<D>, index: number, groups: HTMLElement[]) => {
        const newRoot = partition<D>()(root);
        const isInView = (d: HierarchyRectangularNode<D> | HierarchyNode<D>) => {
          if (!clickDepth) return true;
          return this.isInviewNodeId.includes(d.data.id);
        };
        const getLeft = (d: HierarchyRectangularNode<D> | HierarchyNode<D>) => {
          let prevTotal = 0;
          const curDepthRow = descendants.filter(node => isInView(node) && node.depth === d.depth);
          const parentNode = descendants.find(n => n.data.id === d.parent?.data.id);
          if (parentNode) {
            const left = parentNode.left || 0;
            prevTotal += left;
            const childrens = (parentNode.data.children as any).filter(child =>
              curDepthRow.some(n => n.data.id === child.id)
            );

            const index = (childrens as any).findIndex(node => node.id === d.data.id);
            prevTotal = ((childrens as any).slice(0, index) || []).reduce((pre, cur) => {
              return pre + cur.value;
            }, prevTotal);
          }

          descendants.forEach(item => {
            if (item.data.id === d.data.id) {
              item.left = prevTotal;
            }
          });

          return Math.max(0, x(prevTotal));
        };

        const getTranslate = (d: HierarchyRectangularNode<D> | HierarchyNode<D>) => {
          const xPos = getLeft(d);
          // const yPos = y(d.depth + preDepth);
          const yPos = y(d.depth);
          if (this.lineMap.has(d.data.id)) {
            this.lineMap.get(d.data.id).x = xPos;
            this.lineMap.get(d.data.id).y = yPos + this.c / 2;
          }
          return `translate(${xPos},${yPos})`;
        };
        const getFillColor = (d: HierarchyRectangularNode<D> | HierarchyNode<D>) => {
          const customColor = this.getFillColor(d.data);
          const palette = Object.values(ColorTypes);
          const colorIndex = getHashVal(d.data.name) % palette.length;
          const defColor = customColor || palette[colorIndex];
          if (this.zoomData?.keywords?.length) {
            if (this.zoomData.keywords.some(k => d.data.name.toLocaleLowerCase().includes(k))) return defColor;
            return '#aaa';
          }
          if (highlightName) return d.data.name === highlightName ? defColor : '#aaa';
          if (highlightId > -1) return d.data.id === highlightId ? defColor : '#aaa';
          return d.depth < clickDepth ? '#aaa' : defColor;
        };
        const getStrokeColor = (d: HierarchyRectangularNode<D> | HierarchyNode<D>) => {
          // if (this.zoomData?.keywords?.some(k => d.data.name.toLocaleLowerCase().includes(k))) {
          //   return '#3A84FF';
          // }
          return d.data.status?.code === 2 ? '#EA3636' : '#eee';
        };
        const getWidth = (d: HierarchyRectangularNode<D> | HierarchyNode<D>) => {
          const width = Math.min(
            Math.max(1, x(d.data.value)), // TODO
            this.w
          );

          return width;
        };

        const descendants = root.descendants().filter(node => getWidth(node) > 0 && isInView(node));
        // const nodeLength = descendants.length;
        currentDepth += descendants.length ? descendants[descendants.length - 1].depth + 1 : 0;
        const wrapper = select(groups[index]).attr('width', this.w);
        wrapper.selectAll('path.split-line').remove();
        if (preDepth > 1 && descendants.length > 0) {
          wrapper
            .append('path')
            .transition()
            .duration(this.transitionDuration)
            .ease(this.transitionEase)
            .attr('class', `split-line`)
            .attr('stroke', '#ddd')
            .attr('stroke-width', 1)
            .attr('stroke-dasharray', '5,5')
            .attr(
              'd',
              threadLine([
                {
                  x: 0,
                  y: y(newRoot.depth + preDepth - 1 / 2)
                },
                {
                  x: this.w,
                  y: y(newRoot.depth + preDepth - 1 / 2)
                }
              ])
            );
        }

        let g = wrapper.selectAll('g.flame-item').data(descendants, (d: HierarchyRectangularNode<D>) => d?.data?.id);
        g.transition()
          .duration(this.transitionDuration)
          .ease(this.transitionEase)
          .attr('transform', (d: HierarchyRectangularNode<D>) => getTranslate(d));
        g.select('rect.flame-item-rect')
          .transition()
          .duration(this.transitionDuration)
          .ease(this.transitionEase)
          .attr('width', w => getWidth(w));

        const node = g
          .enter()
          .append('svg:g')
          .attr('class', 'flame-item')
          .attr('transform', w => getTranslate(w));

        node
          .append('svg:rect')
          .attr('class', 'flame-item-rect')
          .transition()
          .delay(this.transitionDuration / 2)
          .attr('width', w => getWidth(w));

        node
          .append('svg:image')
          .attr('class', 'flame-item-img')
          .attr('transform', `translate(${(this.c - this.iconSize) / 2}, ${(this.c - this.iconSize) / 2})`)
          .attr('width', 0)
          .transition()
          .delay(this.transitionDuration / 2);

        const foreignObject = node.append('foreignObject').append('xhtml:div').attr('class', 'flame-graph-text');
        foreignObject.append('xhtml:div').attr('class', 'text-name').attr('style', `line-height: ${this.c}px`);
        foreignObject.append('xhtml:div').attr('class', 'text-value').attr('style', `line-height: ${this.c}px`);
        // Now we have to re-select to see the new elements (why?).
        g = wrapper
          .selectAll('g.flame-item')
          .data(
            descendants,
            ((d: HierarchyRectangularNode<D>) => d?.data?.id) as ValueFn<HTMLElement | BaseType, unknown, KeyType>
          );
        g.attr('height', this.c)
          .attr('class', 'flame-item')
          .attr('id', d => d.data.id)
          .attr('width', w => getWidth(w));

        g.select('rect')
          .attr('height', () => this.c)
          .attr('fill', d => getFillColor(d))
          .attr('stroke', d => getStrokeColor(d));

        const textDiv = g
          .select('foreignObject')
          .transition()
          .delay(this.transitionDuration / 2)
          .attr('width', (w, index, groups) => {
            const padding = 6;
            const width = getWidth(w) <= padding ? padding : getWidth(w) - padding;
            select(groups[index]).attr('transform', `translate(${padding}, 0)`);
            return width;
          })
          .attr('height', () => this.c);
        textDiv.select('div.text-name').text(d => {
          const w = getWidth(d);
          if (w > 10) {
            return this.getName(d, 'name');
          }
          return '';
        });
        textDiv.select('div.text-value').text(d => {
          const w = getWidth(d);
          if (w > 10) {
            return this.getName(d, 'value');
          }
          return '';
        });
        g.exit().remove();
        g.on('click', (_, d) => {
          this.zoomData = {
            ...this.zoomData,
            value: d.data.value,
            clickDepth: d.depth,
            highlightName: d.data.id === RootId ? '' : this.zoomData.highlightName || ''
          };
          this.getInViewNode(d);
          this.zoomGraph(this.zoomData);
        });
        if (this.onDetail) {
          // eslint-disable-next-line @typescript-eslint/no-this-alias
          const self = this;
          g.on('mousemove', (e: MouseEvent, d) => {
            this.onDetail(e, d, {
              rootValue: this.mainData.value
            });
          })
            .on('mouseout', function (e: MouseEvent) {
              select(this).select('rect').attr('opacity', '.9');
              select(self.chartDom).select('svg').selectAll('path.thread-line').remove();
              self.onDetail(e, null);
            })
            .on('mouseover', function () {
              select(this).select('rect').attr('opacity', '.5');
            })
            .on('contextmenu', function (e, d) {
              e.preventDefault();
              self.onContextMenu(e, d);
            });
        }
      })
      .exit()
      .remove();
    return currentDepth;
  }
  getInViewNode(d?: HierarchyNode<D>) {
    if (!d) {
      this.isInviewNodeId = findChildById([this.mainData], this.mainData.id).concat([this.mainData.id]);
    } else {
      this.isInviewNodeId = findRegionById([this.mainData], d.data.id).concat(findChildById([d.data], d.data.id));
    }
  }
  getName(d: HierarchyNode<D> | HierarchyRectangularNode<D>, type: 'all' | 'name' | 'value' = 'all') {
    const value = this.getValue(d as HierarchyRectangularNode<D>);
    if (type === 'name') return d.data.name;
    const { text, suffix } = usFormat(value);
    if (type === 'value') return `(${((value / this.getValue(this.mainData)) * 100).toFixed(2)}%, ${text}${suffix})`;
    return `${d.data.name}(${((value / this.getValue(this.mainData)) * 100).toFixed(2)}%, ${text}${suffix})`;
  }

  getValue(d: D | HierarchyRectangularNode<D>) {
    if ('data' in d) {
      return d.data.value / 1000;
    }

    return d.value / 1000;
  }

  getChildren(d: D | HierarchyRectangularNode<D> | HierarchyNode<D>) {
    if ('data' in d) {
      return d.data.children as D[];
    }
    return d.children as D[];
  }

  initData(d: IFlameData<D>) {
    const { main, threads } = structuredClone(d);
    let maxDepth = 1;
    let nodes = hierarchy(main, (d: D) => d.children).descendants();
    // const mergeList = [...nodes];
    // const fromSet = new Set(...nodes.filter(item => item.data.last_sibling_id).map(item => item.data.last_sibling_id));
    // const lineMap = new Map<string, ILineData<D>>();
    maxDepth += nodes.at(-1).depth;
    threads.forEach(thread => {
      nodes = hierarchy(thread, (d: D) => d.children).descendants();
      // mergeList.push(...nodes);
      // nodes.forEach(item => item.data.last_sibling_id && fromSet.add(item.data.last_sibling_id));
      maxDepth += nodes.at(-1).depth + 2;
    });
    // fromSet.forEach(id => {
    //   const node = mergeList.find(item => item.data.id === id);
    //   if (node) {
    //     lineMap.set(id, { x: 0, y: 0, tag: 'to', data: node.data });
    //     const from = mergeList.find(item => item.data.last_sibling_id === id).data;
    //     lineMap.set(from.id, { x: 0, y: 0, tag: 'from', data: from });
    //   }
    // });
    // this.lineMap = lineMap;

    return {
      threads,
      main,
      maxDepth
    };
  }
}
