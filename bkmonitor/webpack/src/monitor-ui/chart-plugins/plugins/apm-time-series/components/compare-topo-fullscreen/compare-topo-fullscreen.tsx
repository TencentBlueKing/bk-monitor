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

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import { EDataType, EOptionKind } from '../details-side';
import CompareTopoGraph from './compare-topo-graph';

import './compare-topo-fullscreen.scss';
type CompareTopoFullscreenEvent = {
  onShowChange: (val?: boolean) => void;
};

type CompareTopoFullscreenProps = {
  /** 调用类型 */
  callType: EOptionKind;
  /** 对比时间，时间戳 */
  compareTime: number;
  /** 数据类型 */
  dataType: EDataType;
  isService: boolean;
  /** 参照时间 */
  referTime: number;
  secondSelectList: { id: string; name: string }[];
  show: boolean;
};

@Component
export default class CompareTopoFullscreen extends tsc<CompareTopoFullscreenProps, CompareTopoFullscreenEvent> {
  @Prop({ default: false }) readonly show!: boolean;
  @Prop({ default: true }) readonly isServer!: boolean;
  @Prop({ default: 0 }) readonly compareTime!: number;
  @Prop({ default: 0 }) readonly referTime!: number;
  @Prop({ default: 'caller' }) callType!: EOptionKind;
  @Prop({ default: 'request_count' }) dataType!: EDataType;
  @Prop({ default: [] }) secondSelectList: CompareTopoFullscreenProps['secondSelectList'];

  @Ref('compareTopoGraph') compareTopoGraphRef!: CompareTopoGraph;

  filterTypeList = Object.freeze([
    { label: '请求数', value: EDataType.requestCount },
    { label: '错误数', value: EDataType.errorCount },
    { label: '响应耗时', value: EDataType.avgDuration },
  ]);
  countList = Object.freeze([]);

  filterParam = {
    type: 'request',
    count: 200,
    call: 'main',
  };

  graphData = {};
  /** 当前激活的节点 */
  activeNode = 'node1';
  tableData = [
    {
      a: 'Apdex',
      b: 15,
      c: 15,
      d: '+45%',
    },
    {
      a: '请求数 (主调)',
      b: 20,
      c: 10,
      d: '+35%',
    },
    {
      a: '请求数 (被调)',
      b: 5,
      c: 2,
      d: '-5%',
    },
  ];

  get showSecondSelect() {
    return this.filterParam.type === EDataType.errorCount || this.filterParam.type === EDataType.avgDuration;
  }

  get formatTime() {
    return {
      refer: dayjs(this.referTime).format('YYYY-MM-DD HH:mm'),
      compare: dayjs(this.compareTime).format('YYYY-MM-DD HH:mm'),
    };
  }

  @Watch('show')
  watchShowChange(val) {
    if (val) {
      this.initParams();
      this.getGraphData();
    }
  }

  initParams() {
    this.filterParam = {
      type: this.dataType || EDataType.requestCount,
      count: 200,
      call: this.callType || EOptionKind.caller,
    };
  }

  getGraphData() {
    setTimeout(() => {
      this.graphData = {
        nodes: [
          {
            id: 'node0',
            name: '节点0',
            topoType: 'icon',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTUxMiAxNS4wNGE0OTcuOTIgNDk3LjkyIDAgMCAxIDQ5Ny4wMjQgNDk3LjA4OCA0OTYuODMyIDQ5Ni44MzIgMCAwIDEtMTQ1LjcyOCAzNTEuNjhBNDk0LjQgNDk0LjQgMCAwIDEgNTEyIDEwMDguOTZhNDkzLjgyNCA0OTMuODI0IDAgMCAxLTM1MS4zNi0xNDUuMTUyIDQ5Ni44MzIgNDk2LjgzMiAwIDAgMS0xNDUuNTM2LTM1MS42OEE0OTcuOTIgNDk3LjkyIDAgMCAxIDUxMiAxNS4wNHptLTIyLjc4NCA5MTcuMTJWNzcxLjUyYTQwNS4xMiA0MDUuMTIgMCAwIDAtMTI5LjE1MiAyNi42MjQgMTMxLjY1MiAxMzEuNjUyIDAgMCAwLTE3LjA4OCA2LjQ2NGMzLjUyIDcuMDQgNi43ODQgMTQuMDggMTAuNTYgMjAuOTI4IDI1LjUzNiA0NS41NjggNTUuMzYgODAuODk2IDg4Ljk2IDEwMS4xODQgMTUuNDg4IDIuODE2IDMxLjA0IDQuNjA4IDQ2LjcyIDUuNDR6bTMyMC4xMjgtNzE3LjEyYTEyOC43NjggMTI4Ljc2OCAwIDAgMC0xMC42MjQtMTAuMDQ4IDQ0MS4yMTYgNDQxLjIxNiAwIDAgMS01OC4yNCAzNi45MjhjMjcuMDcyIDcwLjc4NCA0My45MDQgMTU2LjAzMiA0Ni41OTIgMjQ3LjQyNGgxNDQuODk2QTQxOS42NDggNDE5LjY0OCAwIDAgMCA4MDkuMzQ0IDIxNS4wNHptLTQ2LjcyLTQwLjM4NGE0MTUuMzYgNDE1LjM2IDAgMCAwLTg1LjY5Ni00OS40NzJjMTIuNDE2IDE2LjM4NCAyMy42OCAzMy42IDMzLjY2NCA1MS41ODQgMy44NCA3LjA0IDcuODcyIDE1LjIzMiAxMS45MDQgMjMuMzYgMTMuNTY4LTguMTI4IDI3LjEzNi0xNi41NzYgNDAuMTI4LTI1LjUzNnpNNTgxLjQ0IDk3LjIxNmE1MzIuMzUyIDUzMi4zNTIgMCAwIDAtNDYuNjU2LTUuMTJ2MTYxLjIxNmE0MjguOTkyIDQyOC45OTIgMCAwIDAgMTQ2LjE3Ni0zMy40MDhjLTIuOTQ0LTcuMjk2LTcuMDQtMTQuMzM2LTEwLjQ5Ni0yMC44NjQtMjQuOTYtNDYuMTQ0LTU1LjY4LTgwLjg5Ni04OS4wMjQtMTAxLjc2em0tOTIuMjI0LTUuMTJhNTM0LjAxNiA1MzQuMDE2IDAgMCAwLTQ2LjcyIDUuMTJjLTMzLjYgMjAuOTI4LTYzLjQyNCA1NS42OC04OC45NiAxMDEuODI0LTMuNzc2IDYuNTI4LTcuMDQgMTMuNTY4LTEwLjgxNiAyMC44NjRhNDI4LjggNDI4LjggMCAwIDAgMTQ2LjQ5NiAzMy40MDhWOTIuMTZ6bS0xNDIuMTQ0IDMzLjA4OGE0MTQuODQ4IDQxNC44NDggMCAwIDAtODUuNzYgNDkuNDcyYzEzLjA1NiA4Ljk2IDI2LjYyNCAxNy4yOCA0MC40NDggMjUuNDcyYTM3NS4xNjggMzc1LjE2OCAwIDAgMSA0NS4zMTItNzQuODh6TTIyNC45NiAyMDQuOTkyQTQxOS42NDggNDE5LjY0OCAwIDAgMCA5Mi4wMzIgNDg5LjQwOGgxNDQuODk2YzIuNjg4LTkxLjUyIDE5LjUyLTE3Ni42NCA0Ni40LTI0Ny40ODhhNDc4LjQ2NCA0NzguNDY0IDAgMCAxLTU4LjM2OC0zNi45Mjh6TTkyLjAzMiA1MzUuMjMyYTQyMC44IDQyMC44IDAgMCAwIDEyMi42MjQgMjc0LjMwNGwxMC4zMDQgMTAuMjRjMTguNDMyLTE0LjAxNiAzNy44ODgtMjYuNDk2IDU4LjM2OC0zNy4zNzYtMjYuODgtNzEuMTA0LTQzLjcxMi0xNTUuNzc2LTQ2LjQtMjQ3LjIzMkg5Mi4wMzJ6bTE2OS4yOCAzMTQuNDMyYzI2LjU2IDE5Ljg0IDU1LjI5NiAzNi40MTYgODUuNzYgNDkuNDA4YTM2MC41MTIgMzYwLjUxMiAwIDAgMS0zMy42NjQtNTEuNTg0IDM1MS42MTYgMzUxLjYxNiAwIDAgMS0xMS42NDgtMjIuNzg0IDQxNi42NCA0MTYuNjQgMCAwIDAtNDAuNDQ4IDI0Ljk2em0yNzMuNDcyIDgyLjQ5NmEzNzEuODQgMzcxLjg0IDAgMCAwIDQ2LjY1Ni01LjQ0YzMzLjQwOC0yMC4zNTIgNjQtNTUuNjE2IDg4Ljk2LTEwMS4xODQgMy41Mi02Ljc4NCA3LjY4LTEzLjgyNCAxMC41Ni0yMC45MjhhMTMzLjg4OCAxMzMuODg4IDAgMCAwLTE3LjAyNC02LjQ2NCA0MDUuMjQ4IDQwNS4yNDggMCAwIDAtMTI5LjE1Mi0yNi42MjR2MTYwLjY0em0xNDIuMTQ0LTMzLjA4OGE0MTYuMzIgNDE2LjMyIDAgMCAwIDg1Ljc2LTQ5LjQwOCAzOTAuNjU2IDM5MC42NTYgMCAwIDAtNDAuMTkyLTI0Ljk2bC0xMS45MDQgMjIuNzg0YTQxNS4zNiA0MTUuMzYgMCAwIDEtMzMuNiA1MS41ODR6bTEyMS43OTItNzkuMjk2bDEwLjYyNC0xMC4yNGE0MjAuOCA0MjAuOCAwIDAgMCAxMjIuNjI0LTI3NC4zNjhINzg3LjA3MmMtMi42ODggOTEuNTItMTkuNTIgMTc2LjEyOC00Ni42NTYgMjQ3LjIzMiAyMC40OCAxMC43NTIgNDAgMjMuMjMyIDU4LjMwNCAzNy4zNzZ6bS05OS44NC01NTguMDhhMjAzLjY0OCAyMDMuNjQ4IDAgMCAxLTE4Ljk0NCA3LjM2IDQ2MC42MDggNDYwLjYwOCAwIDAgMS0xNDUuMTUyIDI5LjgyNHYxOTAuNDY0aDIwNi4yMDhjLTIuNDMyLTg0LjM1Mi0xNy40MDgtMTYyLjU2LTQyLjA0OC0yMjcuNjQ4em0tMjA5LjY2NCAzNy4xMmE0NTYuMDY0IDQ1Ni4wNjQgMCAwIDEtMTQ0Ljg5Ni0yOS43NiAxODcuOTA0IDE4Ny45MDQgMCAwIDEtMTkuNTItNy4zNmMtMjQuMzg0IDY1LjA4OC0zOS42MTYgMTQzLjI5Ni00Mi4wNDggMjI3LjY0OGgyMDYuNDY0VjI5OC44OHptMCA0MjYuNjI0VjUzNS4xNjhIMjgyLjc1MmMyLjQzMiA4NC4xNiAxNy42NjQgMTYxLjk4NCA0Mi4wNDggMjI3LjM5MiA2LjUyOC0yLjQzMiAxMy4wNTYtNS4xMiAxOS41Mi03LjI5NmE0NjMuNjggNDYzLjY4IDAgMCAxIDE0NC44OTYtMjkuODI0em00NS41NjggMGE0NjUuMzQ0IDQ2NS4zNDQgMCAwIDEgMTQ0Ljg5NiAyOS44MjRjNi40NjQgMi4xNzYgMTIuNzM2IDQuODY0IDE5LjIgNy4yOTYgMjQuNzA0LTY1LjQwOCAzOS42OC0xNDMuMjMyIDQyLjExMi0yMjcuMzkySDUzNC43ODRWNzI1LjQ0eiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
          },
          {
            id: 'node1',
            name: '节点1',
            topoType: 'icon',
            icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTUxMiAxNS4wNGE0OTcuOTIgNDk3LjkyIDAgMCAxIDQ5Ny4wMjQgNDk3LjA4OCA0OTYuODMyIDQ5Ni44MzIgMCAwIDEtMTQ1LjcyOCAzNTEuNjhBNDk0LjQgNDk0LjQgMCAwIDEgNTEyIDEwMDguOTZhNDkzLjgyNCA0OTMuODI0IDAgMCAxLTM1MS4zNi0xNDUuMTUyIDQ5Ni44MzIgNDk2LjgzMiAwIDAgMS0xNDUuNTM2LTM1MS42OEE0OTcuOTIgNDk3LjkyIDAgMCAxIDUxMiAxNS4wNHptLTIyLjc4NCA5MTcuMTJWNzcxLjUyYTQwNS4xMiA0MDUuMTIgMCAwIDAtMTI5LjE1MiAyNi42MjQgMTMxLjY1MiAxMzEuNjUyIDAgMCAwLTE3LjA4OCA2LjQ2NGMzLjUyIDcuMDQgNi43ODQgMTQuMDggMTAuNTYgMjAuOTI4IDI1LjUzNiA0NS41NjggNTUuMzYgODAuODk2IDg4Ljk2IDEwMS4xODQgMTUuNDg4IDIuODE2IDMxLjA0IDQuNjA4IDQ2LjcyIDUuNDR6bTMyMC4xMjgtNzE3LjEyYTEyOC43NjggMTI4Ljc2OCAwIDAgMC0xMC42MjQtMTAuMDQ4IDQ0MS4yMTYgNDQxLjIxNiAwIDAgMS01OC4yNCAzNi45MjhjMjcuMDcyIDcwLjc4NCA0My45MDQgMTU2LjAzMiA0Ni41OTIgMjQ3LjQyNGgxNDQuODk2QTQxOS42NDggNDE5LjY0OCAwIDAgMCA4MDkuMzQ0IDIxNS4wNHptLTQ2LjcyLTQwLjM4NGE0MTUuMzYgNDE1LjM2IDAgMCAwLTg1LjY5Ni00OS40NzJjMTIuNDE2IDE2LjM4NCAyMy42OCAzMy42IDMzLjY2NCA1MS41ODQgMy44NCA3LjA0IDcuODcyIDE1LjIzMiAxMS45MDQgMjMuMzYgMTMuNTY4LTguMTI4IDI3LjEzNi0xNi41NzYgNDAuMTI4LTI1LjUzNnpNNTgxLjQ0IDk3LjIxNmE1MzIuMzUyIDUzMi4zNTIgMCAwIDAtNDYuNjU2LTUuMTJ2MTYxLjIxNmE0MjguOTkyIDQyOC45OTIgMCAwIDAgMTQ2LjE3Ni0zMy40MDhjLTIuOTQ0LTcuMjk2LTcuMDQtMTQuMzM2LTEwLjQ5Ni0yMC44NjQtMjQuOTYtNDYuMTQ0LTU1LjY4LTgwLjg5Ni04OS4wMjQtMTAxLjc2em0tOTIuMjI0LTUuMTJhNTM0LjAxNiA1MzQuMDE2IDAgMCAwLTQ2LjcyIDUuMTJjLTMzLjYgMjAuOTI4LTYzLjQyNCA1NS42OC04OC45NiAxMDEuODI0LTMuNzc2IDYuNTI4LTcuMDQgMTMuNTY4LTEwLjgxNiAyMC44NjRhNDI4LjggNDI4LjggMCAwIDAgMTQ2LjQ5NiAzMy40MDhWOTIuMTZ6bS0xNDIuMTQ0IDMzLjA4OGE0MTQuODQ4IDQxNC44NDggMCAwIDAtODUuNzYgNDkuNDcyYzEzLjA1NiA4Ljk2IDI2LjYyNCAxNy4yOCA0MC40NDggMjUuNDcyYTM3NS4xNjggMzc1LjE2OCAwIDAgMSA0NS4zMTItNzQuODh6TTIyNC45NiAyMDQuOTkyQTQxOS42NDggNDE5LjY0OCAwIDAgMCA5Mi4wMzIgNDg5LjQwOGgxNDQuODk2YzIuNjg4LTkxLjUyIDE5LjUyLTE3Ni42NCA0Ni40LTI0Ny40ODhhNDc4LjQ2NCA0NzguNDY0IDAgMCAxLTU4LjM2OC0zNi45Mjh6TTkyLjAzMiA1MzUuMjMyYTQyMC44IDQyMC44IDAgMCAwIDEyMi42MjQgMjc0LjMwNGwxMC4zMDQgMTAuMjRjMTguNDMyLTE0LjAxNiAzNy44ODgtMjYuNDk2IDU4LjM2OC0zNy4zNzYtMjYuODgtNzEuMTA0LTQzLjcxMi0xNTUuNzc2LTQ2LjQtMjQ3LjIzMkg5Mi4wMzJ6bTE2OS4yOCAzMTQuNDMyYzI2LjU2IDE5Ljg0IDU1LjI5NiAzNi40MTYgODUuNzYgNDkuNDA4YTM2MC41MTIgMzYwLjUxMiAwIDAgMS0zMy42NjQtNTEuNTg0IDM1MS42MTYgMzUxLjYxNiAwIDAgMS0xMS42NDgtMjIuNzg0IDQxNi42NCA0MTYuNjQgMCAwIDAtNDAuNDQ4IDI0Ljk2em0yNzMuNDcyIDgyLjQ5NmEzNzEuODQgMzcxLjg0IDAgMCAwIDQ2LjY1Ni01LjQ0YzMzLjQwOC0yMC4zNTIgNjQtNTUuNjE2IDg4Ljk2LTEwMS4xODQgMy41Mi02Ljc4NCA3LjY4LTEzLjgyNCAxMC41Ni0yMC45MjhhMTMzLjg4OCAxMzMuODg4IDAgMCAwLTE3LjAyNC02LjQ2NCA0MDUuMjQ4IDQwNS4yNDggMCAwIDAtMTI5LjE1Mi0yNi42MjR2MTYwLjY0em0xNDIuMTQ0LTMzLjA4OGE0MTYuMzIgNDE2LjMyIDAgMCAwIDg1Ljc2LTQ5LjQwOCAzOTAuNjU2IDM5MC42NTYgMCAwIDAtNDAuMTkyLTI0Ljk2bC0xMS45MDQgMjIuNzg0YTQxNS4zNiA0MTUuMzYgMCAwIDEtMzMuNiA1MS41ODR6bTEyMS43OTItNzkuMjk2bDEwLjYyNC0xMC4yNGE0MjAuOCA0MjAuOCAwIDAgMCAxMjIuNjI0LTI3NC4zNjhINzg3LjA3MmMtMi42ODggOTEuNTItMTkuNTIgMTc2LjEyOC00Ni42NTYgMjQ3LjIzMiAyMC40OCAxMC43NTIgNDAgMjMuMjMyIDU4LjMwNCAzNy4zNzZ6bS05OS44NC01NTguMDhhMjAzLjY0OCAyMDMuNjQ4IDAgMCAxLTE4Ljk0NCA3LjM2IDQ2MC42MDggNDYwLjYwOCAwIDAgMS0xNDUuMTUyIDI5LjgyNHYxOTAuNDY0aDIwNi4yMDhjLTIuNDMyLTg0LjM1Mi0xNy40MDgtMTYyLjU2LTQyLjA0OC0yMjcuNjQ4em0tMjA5LjY2NCAzNy4xMmE0NTYuMDY0IDQ1Ni4wNjQgMCAwIDEtMTQ0Ljg5Ni0yOS43NiAxODcuOTA0IDE4Ny45MDQgMCAwIDEtMTkuNTItNy4zNmMtMjQuMzg0IDY1LjA4OC0zOS42MTYgMTQzLjI5Ni00Mi4wNDggMjI3LjY0OGgyMDYuNDY0VjI5OC44OHptMCA0MjYuNjI0VjUzNS4xNjhIMjgyLjc1MmMyLjQzMiA4NC4xNiAxNy42NjQgMTYxLjk4NCA0Mi4wNDggMjI3LjM5MiA2LjUyOC0yLjQzMiAxMy4wNTYtNS4xMiAxOS41Mi03LjI5NmE0NjMuNjggNDYzLjY4IDAgMCAxIDE0NC44OTYtMjkuODI0em00NS41NjggMGE0NjUuMzQ0IDQ2NS4zNDQgMCAwIDEgMTQ0Ljg5NiAyOS44MjRjNi40NjQgMi4xNzYgMTIuNzM2IDQuODY0IDE5LjIgNy4yOTYgMjQuNzA0LTY1LjQwOCAzOS42OC0xNDMuMjMyIDQyLjExMi0yMjcuMzkySDUzNC43ODRWNzI1LjQ0eiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
          },
          {
            id: 'node2',
            name: '节点2',
            compareValue: 56,
            number1: 56,
            number2: 78,
            topoType: 'number',
          },
          {
            id: 'node3',
            name: '节点3',
            compareValue: -78,
            number1: 56,
            number2: 78,
            topoType: 'number',
          },
          {
            id: 'node4',
            name: '节点4',
            compareValue: -78,
            number1: 56,
            number2: 78,
            topoType: 'number',
          },
          {
            id: 'node5',
            name: '节点5',
            compareValue: -78,
            number1: 56,
            number2: 78,
            topoType: 'number',
            lineDash: [4, 4],
          },
        ],
        edges: [
          {
            source: 'node0', // 起始点 id
            target: 'node1', // 目标点 id
          },
          {
            source: 'node1', // 起始点 id
            target: 'node2', // 目标点 id
          },
          {
            source: 'node2', // 起始点 id
            target: 'node3', // 目标点 id
          },
          {
            source: 'node1', // 起始点 id
            target: 'node4', // 目标点 id
          },
          {
            source: 'node1', // 起始点 id
            target: 'node5', // 目标点 id
          },
          {
            source: 'node4', // 起始点 id
            target: 'node5', // 目标点 id
          },
        ],
      };
    }, 300);
  }

  @Emit('showChange')
  handleShowChange(show?: boolean) {
    if (!show) this.compareTopoGraphRef.reset();
    return show ?? !this.show;
  }

  handleNodeClick(val) {
    this.activeNode = val;
  }

  handleCallBtnClick(type: string) {
    this.filterParam.call = type;
  }

  render() {
    return (
      <bk-dialog
        ext-cls='compare-topo-fullscreen-dialog'
        show-footer={false}
        value={this.show}
        fullscreen
        on-value-change={this.handleShowChange}
      >
        <div
          class='dialog-header'
          slot='tools'
        >
          {this.$t('对比拓扑')}
        </div>
        <bk-resize-layout
          class='dialog-content'
          initial-divide={320}
          max={500}
          min={320}
          placement='right'
        >
          <div
            class='topo-chart'
            slot='main'
          >
            <div class='header-tools'>
              <div class='filter-wrap'>
                <bk-select
                  v-model={this.filterParam.type}
                  clearable={false}
                >
                  {this.filterTypeList.map(item => (
                    <bk-option
                      id={item.value}
                      key={item.value}
                      name={item.label}
                    />
                  ))}
                </bk-select>
                {this.showSecondSelect && (
                  <bk-select
                    v-model={this.filterParam.count}
                    clearable={false}
                  >
                    {this.secondSelectList.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                )}
                <div class='bk-button-group'>
                  <bk-button
                    class={{ 'is-selected': this.filterParam.call === EOptionKind.caller }}
                    onClick={() => {
                      this.handleCallBtnClick(EOptionKind.caller);
                    }}
                  >
                    {this.$t('主调')}
                  </bk-button>
                  <bk-button
                    class={{ 'is-selected': this.filterParam.call === EOptionKind.callee }}
                    onClick={() => {
                      this.handleCallBtnClick(EOptionKind.callee);
                    }}
                  >
                    {this.$t('被调')}
                  </bk-button>
                </div>
              </div>
              <div class='compare-time-panel'>
                <div class='panel-item'>
                  <div class='color-block' />
                  <div class='text'>
                    <span class='name'>{this.$t('参照时间')}:</span>
                    {this.formatTime.refer}
                  </div>
                </div>
                <div class='panel-item'>
                  <div class='color-block' />
                  <div class='text'>
                    <span class='name'>{this.$t('对比时间')}:</span>
                    {this.formatTime.compare}
                  </div>
                </div>
              </div>
            </div>
            <CompareTopoGraph
              ref='compareTopoGraph'
              activeNode={this.activeNode}
              data={this.graphData}
              onNodeClick={this.handleNodeClick}
            />
          </div>
          <div
            class='service-overview-panel'
            slot='aside'
          >
            <div class='panel-title title'>{this.$t(this.isServer ? '服务概览' : '接口概览')}</div>
            <div class='panel-content'>
              <div class='panel-form'>
                <div class='form-header'>
                  <div class='form-title'>
                    <i class='icon-monitor icon-wangye' />
                    <div class='title'>Mongo</div>
                  </div>
                  {this.isServer && (
                    <div class='setting-btn'>
                      {this.$t('服务配置')}
                      <i class='icon-monitor icon-shezhi' />
                    </div>
                  )}
                </div>
                <div class='form-content'>
                  <div class='form-item'>
                    <div class='item-label'>{this.$t('类型')}:</div>
                    <div class='item-value'>Mysql</div>
                  </div>
                  <div class='form-item'>
                    <div class='item-label'>{this.$t('语言')}:</div>
                    <div class='item-value'>php</div>
                  </div>
                  {this.isServer && [
                    <div
                      key='0'
                      class='form-item'
                    >
                      <div class='item-label'>{this.$t('实例数')}:</div>
                      <div class='item-value'>2</div>
                    </div>,
                    <div
                      key='1'
                      class='form-item'
                    >
                      <div class='item-label'>{this.$t('三方应用')}:</div>
                      <div class='item-value'>
                        memcache
                        <i class='icon-monitor icon-fenxiang' />
                      </div>
                    </div>,
                  ]}
                </div>
              </div>
              <bk-table
                class='panel-table'
                data={this.tableData}
                outer-border={false}
              >
                <bk-table-column
                  label={this.$t('对比数据')}
                  min-width='100px'
                  prop='a'
                />
                <bk-table-column
                  label={this.$t('对比')}
                  min-width='50px'
                  prop='b'
                  sortable
                />
                <bk-table-column
                  label={this.$t('参照')}
                  min-width='50px'
                  prop='c'
                  sortable
                />
                <bk-table-column
                  scopedSlots={{
                    default: ({ row }) => <span class={[row.d.startsWith('+') ? 'up' : 'down']}>{row.d}</span>,
                  }}
                  label={this.$t('差异值')}
                  min-width='75px'
                  prop='d'
                  sortable
                />
              </bk-table>
            </div>
          </div>
        </bk-resize-layout>
      </bk-dialog>
    );
  }
}
