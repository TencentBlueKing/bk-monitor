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
import { Component, InjectReactive, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import G6 from '@antv/g6';
import dayjs from 'dayjs';

import bus from '../../../../monitor-common/utils/event-bus';
import { Debounce, random } from '../../../../monitor-common/utils/utils';
import EmptyStatus from '../../../../monitor-pc/components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../../monitor-pc/components/empty-status/types';
import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
import CommonTable from '../../../../monitor-pc/pages/monitor-k8s/components/common-table';
import {
  IFilterDict,
  ITableColumn,
  ITableFilterItem,
  ITablePagination
} from '../../../../monitor-pc/pages/monitor-k8s/typings';
import { transformConditionValueParams } from '../../../../monitor-pc/pages/monitor-k8s/utils';
import RatioLegend from '../../components/chart-legend/relation-legend';
import RelationChartTitle from '../../components/relation-chart-title/relation-chart-title';
import backIcon from '../../icons/back.svg';
import bannerIcon from '../../icons/banner.svg';
import { IRelationStatusItem, LegendActionType, PanelModel } from '../../typings';
import { ITableDataItem } from '../../typings/table-chart';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';

import './relation-graph.scss';

interface IRelationGraphProps {
  panel: PanelModel;
  showChartHeader?: boolean;
}

interface ILayout {
  type?: string;
  center?: number[];
  linkDistance?: number;
  maxIteration?: number;
  maxPreventOverlapIteration?: number;
  unitRadius?: number;
  preventOverlap?: boolean;
  nodeSize?: number;
  strictRadial?: boolean;
  nodeSpacing?: number;
  rankdir?: string; // 布局的方向 从左至右
  nodesep?: number; // 节点的间距
  ranksep?: number; // 层间距
  workerEnabled?: boolean; // 可选，开启 web-worker
}

const LIMIT_RADIAL_LAYOUT_COUNT = 700;
const LIMIT_WORKER_ENABLED = 500;
@Component
export class RelationGraph extends CommonSimpleChart {
  @Ref() chartTitle: RelationChartTitle;

  empty = true;
  emptyText = '';
  canvasWidth = 0; // 画布宽度
  canvasHeight = 0; // 画布高度
  graph = null; // 拓扑图实例
  isOverview = true; // 总览/列表
  minZoomVal = 0.2; // 缩放滑动条最小值
  maxZoomVal = 2; // 缩放滑动条最大值
  zoomValue = 1; // 缩放比例
  initZoomValue = 1;
  isRendered = false; // 拓扑图是否已经渲染完

  /** 图表数据 */
  tableData: ITableDataItem[] = [];
  /** 表格列数据 */
  columns: ITableColumn[] = [];
  /** 表头设置的列 */
  checkedColumns: string[] = [];
  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  /* 表格排序 */
  sortKey = '';
  /* 关键字搜索 */
  keyword = '';
  /** 状态 */
  filter = 'all';
  /** 过滤条件 */
  filterList: ITableFilterItem[] = [];
  /** search-select可选项数据 */
  conditionOptions = [];
  conditionList = [];
  /* 是否显示无数据节点 */
  showNoData = true;
  /* 是否全屏 */
  isFullScreen = false;
  /** 当前请求是否下钻 */
  isDrillDown = false;
  /* 拓扑图数据 */
  graphData = null;
  /* 当前下钻的节点 */
  serviceName = '';
  /* 类型切换 */
  sizeCategory = 'request_count';
  /* 用于刷新右下角统计的值 */
  legendKey = random(8);
  /** 布局基础配置 */
  baseLayoutConf: ILayout = {
    center: [this.canvasWidth / 2, this.canvasHeight / 2], // 布局的中心
    linkDistance: 400, // 边长度
    maxIteration: 1000, // 最大迭代次数
    preventOverlap: true, // 是否防止重叠
    nodeSize: 40, // 节点大小（直径）
    nodeSpacing: 500 // preventOverlap 为 true 时生效, 防止重叠时节点边缘间距的最小值
  };
  /** gForce 布局配置 */
  gForceLayoutConf: ILayout = {
    ...this.baseLayoutConf,
    type: 'gForce',
    linkDistance: 200,
    nodeSpacing: 200,
    maxIteration: 4000,
    workerEnabled: true // 可选，开启 web-worker
  };
  /** 辐射形 Radial 布局配置 */
  radialLayoutConf: ILayout = {
    ...this.baseLayoutConf,
    type: 'radial',
    maxPreventOverlapIteration: 1000, // 防止重叠步骤的最大迭代次数
    unitRadius: 200, // 每一圈距离上一圈的距离
    strictRadial: false // 是否必须是严格的 radial 布局，及每一层的节点严格布局在一个环上。preventOverlap 为 true 时生效。
    // workerEnabled: true // 可选，开启 web-worker
  };
  /** 层次 Dagre 布局配置 */
  dagreLayoutConf: ILayout = {
    type: 'dagre',
    rankdir: 'LR', // 布局的方向 从左至右
    nodesep: 30, // 节点的间距
    ranksep: 100 // 层间距
  };
  // 表格列数据项过滤
  tableFilterDict: IFilterDict = {};
  legendStatusData: IRelationStatusItem[] = [];
  legendStatisticsData = [];
  /** 图例过滤 */
  legendFilters = {
    status: [],
    request_count: [],
    avg_duration: []
  };
  emptyStatusType: EmptyStatusType = 'empty';

  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  /** 搜索框类型 */
  get searchType() {
    return this.panel.options?.table_chart?.search_type || 'input';
  }

  /** 当前使用的布局 应用概览使用 radial布局、下钻服务使用 dagre 布局 */
  get graphLayout() {
    // 服务拓扑使用 dagre 层级布局
    if (this.serviceName) return this.dagreLayoutConf;
    const curNodeLen = this.graphData?.nodes?.length || 0;
    // 节点过多 使用 gForce 布局
    if (curNodeLen > LIMIT_RADIAL_LAYOUT_COUNT) return this.gForceLayoutConf;
    // 默认使用 radial 辐射布局
    return Object.assign(this.radialLayoutConf, {
      // 当节点数量大于 LIMIT_WORKER_ENABLED 开启
      workerEnabled: curNodeLen > LIMIT_WORKER_ENABLED
    });
  }

  // 节点菜单
  contextMenu() {
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    const self = this;
    return new G6.Menu({
      className: 'node-menu-container',
      trigger: 'click',
      // 是否阻止行为发生
      shouldBegin(evt) {
        // 展开的当前服务返回按钮
        if (['back-text-shape', 'back-icon-shape'].includes(evt.target?.cfg?.name)) {
          self.handleBack();
          return false;
        }
        if (evt.item) return true;
        return false;
      },
      // 菜单项内容
      getContent(evt) {
        if (self.readonly) return undefined;
        const { item } = evt;
        if (!item) return;
        const itemType = item.getType();
        const model = item.getModel() as any;
        const itemName = (target, model) => {
          if (target.id === 'down') {
            return self.serviceName === model.id ? window.i18n.t('上钻服务') : target.name;
          }
          return target.name;
        };
        if (itemType && model) {
          return `<ul>
            ${model.menu
              .map(
                target =>
                  `<li id='${JSON.stringify(target)}'>
      <span>
        <span class="icon-monitor node-menu-icon ${target.icon}"></span>
        ${itemName(target, model)}
      </span>
      ${target.target === 'blank' ? '<span class="icon-monitor icon-fenxiang"></span>' : ''}
    </li>`
              )
              .join('')}
            </ul>`;
        }
      },
      handleMenuClick: (target, item) => this.handleNodeMenuClick(target, item),
      // 在哪些类型的元素上响应 node：节点 | canvas：画布
      itemTypes: ['node']
    });
  }
  // 节点自定义tooltips
  nodeTooltip() {
    return new G6.Tooltip({
      offsetX: 4, // x 方向偏移值
      offsetY: 4, // y 方向偏移值
      // trigger: 'click',
      fixToNode: [1, 0.5], // 固定出现在相对于目标节点的某个位置
      className: 'node-tooltips-container',
      // 允许出现 tooltip 的 item 类型
      itemTypes: ['node'],
      shouldBegin(evt) {
        // 展开的当前服务返回按钮
        if (['back-text-shape', 'back-icon-shape'].includes(evt.target?.cfg?.name)) {
          return false;
        }
        if (evt.item) return true;
        return false;
      },
      // 自定义 tooltip 内容
      getContent: e => this.getTooltipsContent(e)
    });
  }
  /**
   * @description: 获取图表数据
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {
    this.beforeGetPanelData(start_time, end_time);
    this.handleLoadingChange(true);
    if (this.graph) {
      // 筛选时显示loading 需注销实例重新生成
      this.graph.destroy();
      this.graph = null;
      /** 重置图例过滤参数 */
      this.legendFilters = {
        status: [],
        request_count: [],
        avg_duration: []
      };
    }
    this.emptyText = window.i18n.tc('加载中...');
    this.empty = true;
    this.isRendered = false;
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime
      };
      const variablesService = new VariablesService(this.viewOptions);
      let promiseList = [];
      if (this.isOverview) {
        promiseList = this.panel.targets
          .filter(item => item.dataType === 'topo')
          .map(item => {
            if (!this.isDrillDown) {
              // 当前如果不是下钻请求 则使用viewOptions里service_name
              const variables = variablesService.transformVariables(this.viewOptions);
              this.serviceName = variables.service_name ?? '';
            }
            return (this as any).$api[item.apiModule]
              [item.apiFunc](
                variablesService.transformVariables(
                  {
                    ...item.data,
                    ...params,
                    service_name: this.serviceName,
                    condition_list: transformConditionValueParams(this.conditionList),
                    size_category: this.sizeCategory,
                    view_options: {
                      ...this.viewOptions
                    }
                  },
                  {
                    ...this.viewOptions.filters,
                    ...(this.viewOptions.filters?.current_target || {}),
                    ...this.viewOptions,
                    ...this.viewOptions.variables
                  }
                ),
                { needMessage: false }
              )
              .then(res => {
                const legendStatusData = res.legend_data.statusList.map(item => ({
                  ...item,
                  show: true
                }));
                const legendStatisticsData = res.legend_data.statistics.map(option => ({
                  ...option,
                  data: option.data.map(val => ({
                    ...val,
                    select: false
                  }))
                }));
                this.filterList = res.filter_list;
                const graphData = {
                  ...res,
                  edges: res.edges.map(edge => ({
                    ...edge,
                    type: 'line-dash', // 使用自定义的边类型
                    direction: edge.type // 后端定义的 type 为边的方向（单向/双向）
                  }))
                };
                this.graphData = graphData;
                this.legendStatusData = legendStatusData;
                this.legendStatisticsData = legendStatisticsData;
                this.clearErrorMsg();
                return true;
              })
              .catch(error => {
                this.handleErrorMsgChange(error.msg || error.message);
              });
          });
      } else {
        promiseList = this.panel.targets
          .filter(item => item.dataType === 'table')
          .map(item =>
            (this as any).$api[item.apiModule]
              [item.apiFunc](
                variablesService.transformVariables(
                  {
                    ...item.data,
                    ...params,
                    filter: this.filter === 'all' ? '' : this.filter,
                    sort: this.sortKey,
                    filter_dict: this.tableFilterDict,
                    page: this.pagination.current,
                    page_size: this.pagination.limit,
                    keyword: this.keyword,
                    condition_list: transformConditionValueParams(this.conditionList),
                    view_options: {
                      ...this.viewOptions
                    }
                  },
                  {
                    ...this.viewOptions.filters,
                    ...(this.viewOptions.filters?.current_target || {}),
                    ...this.viewOptions,
                    ...this.viewOptions.variables
                  }
                ),
                { needMessage: false }
              )
              .then(({ columns, data, total, condition_list }) => {
                this.emptyStatusType = this.keyword || this.filter !== 'all' ? 'search-empty' : 'empty';
                this.tableData = data || [];
                this.columns = (columns || []).map(item => ({
                  ...item,
                  checked: this.checkedColumns.length ? this.checkedColumns.includes(item.id) : item.checked
                }));
                this.conditionOptions = condition_list || [];
                this.pagination.count = total || 0;
                this.clearErrorMsg();
                return true;
              })
              .catch(error => {
                this.handleErrorMsgChange(error.msg || error.message);
              })
          );
      }
      const res = await Promise.all(promiseList).catch(() => false);

      if (res) {
        this.inited = true;
        if (this.isOverview) {
          this.empty = !this.graphData.nodes.length;
          this.emptyText = !this.graphData.nodes.length ? window.i18n.tc('查无数据') : '';
          if (!this.empty) {
            this.initGraph();
          }
        } else {
          this.empty = !this.tableData.length;
          this.emptyText = !this.tableData.length ? window.i18n.tc('查无数据') : '';
        }
      } else {
        this.empty = true;
        this.emptyText = window.i18n.tc('出错了');
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      if (this.isOverview) {
        this.emptyStatusType = '500';
      }
      console.error(e);
    }
    this.handleLoadingChange(false);
  }
  handleTimeRangeChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }
  /**
   * @description: 初始化实例拓扑图
   */
  initGraph() {
    setTimeout(() => {
      const { width, height } = (this.$refs.graphContainer as HTMLDivElement).getBoundingClientRect();
      this.canvasWidth = width;
      this.canvasHeight = height;
      // 自定义节点
      G6.registerNode(
        'custom-node',
        {
          /**
           * 绘制节点，包含文本
           * @param  {Object} cfg 节点的配置项
           * @param  {G.Group} group 图形分组，节点中图形对象的容器
           * @return {G.Shape} 返回一个绘制的图形作为 keyShape，通过 node.get('keyShape') 可以获取。
           */
          draw: (cfg, group) => this.drawNode(cfg, group),
          /**
           * 设置节点的状态，主要是交互状态，业务状态请在 draw 方法中实现
           * 单图形的节点仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
           * @param  {String} name 状态名称
           * @param  {Object} value 状态值
           * @param  {Node} node 节点
           */
          setState: (name, value, item) => this.setNodeState(name, value, item)
        },
        'circle'
      );
      // 自定义边
      G6.registerEdge(
        'line-dash',
        {
          /**
           * 绘制边，包含文本
           * @param  {Object} cfg 边的配置项
           * @param  {G.Group} group 图形分组，边中的图形对象的容器
           * @return {G.Shape} 绘制的图形，通过 node.get('keyShape') 可以获取到
           */
          draw: (cfg, group) => this.drawLine(cfg, group),
          /**
           * 设置边的状态，主要是交互状态，业务状态请在 draw 方法中实现
           * 单图形的边仅考虑 selected、active 状态，有其他状态需求的用户自己复写这个方法
           * @param  {String} name 状态名称
           * @param  {Object} value 状态值
           * @param  {Edge} edge 边
           */
          setState: (name, value, item) => this.setEdgeState(name, value, item)
        },
        this.serviceName ? 'cubic-horizontal' : 'quadratic'
      );

      this.graph = new G6.Graph({
        container: this.$refs.graphContainer as HTMLElement, // 指定挂载容器
        width: this.canvasWidth,
        height: this.canvasHeight,
        minZoom: this.minZoomVal, // 画布最小缩放比例
        maxZoom: this.maxZoomVal, // 画布最大缩放比例
        fitCenter: true, // 图的中心将对齐到画布中心
        fitView: true, // 将图适配到画布大小，可以防止超出画布或留白太多
        animate: false,
        modes: {
          // 设置画布的交互模式
          default: [
            'drag-canvas', // 拖拽画布
            'zoom-canvas', // 缩放画布
            !!this.serviceName ? '' : 'drag-node' // 拖拽节点 服务拓扑不可拖拽节点
          ]
        },
        /** 图布局 */
        layout: { ...this.graphLayout },
        defaultEdge: {
          // 边的配置
          type: 'line-dash',
          style: {
            stroke: '#979BA5',
            lineWidth: 1
          }
        },
        defaultNode: {
          // 节点配置
          type: 'custom-node'
        },
        plugins: [
          // 插件配置
          this.nodeTooltip(), // 节点tooltips
          this.contextMenu() // 节点菜单
        ]
      });
      this.bindListener(this.graph); // 图监听事件
      this.graph.data(this.graphData); // 读取数据源到图上
      this.graph.render(); // 渲染图
    }, 30);
  }
  /**
   * 绘制节点，包含文本
   * @param  {Object} cfg 节点的配置项
   * @param  {G.Group} group 图形分组，节点中图形对象的容器
   * @return {G.Shape} 返回一个绘制的图形作为 keyShape，通过 node.get('keyShape') 可以获取。
   */
  drawNode(cfg, group) {
    // 节点基础结构
    const keyShape = group.addShape('circle', {
      attrs: {
        fill: '#fff', // 填充颜色,
        stroke: `${cfg.stroke}`, // 描边颜色
        lineWidth: cfg.have_data ? 4 : 2, // 描边宽度
        cursor: 'pointer', // 手势类型
        r: Number(cfg.size) // 圆半径
      },
      name: 'custom-node-keyShape'
    });

    if (this.serviceName && this.serviceName === cfg.name) {
      // 展开服务当前服务节点外边框
      group.addShape('circle', {
        attrs: {
          stroke: '#979BA5', // 描边颜色
          lineWidth: 28, // 描边宽度
          cursor: 'pointer', // 手势类型
          r: Number(cfg.size + 14 + (cfg.have_data ? 2 : 1)), // 圆半径
          opacity: 0.08
        },
        name: 'custom-node-outline'
      });
    }

    // 节点label
    if (cfg.name) {
      let positionObj = {};
      switch (cfg.topo_level) {
        case 'upstream':
          positionObj = {
            x: -Number(cfg.size) - 12,
            y: Number(cfg.size) / 6, // label在y轴上的偏移
            textAlign: 'right'
          };
          break;
        case 'downstream':
          positionObj = {
            x: Number(cfg.size) + 12,
            y: Number(cfg.size) / 6 // label在y轴上的偏移
          };
          break;
        default:
          positionObj = {
            x: 0,
            y: Number(cfg.size + 12), // label在y轴上的偏移
            textAlign: 'center' // 文本内容的当前对齐方式
          };
      }
      group.addShape('text', {
        attrs: {
          ...positionObj,
          text: cfg.name, //  文本内容
          fill: '#222', // 填充颜色,
          fontSize: 14,
          lineWidth: 3, // 描边宽度
          stroke: '#fff' // 描边颜色
        },
        name: 'text-shape',
        // 设置 draggable 以允许响应鼠标的图拽事件
        draggable: true
      });
    }
    // 节点中心icon
    group.addShape('image', {
      attrs: {
        x: -12,
        y: -12,
        width: 24,
        height: 24,
        cursor: 'pointer', // 手势类型
        img: cfg.icon // 图片资源
      },
      name: 'node-icon-shape',
      // 设置 draggable 以允许响应鼠标的图拽事件
      draggable: true
    });
    // 语言标签
    if (cfg.have_data && cfg.language_icon) {
      group.addShape('circle', {
        attrs: {
          x: -cfg.size / 2 - 12,
          y: -cfg.size / 2 - 12,
          fill: '#FAFBFD',
          stroke: `#979BA5`, // 描边颜色
          lineWidth: 1, // 描边宽度
          r: 10 // 圆半径
        },
        name: 'language-circle'
      });
      group.addShape('image', {
        attrs: {
          x: -cfg.size / 2 - 18.5,
          y: -cfg.size / 2 - 18.5,
          width: 13,
          height: 13,
          img: cfg.language_icon
        },
        name: 'language-image-shape'
      });
    }
    // 起始服务 icon
    if (cfg.have_data && cfg.is_root_service) {
      group.addShape('circle', {
        attrs: {
          x: -cfg.size / 2 - 12,
          y: -cfg.size / 2 - 12 + 25,
          fill: '#EDF4FF',
          stroke: `#3A84FF`, // 描边颜色
          lineWidth: 1, // 描边宽度
          r: 10 // 圆半径
        },
        name: 'start-circle'
      });
      group.addShape('image', {
        attrs: {
          x: -cfg.size / 2 - 16.5,
          y: -cfg.size / 2 - 16.5 + 25,
          width: 10,
          height: 10,
          img: bannerIcon
        },
        name: 'start'
      });
    }
    // 展开服务节点 返回按钮
    if (this.isDrillDown && this.serviceName === cfg.name) {
      group.addShape('text', {
        attrs: {
          x: 6,
          y: Number(cfg.size + 46), // label在y轴上的偏移
          textAlign: 'center', // 文本内容的当前对齐方式
          text: this.$t('返回应用'), //  文本内容
          fill: '#3A84FF', // 填充颜色,
          fontSize: 12,
          lineWidth: 3, // 描边宽度
          cursor: 'pointer' // 手势类型
        },
        name: 'back-text-shape',
        // 设置 draggable 以允许响应鼠标的图拽事件
        draggable: true
      });

      group.addShape('image', {
        attrs: {
          x: -30,
          y: Number(cfg.size + 36), // label在y轴上的偏移
          width: 10,
          height: 10,
          img: backIcon,
          cursor: 'pointer' // 手势类型
        },
        name: 'back-icon-shape'
      });
    }
    return keyShape;
  }
  /**
   * @description: 自定义节点 state 状态设置
   * @param  {String} name 状态名称
   * @param  {Object} value 状态值
   * @param  {Node} node 节点
   */
  setNodeState(name, value, item) {
    const group = item.get('group');
    if (name === 'disabled') {
      // 节点、label、中心icon 切换 disabled 状态
      const nodeShape = group.find(e => e.get('name') === 'custom-node-keyShape');
      const labelShape = group.find(e => e.get('name') === 'text-shape');
      const iconShape = group.find(e => e.get('name') === 'node-icon-shape');
      const languageCircle = group.find(e => e.get('name') === 'language-circle');
      const languageImageShape = group.find(e => e.get('name') === 'language-image-shape');
      const startCircle = group.find(e => e.get('name') === 'start-circle');
      const start = group.find(e => e.get('name') === 'start');
      [nodeShape, labelShape, iconShape, languageCircle, languageImageShape, startCircle, start].forEach(
        shape => shape?.attr({ opacity: value ? 0.1 : 1 })
      );
    }
  }
  /**
   * 绘制边，包含文本
   * @param  {Object} cfg 边的配置项
   * @param  {G.Group} group 图形分组，边中的图形对象的容器
   * @return {G.Shape} 绘制的图形，通过 node.get('keyShape') 可以获取到
   */
  drawLine(cfg, group) {
    const endArrow = {
      path: G6.Arrow.triangle(10, 10, 0), // 路径
      fill: '#979BA5', // 填充颜色
      stroke: '#979BA5', // 描边颜色
      strokeOpacity: 0 // 描边透明度
    };
    // 双向箭头连线
    const startArrow = cfg.direction === 'complex' ? endArrow : false;

    const keyShape = group.addShape('path', {
      attrs: {
        path: G6.Arrow.triangle(10, 10, 0), // 路径
        startArrow,
        endArrow
      },
      className: 'edge-shape',
      name: 'edge-shape'
    });
    return keyShape;
  }
  /**
   * @description: 自定义边 state 状态设置
   * @param  {String} name 状态名称
   * @param  {Object} value 状态值
   * @param  {item} item 边
   */
  setEdgeState(name, value, item) {
    const lineDash = [4, 4];
    const group = item.get('group');
    if (name === 'focus') {
      const keyShape = group.find(ele => ele.get('name') === 'edge-shape');
      if (value) {
        let index = 0;
        const totalLength = lineDash[0] + lineDash[1];
        // 设置边属性
        keyShape.attr({
          endArrow: {
            path: G6.Arrow.triangle(10, 10, 0), // 线条路径 String | Array
            fill: '#979BA5', // 填充颜色
            stroke: '#979BA5', // 描边颜色
            strokeOpacity: 0 // 描边透明度
          }
        });
        // 设置边动画
        keyShape.animate(
          () => {
            index += 1;
            if (index > totalLength) index = 0;
            return { lineDash, lineDashOffset: -index };
          },
          {
            repeat: true, // whether executes the animation repeatly
            duration: 3000 // the duration for executing once
          }
        );
      } else {
        // 停止动画
        keyShape.stopAnimate();
        keyShape.attr({
          strokeOpacity: 1, // 描边透明度
          lineDash: [] // 恢复实线
        });
      }
    }
    if (name === 'disabled') {
      const keyShape = group.find(ele => ele.get('name') === 'edge-shape');
      if (value) {
        keyShape.attr({
          strokeOpacity: 0.2,
          lineDash: []
        });
      } else {
        keyShape.attr({
          strokeOpacity: 1,
          lineDash: []
        });
      }
    }
  }
  /**
   * @description: 节点菜单点击事件
   * @param { HTMLElement } target
   * @param { Item } item
   */
  handleNodeMenuClick(target, item) {
    if (this.readonly) return;
    // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
    const linkObj = JSON.parse(target.closest('li')?.id || '');
    const linkClick = item => {
      if (!item.url) return;
      if (item.target === 'self') {
        this.$router.push({
          path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${item.url}`.replace(/\/\//g, '/')
        });
        return;
      }
      if (item.target === 'event') {
        bus.$emit(item.key, item);
      } else {
        window.open(item.url, random(10));
      }
    };
    if (item) {
      // 节点菜单
      const { id } = linkObj;
      const model = item?.getModel();
      if (id === 'down' && model) {
        const isUp = this.serviceName === model.id;
        if (isUp) {
          /** 上钻 */
          this.handleBack();
          return;
        }
        /** 下钻 */
        this.isDrillDown = true;
        this.serviceName = model.id;
        this.getPanelData();
      } else {
        linkClick(linkObj);
      }
    } else {
      // 空白处菜单
      linkClick(linkObj);
    }
  }
  /**
   * @description: 定义节点 tooltip 内容
   * @param { HTMLElement } e
   */
  getTooltipsContent(e) {
    const outDiv = document.createElement('div');
    const {
      id,
      label,
      stroke,
      tips,
      kind,
      language_icon: languageIcon,
      language,
      is_root_service: isRootService
    } = e.item.getModel();
    const isService = kind === 'service';

    outDiv.innerHTML = `
        <h3 class='node-label'>
          <span class='label-mark' style='background-color: ${stroke}'></span>
          <div style="min-height:32px;">
            <div class='node-text'>${label || id}</div>
            <img
              class='language-icon'
              src='${languageIcon}'
              alt='${language}'
              style="display: ${languageIcon && isService ? '' : 'none'}" />
            <span class='language-name' style="display: ${!isService ? 'none' : ''}">${language}</span>
          </div>
          <div class='root-node-mark' style="display: ${isRootService && isService ? 'flex' : 'none'}">
            <img class='root-icon' src='${bannerIcon}'  alt=''/>
            <span>${this.$t('起始')}</span>
          </div>
        </h3>
        <ul class='node-message'>
          ${tips
            .map(
              tip =>
                `<li><div class='value'>${tip.value}</div><div style='color: rgba(0,0,0,0.60);'>${tip.name}</div></li>`
            )
            .join('')}
        </ul>
      `;
    return outDiv;
  }
  /**
   * @description: 实例的监听事件
   */
  bindListener(graph) {
    // 鼠标进入 hover
    graph.on('node:mouseenter', evt => {
      if (['back-text-shape', 'back-icon-shape'].includes(evt.target?.cfg?.name)) return false;

      this.clearFocusEdgeState();

      const { item } = evt;
      const { id } = item._cfg;
      const neighbors = graph.getNeighbors(id);
      const allEdges = [];
      graph.getNodes().forEach(node => {
        if (neighbors.includes(node) || node === item) {
          // 当前节点和所有相邻节点保持高亮
          graph.setItemState(node, 'disabled', false);
        } else {
          // 其余节点置灰 disabled
          graph.setItemState(node, 'disabled', true);
        }

        // 获取所有边且去重
        node.getEdges().forEach(edge => {
          if (!allEdges.includes(edge)) allEdges.push(edge);
        });
      });
      allEdges.forEach(edge => graph.setItemState(edge, 'disabled', false));
      const relatedEdges = item.getEdges();
      const unRelatedEdges = allEdges.filter(edge => !relatedEdges.includes(edge));
      // 所有不关联的边置灰 disabled
      unRelatedEdges.forEach(edge => graph.setItemState(edge, 'disabled', true));
      // 所有关联的边高亮 focus
      relatedEdges.forEach(edge => graph.setItemState(edge, 'focus', true));
    });

    // 鼠标离开
    graph.on('node:mouseleave', evt => {
      if (['back-text-shape', 'back-icon-shape'].includes(evt.target?.cfg?.name)) return false;
      this.clearFocusItemState(graph);
    });

    graph.on('afterrender', () => {
      this.isRendered = true;
      const zoom = this.graph.getZoom();
      this.zoomValue = zoom;
      this.initZoomValue = zoom;
      if (zoom > 1) {
        /** 下钻服务节点较少 防止自适应缩放过大 */
        this.graph.zoomTo(1, { x: this.canvasWidth / 2, y: this.canvasHeight / 2 });
        this.zoomValue = 1;
        this.initZoomValue = 1;
      }
      this.handleHighlightNode();
    });

    graph.on('afterlayout', () => {
      this.isRendered = true;
    });

    graph.on('wheelzoom', () => {
      this.zoomValue = this.graph.getZoom();
    });
  }
  /**
   * @description: 重写ResizeMixin的handleResize方法
   */
  handleResize() {
    if (!this.graph || this.graph.get('destroyed')) return;
    const { width, height } = (this.$refs.graphContainer as HTMLDivElement).getBoundingClientRect();
    this.canvasWidth = width;
    this.canvasHeight = height;
    // 修改画布大小
    this.graph.changeSize(width, height);
    // 将拓扑图移到画布中心
    this.graph.fitCenter();
    this.graph.fitView();
  }
  /**
   * @description: 缩放
   * @param { number } ratio 缩放比例
   */
  handleGraphZoom(ratio) {
    this.zoomValue = ratio;
    // 以画布中心为圆心放大/缩小
    this.graph.zoomTo(ratio, { x: this.canvasWidth / 2, y: this.canvasHeight / 2 });
  }
  /**
   * @desc 清楚所有选中状态
   */
  clearFocusItemState(graph) {
    if (!graph) return;

    this.clearFocusEdgeState();
  }
  /**
   * @desc 清除图上所有节点和边的 focus、unSelected 状态及相应样式
   * @param { Object } graph
   */
  clearFocusEdgeState() {
    const focusEdges = this.graph.findAllByState('edge', 'focus');
    // 取消与选中节点关联边的 focus 状态
    focusEdges.forEach(fedge => this.graph.setItemState(fedge, 'focus', false));
    this.handleHighlightNode();
  }
  /* 切换总览/列表 */
  handleOverview(value: boolean) {
    this.empty = true;
    this.emptyText = window.i18n.tc('加载中...');
    this.isOverview = value;
    this.tableFilterDict = {};
    if (!this.isOverview) {
      this.graph.destroy();
      this.graph = null;
    }
    this.$nextTick(() => {
      this.getPanelData();
    });
  }
  /* 列表筛选 */
  handleSortChange({ prop, order }) {
    switch (order) {
      case 'ascending':
        this.sortKey = prop;
        break;
      case 'descending':
        this.sortKey = `-${prop}`;
        break;
      default:
        this.sortKey = undefined;
    }
    this.getPanelData();
  }
  /** 列表数据项筛选 */
  handleTableFilterChange(filters: IFilterDict) {
    this.tableFilterDict = filters;
    this.pagination.current = 1;
    this.getPanelData();
  }
  /* 列表分页 */
  async handleLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    this.getPanelData();
  }
  /**
   * @description: 切换分页
   * @param {number} page
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.getPanelData();
  }
  /**
   * @desc 表头字段设置
   * @param { array } list
   */
  handleColumnChange(list: string[]) {
    this.checkedColumns = list;
  }
  /* 关键字搜索 */
  handleSearchChange(value: string | number) {
    this.keyword = value as any;
    if (this.isOverview) {
      this.handleHighlightNode();
    } else {
      this.pagination.current = 1;
      this.getPanelData();
    }
  }
  /* 条件搜索 */
  handleConditionChange() {}
  /* 回中 */
  handlebackToCenter() {
    this.graph.fitView();
    this.zoomValue = this.initZoomValue;
  }
  /*  是否显示无数据节点 */
  handleShowNodata(v: boolean) {
    this.showNoData = v;
    if (this.isOverview) {
      this.handleHighlightNode();
    } else {
      this.pagination.current = 1;
      this.getPanelData();
    }
  }
  /** 根据当前所选分类显示高亮节点 */
  handleHighlightNode() {
    const showAll = this.filter === 'all';
    const targetNodes = []; // 所选分类节点
    const allEdges = []; // 所有边
    const allNodes = this.graph.getNodes(); // 所有节点

    allNodes.forEach(node => {
      const model = node.getModel();
      // 关键字搜索匹配
      const isKeywordMatch = model.name.toLowerCase().includes(this.keyword.toLowerCase());
      // 是否展示无数据节点
      const isShowNoDataNode = this.showNoData ? true : model.have_data;
      // 图例过滤
      const isLegendFilter = this.handleLegendFilterNode(model);
      // 高亮当前分类的节点 根据分类、关键字搜索匹配过滤
      const isDisabled =
        !isShowNoDataNode ||
        !isLegendFilter ||
        (showAll ? !isKeywordMatch : model.category !== this.filter || !isKeywordMatch);
      this.graph.setItemState(node, 'disabled', isDisabled);
      // 保存高亮节点 用于设置关联边高亮
      if (!isDisabled) targetNodes.push(model.id);

      // 获取所有边且去重
      node.getEdges().forEach(edge => {
        if (!allEdges.includes(edge)) allEdges.push(edge);
      });
    });

    allEdges.forEach(edge => {
      const edgeModel = edge.getModel();
      // source、target均是高亮节点的边
      const isRelated = [edgeModel.source, edgeModel.target].every(item => targetNodes.includes(item));
      this.graph.setItemState(edge, 'disabled', !isRelated);
    });
  }
  /* 头部过滤 */
  handleFilterChange(filter: string) {
    this.filter = filter;
    if (this.isOverview) {
      this.handleHighlightNode();
    } else {
      this.pagination.current = 1;
      this.getPanelData();
    }
  }
  /** 清空筛选条件 */
  handleClearFilter() {
    this.filter = '';
    this.keyword = '';
    this.pagination.current = 1;
    this.getPanelData();
  }
  /* 切换全屏 */
  handleFullScreen() {
    this.isFullScreen = !this.isFullScreen;
    if (this.isFullScreen) {
      if (this.$el.requestFullscreen) {
        this.$el.requestFullscreen();
      }
    } else {
      document.exitFullscreen();
    }
  }
  handleBack() {
    this.isDrillDown = false;
    this.serviceName = '';
    this.getPanelData();
  }

  /* 切换右下角类型 */
  async handleChangeStatistics(v: string) {
    this.sizeCategory = v;
    await this.getPanelData();
    this.legendKey = random(8);
  }

  /** 选中图例 */
  handleSelectLegend({ actionType, item, option }: { actionType: LegendActionType; item: any; option: string }) {
    if (actionType === 'shift-click') {
      if (option === 'status') {
        this.legendStatusData = this.legendStatusData.map(legend => ({
          ...legend,
          show: item.color === legend.color ? !legend.show : legend.show
        }));
      } else {
        this.legendStatisticsData = this.legendStatisticsData.map(statis => ({
          ...statis,
          data:
            statis.id === option
              ? statis.data.map(val => ({
                  ...val,
                  select: item.size === val.size ? !val.select : val.select
                }))
              : statis.data
        }));
      }
    } else if (actionType === 'click') {
      if (option === 'status') {
        const hasOtherShow = this.legendStatusData.some(set => set.name !== item.name && set.show);
        this.legendStatusData = this.legendStatusData.map(legend => ({
          ...legend,
          show: legend.color === item.color || !hasOtherShow
        }));
      } else {
        const hasOtherSelect = this.legendStatisticsData.some(statistics =>
          statistics.data.some(set => set.size !== item.size && set.select)
        );
        this.legendStatisticsData = this.legendStatisticsData.map(statis => ({
          ...statis,
          data:
            statis.id === option
              ? statis.data.map(val => ({
                  ...val,
                  select: val.size === item.size || (!item.select ? false : !hasOtherSelect)
                }))
              : statis.data
        }));
      }
    }
    if (option === 'status') {
      this.legendFilters.status = this.legendStatusData.filter(legend => legend.show).map(legend => legend.color);
    } else {
      this.legendFilters[option] = this.legendStatisticsData
        .find(statistics => statistics.id === option)
        .data.filter(legend => legend.select)
        .map(legend => legend.name);
    }
    this.handleHighlightNode();
  }

  /** 根据图例筛选节点是否高亮 */
  handleLegendFilterNode(node) {
    return Object.keys(this.legendFilters).every(legend => {
      const selectArr = this.legendFilters[legend];
      let isShow = true;
      switch (legend) {
        case 'status':
          isShow = selectArr.includes(node.stroke);
          break;
        case 'request_count':
          isShow = this.handleStatisticFilter(node, selectArr, 'request_count');
          break;
        case 'avg_duration':
          isShow = this.handleStatisticFilter(node, selectArr, 'avg_duration');
          break;
        default:
          break;
      }
      return !selectArr.length || isShow;
    });
  }

  handleStatisticFilter(node, list, option) {
    if (!list.length) return true;

    let targetValue = node.tips?.find(item => item.id === option)?.value;
    if (!targetValue || targetValue === '--') return false;
    return list.some(val => {
      let minLimit = val.split('~')[0];
      let maxLimit = val.split('~')?.[1] || null;

      if (option === 'request_count') {
        if (minLimit.includes('k')) minLimit = minLimit.replace('k', '000').replace(/[^0-9]/gi, '');
        if (maxLimit?.includes('k')) maxLimit = maxLimit.replace('k', '000').replace(/[^0-9]/gi, '');
        return Number(targetValue) >= Number(minLimit) && (!maxLimit ? true : Number(targetValue) < Number(maxLimit));
      }

      if (minLimit.includes('ms')) minLimit = minLimit.replace(/[^0-9]/gi, '');
      if (maxLimit?.includes('ms')) {
        maxLimit = maxLimit.replace(/[^0-9]/gi, '');
      } else if (maxLimit?.includes('s')) {
        maxLimit = maxLimit.replace('s', '000').replace(/[^0-9]/gi, '');
      }
      if (targetValue.includes('ms')) {
        targetValue = targetValue.replace('ms', '');
      }
      if (['s', 'min', 'h', 'd'].some(val => targetValue.includes(val)) && !maxLimit) return true;
      return Number(targetValue) >= Number(minLimit) && Number(targetValue) < Number(maxLimit);
    });
  }

  handleOperation(val: EmptyStatusOperationType) {
    if (val === 'clear-filter') {
      this.chartTitle.handleClearFilter();
    } else if (val === 'refresh') {
      this.emptyStatusType = '500';
      this.getPanelData();
    }
  }

  render() {
    return (
      <div class='relation-graph'>
        <RelationChartTitle
          ref='chartTitle'
          isOverview={this.isOverview}
          filterList={this.filterList}
          showNoData={this.showNoData}
          conditionOptions={this.conditionOptions}
          isFullScreen={this.isFullScreen}
          onOverview={this.handleOverview}
          onSearchChange={this.handleSearchChange}
          onConditionChange={this.handleConditionChange}
          onbackToCenter={this.handlebackToCenter}
          onShowNodata={this.handleShowNodata}
          onFilterChange={this.handleFilterChange}
          onFullScreen={this.handleFullScreen}
          onClearFilter={this.handleClearFilter}
        />
        {this.isOverview ? (
          <div class='graph-main'>
            {!this.empty ? (
              <div
                ref='graphContainer'
                class='graph-container'
              >
                {this.isRendered && (
                  <div class='zoom-bar'>
                    <span
                      class='icon-monitor icon-plus-line'
                      onClick={() => this.handleGraphZoom(this.zoomValue + 0.1)}
                    ></span>
                    <bk-slider
                      v-model={this.zoomValue}
                      class='slider-wrap'
                      height='82px'
                      show-tip={false}
                      vertical={true}
                      min-value={this.minZoomVal}
                      max-value={this.maxZoomVal}
                      step={0.1}
                      onChange={value => this.handleGraphZoom(value)}
                    ></bk-slider>
                    <span
                      class='icon-monitor icon-minus-line'
                      onClick={() => this.handleGraphZoom(this.zoomValue - 0.1)}
                    ></span>
                  </div>
                )}
                {!this.isRendered && <div class='empty-chart empty-loading'>Loading...</div>}
              </div>
            ) : (
              <div class='empty-chart'>{this.emptyText}</div>
            )}
          </div>
        ) : (
          <div class='table-container'>
            <CommonTable
              style='background: #fff;'
              checkable={false}
              data={this.tableData}
              columns={this.columns}
              defaultSize='small'
              paginationType='simple'
              pagination={this.pagination}
              onSortChange={this.handleSortChange}
              // eslint-disable-next-line @typescript-eslint/no-misused-promises
              onLimitChange={this.handleLimitChange}
              onPageChange={this.handlePageChange}
              onColumnSettingChange={this.handleColumnChange}
              onFilterChange={this.handleTableFilterChange}
            >
              <EmptyStatus
                type={this.emptyStatusType}
                slot='empty'
                onOperation={this.handleOperation}
              />
            </CommonTable>
          </div>
        )}

        {this.isOverview && this.graphData && !this.empty && this.isRendered ? (
          <RatioLegend
            key={this.legendKey}
            legendStatusData={this.legendStatusData}
            statistics={this.legendStatisticsData}
            sizeCategory={this.sizeCategory}
            // eslint-disable-next-line @typescript-eslint/no-misused-promises
            onStatisticsChange={this.handleChangeStatistics}
            onSelectLegend={this.handleSelectLegend}
          />
        ) : undefined}
      </div>
    );
  }
}

export default ofType<IRelationGraphProps>().convert(RelationGraph);
