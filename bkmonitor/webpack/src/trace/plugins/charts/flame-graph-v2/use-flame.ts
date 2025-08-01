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
import { type HierarchyNode, type HierarchyRectangularNode, hierarchy, partition } from 'd3-hierarchy';
import { path } from 'd3-path';
import { type NumberValue, scaleLinear } from 'd3-scale';
import { type BaseType, type Selection, type ValueFn, select } from 'd3-selection';
import { curveCatmullRom, line } from 'd3-shape';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import traceIcons from '../../utls/icons';
import {
  type BaseDataType,
  type BaseRect,
  type IFlameChartOptions,
  type IFlameData,
  type ILineData,
  type IOtherData,
  type ThreadPos,
  ColorTypes,
  RootId,
} from './types';

const usFormat = getValueFormat('µs');
export class FlameChart<D extends BaseDataType> {
  c = 16;
  direction?: 'ltr' | 'rtl' = 'ltr';
  getFillColor?: (d: BaseDataType) => string;
  h = null;
  iconSize = 12;
  keywords?: string[] = [];
  lineMap: Map<string, ILineData<D>> = new Map();

  mainData: D = null;
  maxDepth = 0;
  minHeight = 200;
  onContextMenu?: (e: MouseEvent, d: HierarchyNode<BaseDataType>) => void;
  onDetail?: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c?: IOtherData) => void;
  onMouseDown?: (e: MouseEvent) => void;
  onMouseMove?: (e: MouseEvent, c?: IOtherData) => void; // tooltip offset
  onMouseOut?: (e: MouseEvent) => void;
  threadPosMap: Record<string, ThreadPos> = {};

  threadsData: D[] = [];
  transitionDuration = 750;
  transitionEase = easeCubic;
  w = 960;
  zoomData: BaseRect = {};
  constructor(
    d: IFlameData<D>,
    options: IFlameChartOptions,
    public chartDom: HTMLElement
  ) {
    Object.assign(this, options);
    this.render(d);
  }
  addRootNode(data: D[]) {
    const root = {
      value: 0,
      name: 'total',
      id: RootId,
      start_time: 0,
      end_time: 0,
    };
    data.forEach((item, index) => {
      root.start_time = index === 0 ? item.start_time : Math.min(root.start_time, item.start_time);
      root.end_time = Math.max(root.end_time, item.end_time);
    });
    root.value = root.end_time - root.start_time;
    return {
      ...root,
      children: data,
    };
  }
  filterGraph(keywords: string[] = []) {
    this.zoomData = {
      ...this.zoomData,
      keywords: keywords.map(k => k?.toLocaleLowerCase()),
    };
    this.zoomGraph(this.zoomData);
  }
  getChildren(d: D | HierarchyNode<D> | HierarchyRectangularNode<D>) {
    if ('data' in d) {
      return d.data.children as D[];
    }
    return d.children as D[];
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
      return d.data.end_time - d.data.start_time;
    }
    if ('end_time' in d) {
      return d.end_time - d.start_time;
    }
    return d.value;
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
      highlightName,
    });
  }
  initData(d: IFlameData<D>) {
    const { main, threads } = structuredClone(d);
    // const stack: D[] = [data];
    // let node: D = null;
    // let children: D[] = null;
    // let i = 0;
    // let child: D = null;
    // const threads: D[] = [];
    // const startTime = data.start_time;
    // let endTime = 0;
    // while ((node = stack.pop())) {
    //   children = node.children as D[];
    //   children.sort((a, b) => a.start_time - b.start_time);
    //   endTime = Math.max(endTime, node.end_time);
    //   if (children && (i = children.length)) {
    //     const spliceIndex = [];
    //     while (i--) {
    //       child = children[i];
    //       endTime = Math.max(endTime, child.end_time);
    //       if (i > 0 && child) {
    //         const startTime = child.start_time;
    //         const preEndTime = children[i - 1].end_time;
    //         if (startTime < preEndTime) {
    //           child.threadSiblingId = children[i - 1].id;
    //           this.threadPosMap[child.threadSiblingId] = {
    //             x: 0,
    //             y: 0
    //           };
    //           threads.push(child);
    //           spliceIndex.push(i);
    //         }
    //       }
    //       stack.push(child);
    //     }
    //     node.children = children.filter((_, index) => !spliceIndex.includes(index));
    //   }
    // }
    // data.start_time = startTime;
    // data.end_time = endTime;
    let maxDepth = 1;
    let nodes = hierarchy(main, (d: D) => d.children).descendants();
    const mergeList = [...nodes];
    const fromSet = new Set(...nodes.filter(item => item.data.last_sibling_id).map(item => item.data.last_sibling_id));
    const lineMap = new Map<string, ILineData<D>>();
    maxDepth += nodes.at(-1).depth;
    threads.forEach(thread => {
      nodes = hierarchy(thread, (d: D) => d.children).descendants();
      mergeList.push(...nodes);
      nodes.forEach(item => item.data.last_sibling_id && fromSet.add(item.data.last_sibling_id));
      maxDepth += nodes.at(-1).depth + 2;
    });
    fromSet.forEach(id => {
      const node = mergeList.find(item => item.data.id === id);
      if (node) {
        lineMap.set(id, { x: 0, y: 0, tag: 'to', data: node.data });
        const from = mergeList.find(item => item.data.last_sibling_id === id).data;
        lineMap.set(from.id, { x: 0, y: 0, tag: 'from', data: from });
      }
    });
    this.lineMap = lineMap;
    return {
      threads,
      main,
      maxDepth,
    };
  }
  initEvent() {
    const rect = this.chartDom.getBoundingClientRect();
    const { startTime, endTime } = this.zoomData;
    const x = scaleLinear([0, this.w]).domain([startTime, endTime]);
    select(this.chartDom)
      .select('svg')
      .on('mousemove', (event: MouseEvent) => {
        const left = event.clientX - rect.left - 6;
        this.onMouseMove(event, {
          xAxisValue: x.invert(left) - startTime,
        });
      })
      .on('mouseout', (event: MouseEvent) => {
        this.onMouseOut(event);
      })
      .on('mousedown', (event: MouseEvent) => {
        event.preventDefault();
        this.onMouseDown(event);
      });
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
      startTime: this.mainData.start_time,
      endTime: this.mainData.end_time,
      clickDepth: 0,
      highlightName: '',
      keywords: this.keywords ?? [],
    };
    this.renderAxis({});
    const preDepth = this.renderMainThread(main);
    this.renderThreads(threads, preDepth!);
    this.initEvent();
  }
  /**
   *
   *@description 渲染x轴
   */
  renderAxis({ startTime = this.mainData.start_time, endTime = this.mainData.end_time }: BaseRect) {
    const x = scaleLinear([0, this.w]).domain([startTime, endTime]);
    select(this.chartDom)
      .select('svg')
      .append('g')
      .attr('class', 'x-axis')
      .attr('width', this.w)
      .attr('transform', `translate(0, ${this.c})`)
      .call(
        axisTop(x)
          .ticks(Math.ceil(this.w / 100))
          .tickSizeOuter(0)
          .tickFormat((d: NumberValue) => {
            const { text, suffix } = usFormat(d.valueOf() - startTime);
            return text + suffix;
          })
      );
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
   * 重置图表
   */
  resetGraph() {
    this.zoomData = {
      ...this.zoomData,
      startTime: this.mainData.start_time,
      endTime: this.mainData.end_time,
      clickDepth: 0,
      highlightName: '',
    };
    this.zoomGraph(this.zoomData);
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
    const { start_time, end_time } = this.mainData;
    const scaleX = scaleLinear([100, 1000], [start_time, end_time]);
    const scaleValue = scaleX(scale);
    const step = (scaleValue - start_time) / 2;
    this.zoomData = {
      ...this.zoomData,
      startTime: start_time + step,
      endTime: end_time - step,
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
   *
   * @param left
   * @param width
   */
  timeZoomGraph(left: number, width: number) {
    if (width < 1) return;
    const { startTime, endTime } = this.zoomData;
    const x = scaleLinear([0, this.w]).domain([startTime, endTime]);
    this.zoomData = {
      ...this.zoomData,
      startTime: Math.max(x.invert(left), startTime),
      endTime: Math.min(x.invert(left + width), endTime),
    };
    this.zoomGraph(this.zoomData);
  }

  /**
   *
   * @param selection selection
   * @param param1
   * @returns
   */
  updateSelection(
    selection: Selection<BaseType, HierarchyNode<D>, null, undefined>,
    {
      preDepth,
      startTime = this.mainData.start_time,
      endTime = this.mainData.end_time,
      clickDepth = 0,
      highlightName = '',
    }: BaseRect
  ) {
    // const x = scaleLinear([startTime, endTime], [0, this.w]);
    const x = scaleLinear([0, this.w]).domain([startTime, endTime]);
    const y = (x: number) => x * this.c;
    let currentDepth = preDepth;
    const threadLine = line<ThreadPos>()
      .x(d => d.x)
      .y(d => d.y)
      .curve(curveCatmullRom.alpha(0.88));
    const drawLine = (to: ILineData<D>, from: ILineData<D>) => {
      let middleX = from.x + (to.x - from.x) / 2 - this.c * 2;
      const middleY = from.y + (to.y - from.y) / 2 + this.c;
      let step = 2;
      while (middleX < 0 && step < 30) {
        middleX = from.x + (to.x - from.x) / 2 - this.c / step;
        step += 1;
      }
      const pathLine = path();
      pathLine.moveTo(from.x, from.y);
      pathLine.bezierCurveTo(from.x, from.y, middleX, middleY, to.x, to.y);
      select(this.chartDom)
        .select('svg')
        .append('path')
        .attr('class', 'thread-line')
        .attr('d', pathLine.toString())
        .attr('stroke', '#666')
        .attr('fill', 'transparent')
        .attr('stroke-width', 1.2)
        .attr('stroke-dasharray', '5,5');
    };
    // select(this.chartDom).select('svg').selectAll('path.split-line').remove();
    selection
      .each((root: HierarchyNode<D>, index: number, groups: HTMLElement[]) => {
        const newRoot = partition<D>()(root);
        const getLeft = (d: HierarchyNode<D> | HierarchyRectangularNode<D>) => {
          return Math.max(0, x(d.data.start_time));
        };
        const isInView = (d: HierarchyNode<D> | HierarchyRectangularNode<D>) => {
          const a = x(d.data.start_time);
          const b = x(d.data.end_time);
          return !((a <= 0 && b <= 0) || (a >= this.w && b >= this.w));
        };
        const getTranslate = (d: HierarchyNode<D> | HierarchyRectangularNode<D>) => {
          const xPos = getLeft(d);
          const yPos = y(d.depth + preDepth);
          if (this.lineMap.has(d.data.id)) {
            this.lineMap.get(d.data.id).x = xPos;
            this.lineMap.get(d.data.id).y = yPos + this.c / 2;
          }
          return `translate(${xPos},${yPos})`;
        };
        const getFillColor = (d: HierarchyNode<D> | HierarchyRectangularNode<D>) => {
          const customColor = this.getFillColor(d.data);
          const defColor = customColor || ColorTypes[d.data.icon_type || 'other'];
          if (this.zoomData?.keywords?.length) {
            if (this.zoomData.keywords.some(k => d.data.name.toLocaleLowerCase().includes(k))) return defColor;
            return '#aaa';
          }
          if (highlightName) return d.data.name === highlightName ? defColor : '#aaa';
          return d.depth < clickDepth ? '#aaa' : defColor;
        };
        const getStrokeColor = (d: HierarchyNode<D> | HierarchyRectangularNode<D>) => {
          // if (this.zoomData?.keywords?.some(k => d.data.name.toLocaleLowerCase().includes(k))) {
          //   return '#3A84FF';
          // }
          return d.data.status?.code === 2 ? '#EA3636' : '#eee';
        };
        const getWidth = (d: HierarchyNode<D> | HierarchyRectangularNode<D>) => {
          const width = Math.min(
            Math.max(1, Math.min(x(d.data.end_time), this.w) - Math.max(x(d.data.start_time), 0)),
            this.w
          );
          // if (width === 1 && nodeLength < 2) return 2;
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
            .attr('class', 'split-line')
            .attr('stroke', '#ddd')
            .attr('stroke-width', 1)
            .attr('stroke-dasharray', '5,5')
            .attr(
              'd',
              threadLine([
                {
                  x: 0,
                  y: y(newRoot.depth + preDepth - 1 / 2),
                },
                {
                  x: this.w,
                  y: y(newRoot.depth + preDepth - 1 / 2),
                },
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
            ((d: HierarchyRectangularNode<D>) => d?.data?.id) as ValueFn<BaseType | HTMLElement, unknown, KeyType>
          );
        g.attr('height', this.c)
          .attr('class', 'flame-item')
          .attr('id', d => d.data.id)
          .attr('width', w => getWidth(w));

        g.select('rect')
          .attr('height', () => this.c)
          .attr('fill', d => getFillColor(d))
          .attr('stroke', d => getStrokeColor(d));
        g.select('.flame-item-img')
          .transition()
          .delay(this.transitionDuration / 2)
          .attr('width', (w, index, groups) => {
            const width = getWidth(w);
            if (width > this.iconSize * 2) {
              select(groups[index]).attr(
                'xlink:href',
                () => traceIcons[w.data.status?.code === 2 ? 'error' : w.data.icon_type] || ''
              );
              return this.iconSize;
            }
            return 0;
          });

        const textDiv = g
          .select('foreignObject')
          .transition()
          .delay(this.transitionDuration / 2)
          .attr('width', (w, index, groups) => {
            const width = getWidth(w);
            const hasImg = width > this.iconSize * 2;
            select(groups[index]).attr('transform', `translate(${hasImg ? this.c : 0}, 0)`);
            return hasImg ? width - this.c : width;
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
            startTime: d.data.start_time,
            endTime: d.data.end_time,
            clickDepth: d.depth,
            highlightName: d.data.id === RootId ? '' : this.zoomData.highlightName || '',
          };
          this.zoomGraph(this.zoomData);
        });
        if (this.onDetail) {
          // eslint-disable-next-line @typescript-eslint/no-this-alias
          const self = this;
          g.on('mousemove', (e: MouseEvent, d) => {
            this.onDetail(e, d, {
              rootValue: this.mainData.end_time - this.mainData.start_time,
            });
          })
            .on('mouseout', function (e: MouseEvent) {
              select(this).select('rect').attr('opacity', '.9');
              select(self.chartDom).select('svg').selectAll('path.thread-line').remove();
              self.onDetail(e, null);
            })
            .on('mouseover', function (e: MouseEvent, d: HierarchyNode<D>) {
              // 处理并发联线
              const { id, last_sibling_id } = d.data;
              if (self.lineMap.has(last_sibling_id) || self.lineMap.has(id)) {
                const list: ILineData<D>[] = [];
                list.push(self.lineMap.get(d.data.id));
                let node: ILineData<D> = null;
                function isInView(node: ILineData<D>) {
                  const a = x(node.data.start_time);
                  const b = x(node.data.end_time);
                  return !((a <= 0 && b <= 0) || (a >= self.w && b >= self.w));
                }

                while ((node = list.pop())) {
                  const to = self.lineMap.get(node.data.last_sibling_id);
                  // to.data
                  if (to && isInView(to)) {
                    drawLine.call(self, node, to);
                    list.push(to);
                  }
                }
                const valueList = Array.from(self.lineMap.values());
                list.push(self.lineMap.get(d.data.id));
                while ((node = list.pop())) {
                  const from = valueList.find(item => item.data.last_sibling_id === node.data.id);
                  if (from && isInView(from)) {
                    drawLine.call(self, from, node);
                    list.push(from);
                  }
                }
              }
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
  zoomGraph(options: BaseRect) {
    const { startTime, endTime, clickDepth, highlightName } = options;
    let preDepth = 1;
    preDepth = this.updateSelection(
      select(this.chartDom).select('g.main-thread') as Selection<BaseType, HierarchyNode<D>, null, undefined>,
      { preDepth, startTime, endTime, clickDepth, highlightName }
    );
    this.threadsData.forEach(thread => {
      const threadPreDepth = this.updateSelection(
        select(this.chartDom).select(`g.thread-${thread.id}`) as Selection<BaseType, HierarchyNode<D>, null, undefined>,
        { preDepth: preDepth + 1, startTime, endTime, clickDepth, highlightName }
      );
      if (threadPreDepth === preDepth + 1) {
        preDepth = threadPreDepth - 1;
      } else {
        preDepth = threadPreDepth;
      }
    });
    const x = scaleLinear([0, this.w]).domain([startTime, endTime]);
    select(this.chartDom)
      .select<SVGGElement>('g.x-axis')
      .call(
        axisTop(x)
          .ticks(10)
          .tickSizeOuter(0)
          .tickFormat((d: NumberValue) => {
            const { text, suffix } = usFormat(d.valueOf() - startTime);
            return text + suffix;
          })
      );
    this.initEvent();
  }
}
