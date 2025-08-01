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

import { random } from 'monitor-common/utils/utils.js';

import type { IEdge, IRank, ITopoData } from '../failure-topo/types';
export enum ComboStatus {
  DataCenter = '数据中心',
  Host = '主机',
  Instance = '服务',
}

export enum EdgeStatus {
  Include = 'include',
  Invoke = 'invoke',
}
export enum NodeStatus {
  Error = 'error',
  Normal = 'normal',
  Root = 'root',
}
export interface IRanksMap {
  [key: string]: IRank[];
}
/** 创建资源图数据 */
export const createGraphData = (ranksMap: IRanksMap, edges: IEdge[]): ITopoData => {
  const combos = [];
  let nodeDatas = [];
  Object.keys(ranksMap).forEach((ranks, index) => {
    const fillColor = '#34383c';
    if (ranksMap[ranks].length > 0) {
      ranksMap[ranks].forEach((rank, index) => {
        const { rank_category, rank_name, rank_alias, nodes, anomaly_count, total, is_sub_rank } = rank;
        const randomStr = random(10);
        combos.push({
          groupId: is_sub_rank ? `${rank_name}${randomStr}` : rank_name,
          groupName: index === 0 ? rank_category.category_alias : '',
          id: rank_category.category_name + rank_name + (is_sub_rank ? randomStr : ''),
          anomaly_count: is_sub_rank ? 0 : anomaly_count,
          subTitle: is_sub_rank ? '' : `${anomaly_count > 0 ? '/' : ''} ${total}`,
          title: is_sub_rank ? '' : rank_alias,
          style: {
            fill: fillColor,
            stroke: fillColor,
          },
        });
        nodes.forEach(node => {
          const { is_root, is_anomaly } = node.entity;
          node.comboId = rank_category.category_name + rank_name + (is_sub_rank ? randomStr : '');
          node.status = is_root || is_anomaly ? (is_root ? 'root' : 'error') : 'normal';
        });
        nodeDatas = nodeDatas.concat(rank.nodes);
      });
    } else {
      const { rank_category, rank_name, rank_alias, nodes, anomaly_count, total } = ranksMap[ranks][0];
      combos.push({
        groupId: rank_name,
        groupName: rank_category.category_alias,
        id: rank_category.category_name,
        anomaly_count,
        subTitle: `${anomaly_count > 0 ? '/' : ''} ${total}`,
        title: rank_alias,
        style: {
          fill: fillColor,
          stroke: fillColor,
        },
      });
      nodes.forEach(node => {
        const { is_root, is_anomaly } = node.entity;
        node.comboId = rank_category.category_name + rank_name;
        node.status = is_root || is_anomaly ? (is_root ? 'root' : 'error') : 'normal';
      });
      nodeDatas = nodeDatas.concat(nodes);
    }
  });
  return {
    combos,
    nodes: nodeDatas,
    edges,
  };
};
