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

import { Component, Inject, InjectReactive, Ref } from 'vue-property-decorator';
// import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
// import type { PanelModel } from '../../typings';
import { dataTypeBarQuery } from 'monitor-api/modules/apm_topo';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import { CommonSimpleChart } from '../common-simple-chart';
import StatusTab from '../table-chart/status-tab';
import ApmRelationGraphContent from './components/apm-relation-graph-content';
import ApmRelationTopo from './components/apm-relation-topo';
import BarAlarmChart from './components/bar-alarm-chart';
import ResourceTopo from './components/resource-topo';
import ServiceOverview from './components/service-overview';
import { alarmBarChartDataTransform, DATA_TYPE_LIST, EDataType } from './components/utils';

import type { ITableColumn, ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings/table';

import './apm-relation-graph.scss';

enum EColumn {
  avgTime = 'avg_time',
  callCount = 'call_count',
  callService = 'call_service',
  callType = 'call_type',
  errorRate = 'error_rate',
  operate = 'operate',
  serverName = 'service_name',
}

const sideTopoMinWidth = 400;
const sideOverviewMinWidth = 320;

@Component
export default class ApmRelationGraph extends CommonSimpleChart {
  @Ref('content-wrap') contentWrap: ApmRelationGraphContent;

  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'enableSelectionRestoreAll', default: false }) readonly enableSelectionRestoreAll: boolean;
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (
    value: [number | string, number | string]
  ) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;
  /* 概览图、列表图切换 */
  showTypes = [
    {
      id: 'topo',
      icon: 'icon-mc-overview',
    },
    {
      id: 'table',
      icon: 'icon-mc-list',
    },
  ];
  showType = 'topo';
  /* 数据类型 */
  dataType = EDataType.Alert;

  /* 筛选列表 */
  filterList = [
    {
      id: 'all',
      name: '全部',
      icon: 'icon-gailan',
    },
    {
      id: 'http',
      name: '网页',
      icon: 'icon-wangye',
    },
    {
      id: 'rpc',
      name: '远程调用',
      icon: 'icon-yuanchengfuwu',
    },
    {
      id: 'db',
      name: '数据库',
      icon: 'icon-DB',
    },
    {
      id: 'messaging',
      name: '消息队列',
      icon: 'icon-xiaoxizhongjianjian',
    },
    {
      id: 'async_backend',
      name: '后台任务',
      icon: 'icon-renwu',
    },
    {
      id: 'other',
      name: '其他',
      icon: 'icon-zidingyi',
    },
  ];
  curFilter = 'all';
  /* 展开列表 */
  expandList = [
    {
      id: 'topo',
      icon: 'icon-ziyuan',
    },
    {
      id: 'overview',
      icon: 'icon-mc-overview',
    },
  ];
  expanded = ['topo', 'overview'];

  /* 表格数据 */
  tableColumns: ITableColumn[] = [];
  tableData = [];
  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 2,
    limit: 10,
    showTotalCount: true,
  };

  searchValue = '';

  graphData = {
    nodes: [],
    edges: [],
  };

  /* 获取头部告警柱状条形图数据方法 */
  getAlarmBarData = null;

  get appName() {
    return this.panel?.options?.apm_relation_graph?.app_name || '';
  }

  get serviceName() {
    return this.panel?.options?.apm_relation_graph?.service_name || '';
  }

  /* 当前图表内参数 */
  get filters() {
    return {
      app_name: this.appName,
      service_name: this.serviceName,
      data_type: this.dataType,
      search: this.searchValue,
    };
  }

  created() {
    this.tableColumns = [
      {
        type: 'link',
        id: EColumn.serverName,
        name: window.i18n.tc('服务名称'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.callType,
        name: window.i18n.tc('调用类型'),
      },
      {
        type: 'string',
        id: EColumn.callService,
        name: window.i18n.tc('调用服务'),
      },
      {
        type: 'number',
        id: EColumn.callCount,
        name: window.i18n.tc('调用数'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.errorRate,
        name: window.i18n.tc('错误率'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.avgTime,
        name: window.i18n.tc('平均响应耗时'),
      },
      {
        type: 'scoped_slots',
        id: EColumn.operate,
        name: window.i18n.tc('操作'),
      },
    ];
    setTimeout(() => {
      this.graphData = {
        nodes: [
          {
            id: 'node0',
            name: '节点0',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTUxMiAxNS4wNGE0OTcuOTIgNDk3LjkyIDAgMCAxIDQ5Ny4wMjQgNDk3LjA4OCA0OTYuODMyIDQ5Ni44MzIgMCAwIDEtMTQ1LjcyOCAzNTEuNjhBNDk0LjQgNDk0LjQgMCAwIDEgNTEyIDEwMDguOTZhNDkzLjgyNCA0OTMuODI0IDAgMCAxLTM1MS4zNi0xNDUuMTUyIDQ5Ni44MzIgNDk2LjgzMiAwIDAgMS0xNDUuNTM2LTM1MS42OEE0OTcuOTIgNDk3LjkyIDAgMCAxIDUxMiAxNS4wNHptLTIyLjc4NCA5MTcuMTJWNzcxLjUyYTQwNS4xMiA0MDUuMTIgMCAwIDAtMTI5LjE1MiAyNi42MjQgMTMxLjY1MiAxMzEuNjUyIDAgMCAwLTE3LjA4OCA2LjQ2NGMzLjUyIDcuMDQgNi43ODQgMTQuMDggMTAuNTYgMjAuOTI4IDI1LjUzNiA0NS41NjggNTUuMzYgODAuODk2IDg4Ljk2IDEwMS4xODQgMTUuNDg4IDIuODE2IDMxLjA0IDQuNjA4IDQ2LjcyIDUuNDR6bTMyMC4xMjgtNzE3LjEyYTEyOC43NjggMTI4Ljc2OCAwIDAgMC0xMC42MjQtMTAuMDQ4IDQ0MS4yMTYgNDQxLjIxNiAwIDAgMS01OC4yNCAzNi45MjhjMjcuMDcyIDcwLjc4NCA0My45MDQgMTU2LjAzMiA0Ni41OTIgMjQ3LjQyNGgxNDQuODk2QTQxOS42NDggNDE5LjY0OCAwIDAgMCA4MDkuMzQ0IDIxNS4wNHptLTQ2LjcyLTQwLjM4NGE0MTUuMzYgNDE1LjM2IDAgMCAwLTg1LjY5Ni00OS40NzJjMTIuNDE2IDE2LjM4NCAyMy42OCAzMy42IDMzLjY2NCA1MS41ODQgMy44NCA3LjA0IDcuODcyIDE1LjIzMiAxMS45MDQgMjMuMzYgMTMuNTY4LTguMTI4IDI3LjEzNi0xNi41NzYgNDAuMTI4LTI1LjUzNnpNNTgxLjQ0IDk3LjIxNmE1MzIuMzUyIDUzMi4zNTIgMCAwIDAtNDYuNjU2LTUuMTJ2MTYxLjIxNmE0MjguOTkyIDQyOC45OTIgMCAwIDAgMTQ2LjE3Ni0zMy40MDhjLTIuOTQ0LTcuMjk2LTcuMDQtMTQuMzM2LTEwLjQ5Ni0yMC44NjQtMjQuOTYtNDYuMTQ0LTU1LjY4LTgwLjg5Ni04OS4wMjQtMTAxLjc2em0tOTIuMjI0LTUuMTJhNTM0LjAxNiA1MzQuMDE2IDAgMCAwLTQ2LjcyIDUuMTJjLTMzLjYgMjAuOTI4LTYzLjQyNCA1NS42OC04OC45NiAxMDEuODI0LTMuNzc2IDYuNTI4LTcuMDQgMTMuNTY4LTEwLjgxNiAyMC44NjRhNDI4LjggNDI4LjggMCAwIDAgMTQ2LjQ5NiAzMy40MDhWOTIuMTZ6bS0xNDIuMTQ0IDMzLjA4OGE0MTQuODQ4IDQxNC44NDggMCAwIDAtODUuNzYgNDkuNDcyYzEzLjA1NiA4Ljk2IDI2LjYyNCAxNy4yOCA0MC40NDggMjUuNDcyYTM3NS4xNjggMzc1LjE2OCAwIDAgMSA0NS4zMTItNzQuODh6TTIyNC45NiAyMDQuOTkyQTQxOS42NDggNDE5LjY0OCAwIDAgMCA5Mi4wMzIgNDg5LjQwOGgxNDQuODk2YzIuNjg4LTkxLjUyIDE5LjUyLTE3Ni42NCA0Ni40LTI0Ny40ODhhNDc4LjQ2NCA0NzguNDY0IDAgMCAxLTU4LjM2OC0zNi45Mjh6TTkyLjAzMiA1MzUuMjMyYTQyMC44IDQyMC44IDAgMCAwIDEyMi42MjQgMjc0LjMwNGwxMC4zMDQgMTAuMjRjMTguNDMyLTE0LjAxNiAzNy44ODgtMjYuNDk2IDU4LjM2OC0zNy4zNzYtMjYuODgtNzEuMTA0LTQzLjcxMi0xNTUuNzc2LTQ2LjQtMjQ3LjIzMkg5Mi4wMzJ6bTE2OS4yOCAzMTQuNDMyYzI2LjU2IDE5Ljg0IDU1LjI5NiAzNi40MTYgODUuNzYgNDkuNDA4YTM2MC41MTIgMzYwLjUxMiAwIDAgMS0zMy42NjQtNTEuNTg0IDM1MS42MTYgMzUxLjYxNiAwIDAgMS0xMS42NDgtMjIuNzg0IDQxNi42NCA0MTYuNjQgMCAwIDAtNDAuNDQ4IDI0Ljk2em0yNzMuNDcyIDgyLjQ5NmEzNzEuODQgMzcxLjg0IDAgMCAwIDQ2LjY1Ni01LjQ0YzMzLjQwOC0yMC4zNTIgNjQtNTUuNjE2IDg4Ljk2LTEwMS4xODQgMy41Mi02Ljc4NCA3LjY4LTEzLjgyNCAxMC41Ni0yMC45MjhhMTMzLjg4OCAxMzMuODg4IDAgMCAwLTE3LjAyNC02LjQ2NCA0MDUuMjQ4IDQwNS4yNDggMCAwIDAtMTI5LjE1Mi0yNi42MjR2MTYwLjY0em0xNDIuMTQ0LTMzLjA4OGE0MTYuMzIgNDE2LjMyIDAgMCAwIDg1Ljc2LTQ5LjQwOCAzOTAuNjU2IDM5MC42NTYgMCAwIDAtNDAuMTkyLTI0Ljk2bC0xMS45MDQgMjIuNzg0YTQxNS4zNiA0MTUuMzYgMCAwIDEtMzMuNiA1MS41ODR6bTEyMS43OTItNzkuMjk2bDEwLjYyNC0xMC4yNGE0MjAuOCA0MjAuOCAwIDAgMCAxMjIuNjI0LTI3NC4zNjhINzg3LjA3MmMtMi42ODggOTEuNTItMTkuNTIgMTc2LjEyOC00Ni42NTYgMjQ3LjIzMiAyMC40OCAxMC43NTIgNDAgMjMuMjMyIDU4LjMwNCAzNy4zNzZ6bS05OS44NC01NTguMDhhMjAzLjY0OCAyMDMuNjQ4IDAgMCAxLTE4Ljk0NCA3LjM2IDQ2MC42MDggNDYwLjYwOCAwIDAgMS0xNDUuMTUyIDI5LjgyNHYxOTAuNDY0aDIwNi4yMDhjLTIuNDMyLTg0LjM1Mi0xNy40MDgtMTYyLjU2LTQyLjA0OC0yMjcuNjQ4em0tMjA5LjY2NCAzNy4xMmE0NTYuMDY0IDQ1Ni4wNjQgMCAwIDEtMTQ0Ljg5Ni0yOS43NiAxODcuOTA0IDE4Ny45MDQgMCAwIDEtMTkuNTItNy4zNmMtMjQuMzg0IDY1LjA4OC0zOS42MTYgMTQzLjI5Ni00Mi4wNDggMjI3LjY0OGgyMDYuNDY0VjI5OC44OHptMCA0MjYuNjI0VjUzNS4xNjhIMjgyLjc1MmMyLjQzMiA4NC4xNiAxNy42NjQgMTYxLjk4NCA0Mi4wNDggMjI3LjM5MiA2LjUyOC0yLjQzMiAxMy4wNTYtNS4xMiAxOS41Mi03LjI5NmE0NjMuNjggNDYzLjY4IDAgMCAxIDE0NC44OTYtMjkuODI0em00NS41NjggMGE0NjUuMzQ0IDQ2NS4zNDQgMCAwIDEgMTQ0Ljg5NiAyOS44MjRjNi40NjQgMi4xNzYgMTIuNzM2IDQuODY0IDE5LjIgNy4yOTYgMjQuNzA0LTY1LjQwOCAzOS42OC0xNDMuMjMyIDQyLjExMi0yMjcuMzkySDUzNC43ODRWNzI1LjQ0eiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
            size: 20,
          },
          {
            id: 'node1',
            name: '节点1',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTUxMiAxNS4wNGE0OTcuOTIgNDk3LjkyIDAgMCAxIDQ5Ny4wMjQgNDk3LjA4OCA0OTYuODMyIDQ5Ni44MzIgMCAwIDEtMTQ1LjcyOCAzNTEuNjhBNDk0LjQgNDk0LjQgMCAwIDEgNTEyIDEwMDguOTZhNDkzLjgyNCA0OTMuODI0IDAgMCAxLTM1MS4zNi0xNDUuMTUyIDQ5Ni44MzIgNDk2LjgzMiAwIDAgMS0xNDUuNTM2LTM1MS42OEE0OTcuOTIgNDk3LjkyIDAgMCAxIDUxMiAxNS4wNHptLTIyLjc4NCA5MTcuMTJWNzcxLjUyYTQwNS4xMiA0MDUuMTIgMCAwIDAtMTI5LjE1MiAyNi42MjQgMTMxLjY1MiAxMzEuNjUyIDAgMCAwLTE3LjA4OCA2LjQ2NGMzLjUyIDcuMDQgNi43ODQgMTQuMDggMTAuNTYgMjAuOTI4IDI1LjUzNiA0NS41NjggNTUuMzYgODAuODk2IDg4Ljk2IDEwMS4xODQgMTUuNDg4IDIuODE2IDMxLjA0IDQuNjA4IDQ2LjcyIDUuNDR6bTMyMC4xMjgtNzE3LjEyYTEyOC43NjggMTI4Ljc2OCAwIDAgMC0xMC42MjQtMTAuMDQ4IDQ0MS4yMTYgNDQxLjIxNiAwIDAgMS01OC4yNCAzNi45MjhjMjcuMDcyIDcwLjc4NCA0My45MDQgMTU2LjAzMiA0Ni41OTIgMjQ3LjQyNGgxNDQuODk2QTQxOS42NDggNDE5LjY0OCAwIDAgMCA4MDkuMzQ0IDIxNS4wNHptLTQ2LjcyLTQwLjM4NGE0MTUuMzYgNDE1LjM2IDAgMCAwLTg1LjY5Ni00OS40NzJjMTIuNDE2IDE2LjM4NCAyMy42OCAzMy42IDMzLjY2NCA1MS41ODQgMy44NCA3LjA0IDcuODcyIDE1LjIzMiAxMS45MDQgMjMuMzYgMTMuNTY4LTguMTI4IDI3LjEzNi0xNi41NzYgNDAuMTI4LTI1LjUzNnpNNTgxLjQ0IDk3LjIxNmE1MzIuMzUyIDUzMi4zNTIgMCAwIDAtNDYuNjU2LTUuMTJ2MTYxLjIxNmE0MjguOTkyIDQyOC45OTIgMCAwIDAgMTQ2LjE3Ni0zMy40MDhjLTIuOTQ0LTcuMjk2LTcuMDQtMTQuMzM2LTEwLjQ5Ni0yMC44NjQtMjQuOTYtNDYuMTQ0LTU1LjY4LTgwLjg5Ni04OS4wMjQtMTAxLjc2em0tOTIuMjI0LTUuMTJhNTM0LjAxNiA1MzQuMDE2IDAgMCAwLTQ2LjcyIDUuMTJjLTMzLjYgMjAuOTI4LTYzLjQyNCA1NS42OC04OC45NiAxMDEuODI0LTMuNzc2IDYuNTI4LTcuMDQgMTMuNTY4LTEwLjgxNiAyMC44NjRhNDI4LjggNDI4LjggMCAwIDAgMTQ2LjQ5NiAzMy40MDhWOTIuMTZ6bS0xNDIuMTQ0IDMzLjA4OGE0MTQuODQ4IDQxNC44NDggMCAwIDAtODUuNzYgNDkuNDcyYzEzLjA1NiA4Ljk2IDI2LjYyNCAxNy4yOCA0MC40NDggMjUuNDcyYTM3NS4xNjggMzc1LjE2OCAwIDAgMSA0NS4zMTItNzQuODh6TTIyNC45NiAyMDQuOTkyQTQxOS42NDggNDE5LjY0OCAwIDAgMCA5Mi4wMzIgNDg5LjQwOGgxNDQuODk2YzIuNjg4LTkxLjUyIDE5LjUyLTE3Ni42NCA0Ni40LTI0Ny40ODhhNDc4LjQ2NCA0NzguNDY0IDAgMCAxLTU4LjM2OC0zNi45Mjh6TTkyLjAzMiA1MzUuMjMyYTQyMC44IDQyMC44IDAgMCAwIDEyMi42MjQgMjc0LjMwNGwxMC4zMDQgMTAuMjRjMTguNDMyLTE0LjAxNiAzNy44ODgtMjYuNDk2IDU4LjM2OC0zNy4zNzYtMjYuODgtNzEuMTA0LTQzLjcxMi0xNTUuNzc2LTQ2LjQtMjQ3LjIzMkg5Mi4wMzJ6bTE2OS4yOCAzMTQuNDMyYzI2LjU2IDE5Ljg0IDU1LjI5NiAzNi40MTYgODUuNzYgNDkuNDA4YTM2MC41MTIgMzYwLjUxMiAwIDAgMS0zMy42NjQtNTEuNTg0IDM1MS42MTYgMzUxLjYxNiAwIDAgMS0xMS42NDgtMjIuNzg0IDQxNi42NCA0MTYuNjQgMCAwIDAtNDAuNDQ4IDI0Ljk2em0yNzMuNDcyIDgyLjQ5NmEzNzEuODQgMzcxLjg0IDAgMCAwIDQ2LjY1Ni01LjQ0YzMzLjQwOC0yMC4zNTIgNjQtNTUuNjE2IDg4Ljk2LTEwMS4xODQgMy41Mi02Ljc4NCA3LjY4LTEzLjgyNCAxMC41Ni0yMC45MjhhMTMzLjg4OCAxMzMuODg4IDAgMCAwLTE3LjAyNC02LjQ2NCA0MDUuMjQ4IDQwNS4yNDggMCAwIDAtMTI5LjE1Mi0yNi42MjR2MTYwLjY0em0xNDIuMTQ0LTMzLjA4OGE0MTYuMzIgNDE2LjMyIDAgMCAwIDg1Ljc2LTQ5LjQwOCAzOTAuNjU2IDM5MC42NTYgMCAwIDAtNDAuMTkyLTI0Ljk2bC0xMS45MDQgMjIuNzg0YTQxNS4zNiA0MTUuMzYgMCAwIDEtMzMuNiA1MS41ODR6bTEyMS43OTItNzkuMjk2bDEwLjYyNC0xMC4yNGE0MjAuOCA0MjAuOCAwIDAgMCAxMjIuNjI0LTI3NC4zNjhINzg3LjA3MmMtMi42ODggOTEuNTItMTkuNTIgMTc2LjEyOC00Ni42NTYgMjQ3LjIzMiAyMC40OCAxMC43NTIgNDAgMjMuMjMyIDU4LjMwNCAzNy4zNzZ6bS05OS44NC01NTguMDhhMjAzLjY0OCAyMDMuNjQ4IDAgMCAxLTE4Ljk0NCA3LjM2IDQ2MC42MDggNDYwLjYwOCAwIDAgMS0xNDUuMTUyIDI5LjgyNHYxOTAuNDY0aDIwNi4yMDhjLTIuNDMyLTg0LjM1Mi0xNy40MDgtMTYyLjU2LTQyLjA0OC0yMjcuNjQ4em0tMjA5LjY2NCAzNy4xMmE0NTYuMDY0IDQ1Ni4wNjQgMCAwIDEtMTQ0Ljg5Ni0yOS43NiAxODcuOTA0IDE4Ny45MDQgMCAwIDEtMTkuNTItNy4zNmMtMjQuMzg0IDY1LjA4OC0zOS42MTYgMTQzLjI5Ni00Mi4wNDggMjI3LjY0OGgyMDYuNDY0VjI5OC44OHptMCA0MjYuNjI0VjUzNS4xNjhIMjgyLjc1MmMyLjQzMiA4NC4xNiAxNy42NjQgMTYxLjk4NCA0Mi4wNDggMjI3LjM5MiA2LjUyOC0yLjQzMiAxMy4wNTYtNS4xMiAxOS41Mi03LjI5NmE0NjMuNjggNDYzLjY4IDAgMCAxIDE0NC44OTYtMjkuODI0em00NS41NjggMGE0NjUuMzQ0IDQ2NS4zNDQgMCAwIDEgMTQ0Ljg5NiAyOS44MjRjNi40NjQgMi4xNzYgMTIuNzM2IDQuODY0IDE5LjIgNy4yOTYgMjQuNzA0LTY1LjQwOCAzOS42OC0xNDMuMjMyIDQyLjExMi0yMjcuMzkySDUzNC43ODRWNzI1LjQ0eiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
          },
          {
            id: 'node2',
            name: '节点2',
            size: 30,
            stroke: '#FF5656',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwOTcgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjE0LjI1OCIgaGVpZ2h0PSIyMDAiPjxwYXRoIGQ9Ik00MzguODU3IDk1MC44NTdIMTEzLjE1MmE0MS4xOCA0MS4xOCAwIDAgMS00MC4wMS00Mi4yMDNWMTE1LjM0NmMwLTIzLjU1MiAxOC4xNC00Mi4yMDMgNDAuMDEtNDIuMjAzaDY1MS40MWMyMS44NyAwIDQwLjAxIDE4LjY1MSA0MC4wMSA0Mi4yMDN2MjA4LjUzYTM2LjU3MSAzNi41NzEgMCAxIDAgNzMuMTQyIDB2LTIwOC41M0M4NzcuNzE0IDUxLjg1OCA4MjcuMjQ2IDAgNzY0LjU2MiAwSDExMy4yMjVDNTAuNDcgMCAwIDUxLjg1OCAwIDExNS4zNDZ2NzkzLjMwOEMwIDk3Mi4xNDIgNTAuNDY5IDEwMjQgMTEzLjE1MiAxMDI0aDMyNS43MDVhMzYuNTcxIDM2LjU3MSAwIDEgMCAwLTczLjE0M3ptMzI5LjE0My01MTJBMjkyLjU3MSAyOTIuNTcxIDAgMSAwIDc2OCAxMDI0YTI5Mi41NzEgMjkyLjU3MSAwIDAgMCAwLTU4NS4xNDN6bTAgNTEyQTIxOS40MjkgMjE5LjQyOSAwIDEgMSA3NjggNTEyYTIxOS40MjkgMjE5LjQyOSAwIDAgMSAwIDQzOC44NTd6bTEwOS4xMy0yMzcuNzE0aC05MC44NDRWNjQwYTM2LjU3MSAzNi41NzEgMCAxIDAtNzMuMTQzIDB2MTA5LjcxNGEzNi41NzEgMzYuNTcxIDAgMCAwIDM2LjU3MSAzNi41NzJIODc3LjEzYTM2LjU3MSAzNi41NzEgMCAxIDAgMC03My4xNDN6TTY1OC4yODUgMjkyLjU3QTM2LjU3MSAzNi41NzEgMCAwIDAgNjIxLjcxNCAyNTZIMjU2YTM2LjU3MSAzNi41NzEgMCAwIDAgMCA3My4xNDNoMzY1LjcxNGEzNi41NzEgMzYuNTcxIDAgMCAwIDM2LjU3Mi0zNi41NzJ6TTI1NiA1NDguNTcxYTM2LjU3MSAzNi41NzEgMCAwIDAgMCA3My4xNDNoOTEuNzk0YTM2LjU3MSAzNi41NzEgMCAwIDAgMC03My4xNDNIMjU2eiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
          },
          {
            id: 'node3',
            name: '节点3',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTk2MCAxMjMuNjg1Qzg3Mi42NjcgNDkuODgzIDcwNC43MzEgMCA1MTIgMCAzMTkuMTk1IDAgMTUxLjMzMyA0OS44ODMgNjQgMTIzLjY4NSAyMy4xODYgMTU4LjIwOCAwIDE5Ny44NSAwIDIzOS45ODJ2MzY2LjAwN2wuMDczIDEuOTc0SDB2MTc1Ljk4MkMwIDkxNi40OCAyMjkuMjMgMTAyNCA1MTIgMTAyNHM1MTItMTA3LjUyIDUxMi0yNDAuMDU1VjYwOC4wMzdoLS4wNzNsLjA3My01LjI2N1YyMzkuOTFjMC00Mi4xMy0yMy4xODYtODEuNzc0LTY0LTExNi4yOTh6TTY0IDM1Ni4yNzljODcuMzMzIDczLjk0NyAyNTUuMjY5IDEyMy44MyA0NDggMTIzLjgzIDE5Mi44MDUgMCAzNjAuNjY3LTQ5Ljg4MyA0NDgtMTIzLjY4NHY3OS4yMTRhNTA4LjI3IDUwOC4yNyAwIDAgMS01OC44MDcgMzIuMTgzYy0xMDQuOTYgNDkuMTUyLTI0My4yIDc2LjIxNS0zODkuMTkzIDc2LjIxNXMtMjg0LjIzMy0yNy4wNjMtMzg5LjE5My03Ni4zNjJBNTA4LjI3IDUwOC4yNyAwIDAgMSA2NCA0MzUuNDkzdi03OS4yMTR6bTAgMTgxLjM5NGM4Ny4zMzMgNzMuODAxIDI1NS4yNjkgMTIzLjY4NSA0NDggMTIzLjY4NSAxOTIuODA1IDAgMzYwLjY2Ny00OS44ODQgNDQ4LTEyMy42ODV2NzkuMjE0YTUyMy43NzYgNTIzLjc3NiAwIDAgMS01OC44MDcgMzIuMTgzQzc5Ni4yMzMgNjk4LjI5NSA2NTcuOTIgNzI1LjM1OCA1MTIgNzI1LjM1OHMtMjg0LjIzMy0yNy4wNjMtMzg5LjE5My03Ni4yODhBNTA4LjI3IDUwOC4yNyAwIDAgMSA2NCA2MTYuODg3VjUzNy42em04MzcuMTkzIDI5Mi43MThDNzk2LjIzMyA4NzkuNjE2IDY1Ny45MiA5MDYuNjc5IDUxMiA5MDYuNjc5cy0yODQuMjMzLTI3LjA2My0zODkuMTkzLTc2LjI4OGE1MzMuNTA0IDUzMy41MDQgMCAwIDEtNTYuMzkzLTMwLjY0N0E1My45OCA1My45OCAwIDAgMSA2NCA3ODQuMDkxdi02NS4wOTdDMTUxLjMzMyA3OTIuODcgMzE5LjI2OSA4NDIuNjggNTEyIDg0Mi42OGMxOTIuODA1IDAgMzYwLjY2Ny00OS45NTcgNDQ4LTEyMy42ODV2NjUuMDI0YzAgNS4xMi0uNzMxIDEwLjM4Ny0yLjQxNCAxNS42NTNhNTE1Ljk1IDUxNS45NSAwIDAgMS01Ni4zMiAzMC42NDd6IiBmaWxsPSIjNjM2NTZFIi8+PC9zdmc+',
            disabled: true,
          },
          {
            id: 'node4',
            name: '节点4',
            stroke: '#FFB848',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTk2MCAxMjMuNjg1Qzg3Mi42NjcgNDkuODgzIDcwNC43MzEgMCA1MTIgMCAzMTkuMTk1IDAgMTUxLjMzMyA0OS44ODMgNjQgMTIzLjY4NSAyMy4xODYgMTU4LjIwOCAwIDE5Ny44NSAwIDIzOS45ODJ2MzY2LjAwN2wuMDczIDEuOTc0SDB2MTc1Ljk4MkMwIDkxNi40OCAyMjkuMjMgMTAyNCA1MTIgMTAyNHM1MTItMTA3LjUyIDUxMi0yNDAuMDU1VjYwOC4wMzdoLS4wNzNsLjA3My01LjI2N1YyMzkuOTFjMC00Mi4xMy0yMy4xODYtODEuNzc0LTY0LTExNi4yOTh6TTY0IDM1Ni4yNzljODcuMzMzIDczLjk0NyAyNTUuMjY5IDEyMy44MyA0NDggMTIzLjgzIDE5Mi44MDUgMCAzNjAuNjY3LTQ5Ljg4MyA0NDgtMTIzLjY4NHY3OS4yMTRhNTA4LjI3IDUwOC4yNyAwIDAgMS01OC44MDcgMzIuMTgzYy0xMDQuOTYgNDkuMTUyLTI0My4yIDc2LjIxNS0zODkuMTkzIDc2LjIxNXMtMjg0LjIzMy0yNy4wNjMtMzg5LjE5My03Ni4zNjJBNTA4LjI3IDUwOC4yNyAwIDAgMSA2NCA0MzUuNDkzdi03OS4yMTR6bTAgMTgxLjM5NGM4Ny4zMzMgNzMuODAxIDI1NS4yNjkgMTIzLjY4NSA0NDggMTIzLjY4NSAxOTIuODA1IDAgMzYwLjY2Ny00OS44ODQgNDQ4LTEyMy42ODV2NzkuMjE0YTUyMy43NzYgNTIzLjc3NiAwIDAgMS01OC44MDcgMzIuMTgzQzc5Ni4yMzMgNjk4LjI5NSA2NTcuOTIgNzI1LjM1OCA1MTIgNzI1LjM1OHMtMjg0LjIzMy0yNy4wNjMtMzg5LjE5My03Ni4yODhBNTA4LjI3IDUwOC4yNyAwIDAgMSA2NCA2MTYuODg3VjUzNy42em04MzcuMTkzIDI5Mi43MThDNzk2LjIzMyA4NzkuNjE2IDY1Ny45MiA5MDYuNjc5IDUxMiA5MDYuNjc5cy0yODQuMjMzLTI3LjA2My0zODkuMTkzLTc2LjI4OGE1MzMuNTA0IDUzMy41MDQgMCAwIDEtNTYuMzkzLTMwLjY0N0E1My45OCA1My45OCAwIDAgMSA2NCA3ODQuMDkxdi02NS4wOTdDMTUxLjMzMyA3OTIuODcgMzE5LjI2OSA4NDIuNjggNTEyIDg0Mi42OGMxOTIuODA1IDAgMzYwLjY2Ny00OS45NTcgNDQ4LTEyMy42ODV2NjUuMDI0YzAgNS4xMi0uNzMxIDEwLjM4Ny0yLjQxNCAxNS42NTNhNTE1Ljk1IDUxNS45NSAwIDAgMS01Ni4zMiAzMC42NDd6IiBmaWxsPSIjNjM2NTZFIi8+PC9zdmc+',
          },
          {
            id: 'node5',
            name: '节点5',
            lineDash: [4, 4],
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTk2MCAxMjMuNjg1Qzg3Mi42NjcgNDkuODgzIDcwNC43MzEgMCA1MTIgMCAzMTkuMTk1IDAgMTUxLjMzMyA0OS44ODMgNjQgMTIzLjY4NSAyMy4xODYgMTU4LjIwOCAwIDE5Ny44NSAwIDIzOS45ODJ2MzY2LjAwN2wuMDczIDEuOTc0SDB2MTc1Ljk4MkMwIDkxNi40OCAyMjkuMjMgMTAyNCA1MTIgMTAyNHM1MTItMTA3LjUyIDUxMi0yNDAuMDU1VjYwOC4wMzdoLS4wNzNsLjA3My01LjI2N1YyMzkuOTFjMC00Mi4xMy0yMy4xODYtODEuNzc0LTY0LTExNi4yOTh6TTY0IDM1Ni4yNzljODcuMzMzIDczLjk0NyAyNTUuMjY5IDEyMy44MyA0NDggMTIzLjgzIDE5Mi44MDUgMCAzNjAuNjY3LTQ5Ljg4MyA0NDgtMTIzLjY4NHY3OS4yMTRhNTA4LjI3IDUwOC4yNyAwIDAgMS01OC44MDcgMzIuMTgzYy0xMDQuOTYgNDkuMTUyLTI0My4yIDc2LjIxNS0zODkuMTkzIDc2LjIxNXMtMjg0LjIzMy0yNy4wNjMtMzg5LjE5My03Ni4zNjJBNTA4LjI3IDUwOC4yNyAwIDAgMSA2NCA0MzUuNDkzdi03OS4yMTR6bTAgMTgxLjM5NGM4Ny4zMzMgNzMuODAxIDI1NS4yNjkgMTIzLjY4NSA0NDggMTIzLjY4NSAxOTIuODA1IDAgMzYwLjY2Ny00OS44ODQgNDQ4LTEyMy42ODV2NzkuMjE0YTUyMy43NzYgNTIzLjc3NiAwIDAgMS01OC44MDcgMzIuMTgzQzc5Ni4yMzMgNjk4LjI5NSA2NTcuOTIgNzI1LjM1OCA1MTIgNzI1LjM1OHMtMjg0LjIzMy0yNy4wNjMtMzg5LjE5My03Ni4yODhBNTA4LjI3IDUwOC4yNyAwIDAgMSA2NCA2MTYuODg3VjUzNy42em04MzcuMTkzIDI5Mi43MThDNzk2LjIzMyA4NzkuNjE2IDY1Ny45MiA5MDYuNjc5IDUxMiA5MDYuNjc5cy0yODQuMjMzLTI3LjA2My0zODkuMTkzLTc2LjI4OGE1MzMuNTA0IDUzMy41MDQgMCAwIDEtNTYuMzkzLTMwLjY0N0E1My45OCA1My45OCAwIDAgMSA2NCA3ODQuMDkxdi02NS4wOTdDMTUxLjMzMyA3OTIuODcgMzE5LjI2OSA4NDIuNjggNTEyIDg0Mi42OGMxOTIuODA1IDAgMzYwLjY2Ny00OS45NTcgNDQ4LTEyMy42ODV2NjUuMDI0YzAgNS4xMi0uNzMxIDEwLjM4Ny0yLjQxNCAxNS42NTNhNTE1Ljk1IDUxNS45NSAwIDAgMS01Ni4zMiAzMC42NDd6IiBmaWxsPSIjNjM2NTZFIi8+PC9zdmc+',
            menu: [
              { id: 'down', name: '接口下钻', icon: 'icon-xiazuan' },
              { id: 'topo', name: '资源拓扑', icon: 'icon-ziyuan' },
              { id: 'application', name: '查看第三方应用', icon: '' },
            ],
          },
        ],
        edges: [
          {
            source: 'node0', // 起始点 id
            target: 'node1', // 目标点 id
            lineWidth: 5,
            label: '99.5ms',
          },
          {
            source: 'node1', // 起始点 id
            target: 'node2', // 目标点 id
            label: '99.5ms',
          },
          {
            source: 'node2', // 起始点 id
            target: 'node3', // 目标点 id
            label: '99.5ms',
          },
          {
            source: 'node1', // 起始点 id
            target: 'node4', // 目标点 id
            label: '99.5ms',
          },
          {
            source: 'node1', // 起始点 id
            target: 'node5', // 目标点 id
            label: '99.5ms',
          },
          {
            source: 'node4', // 起始点 id
            target: 'node5', // 目标点 id
            label: '99.5ms',
          },
        ],
      };
    }, 300);
  }

  /**
   * @description: 获取图表数据
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {
    this.beforeGetPanelData(start_time, end_time);
    this.handleLoadingChange(true);
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        app_name: this.appName,
        service_name: this.serviceName,
        data_type: this.dataType,
      };
      this.getAlarmBarData = async setData => {
        const data = await dataTypeBarQuery({
          ...params,
        }).catch(() => ({ series: [] }));
        setData(alarmBarChartDataTransform(this.dataType, data.series));
      };
    } catch (e) {
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  /**
   * @description 伸缩侧栏
   * @param id
   */
  handleExpand(id: string) {
    const index = this.expanded.findIndex(key => key === id);
    if (index >= 0) {
      this.expanded.splice(index, 1);
    } else {
      this.expanded.push(id);
    }
  }

  handleFilterChange(id) {
    this.curFilter = id;
  }

  handleShowTypeChange(item) {
    this.showType = item.id;
  }

  handleDataTypeChange() {
    this.getPanelData();
  }

  dataZoom(startTime: string, endTime: string) {
    if (this.enableSelectionRestoreAll) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.getPanelData(startTime, endTime);
    }
  }

  render() {
    return (
      <div class='apm-relation-graph'>
        <div class='apm-relation-graph-header'>
          <div class='header-select-wrap'>
            <div class='data-type-select'>
              {this.showTypes.map(item => (
                <div
                  key={item.id}
                  class={['data-type-item', { active: this.showType === item.id }]}
                  onClick={() => this.handleShowTypeChange(item)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
            <bk-select
              class='type-selector'
              v-model={this.dataType}
              clearable={false}
              onChange={this.handleDataTypeChange}
            >
              {DATA_TYPE_LIST.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </div>
          <div class='header-alarm-wrap'>
            <BarAlarmChart
              activeItemHeight={24}
              dataType={this.dataType}
              getData={this.getAlarmBarData}
              itemHeight={16}
              onDataZoom={this.dataZoom as any}
            />
          </div>
          <div class='header-search-wrap'>
            <StatusTab
              class='ml-24'
              needAll={false}
              needExpand={true}
              statusList={this.filterList}
              value={this.curFilter}
              onChange={this.handleFilterChange}
            />
            <bk-checkbox class='ml-24'>无数据节点</bk-checkbox>
            <bk-input
              class='ml-24'
              v-model={this.searchValue}
              behavior='simplicity'
              placeholder={'搜索服务、接口'}
              right-icon='bk-icon icon-search'
              clearable
            />
          </div>
          <div class='header-tool-wrap'>
            <div class='tool-btns'>
              {this.expandList.map(item => (
                <div
                  key={item.id}
                  class={['tool-btn', { active: this.expanded.includes(item.id) }]}
                  onClick={() => this.handleExpand(item.id)}
                >
                  <span class={`icon-monitor ${item.icon}`} />
                </div>
              ))}
            </div>
          </div>
        </div>
        {this.showType === 'topo' ? (
          <ApmRelationGraphContent
            ref='content-wrap'
            expanded={this.expanded}
          >
            <ApmRelationTopo
              activeNode={['node1', 'node2']}
              data={this.graphData}
              scene='request'
            />
            <div
              class='side-wrap'
              slot='side'
            >
              <div
                style={{
                  minWidth: `${sideTopoMinWidth}px`,
                  display: this.expanded.includes('topo') ? 'block' : 'none',
                }}
                class='source-topo'
              >
                <div class='header-wrap'>
                  <div class='title'>资源拓扑</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('topo')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap'>
                  <ResourceTopo />
                </div>
              </div>

              <div
                style={{
                  minWidth: `${sideOverviewMinWidth}px`,
                  display: this.expanded.includes('overview') ? 'block' : 'none',
                }}
                class={['service-overview', { 'no-border': !this.expanded.includes('topo') }]}
              >
                <div class='header-wrap'>
                  <div class='title'>服务概览</div>
                  <div
                    class='expand-btn'
                    onClick={() => this.handleExpand('overview')}
                  >
                    <span class='icon-monitor icon-zhankai' />
                  </div>
                </div>
                <div class='content-wrap'>
                  <ServiceOverview data={{}} />
                </div>
              </div>
            </div>
          </ApmRelationGraphContent>
        ) : (
          <div class='apm-relation-graph-table-wrap'>
            <div class='table-wrap'>
              <CommonTable
                checkable={false}
                columns={this.tableColumns}
                data={this.tableData}
                pagination={this.pagination}
                paginationType={'simple'}
              />
            </div>
          </div>
        )}
      </div>
    );
  }
}
