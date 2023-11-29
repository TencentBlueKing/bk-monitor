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
const nodeCount = 36;
const comboCount = 10;
export const enum NodeStatus {
  Normal = 'normal',
  Error = 'error',
  Root = 'root'
}

export const enum EdgeStatus {
  Include = 'include',
  Invoke = 'invoke'
}
export const enum ComboStatus {
  Instance = '服务',
  Host = '主机',
  DataCenter = '数据中心'
}
const createNodes = () => {
  return new Array(nodeCount).fill(0).map((_, i) => {
    const comboId = `combo_${i % comboCount}`;
    let status = i % 2 === 0 ? NodeStatus.Error : NodeStatus.Normal;
    if (i === 0) {
      status = NodeStatus.Root;
    }
    return {
      id: `node_${i}`,
      comboId,
      aggregateNode:
        i % 2 === 0
          ? [
              {
                id: `node_${i}_1`,
                comboId: `${comboId}_1`,
                status: NodeStatus.Normal
              },
              {
                id: `node_${i}_2`,
                comboId: `${comboId}_1`,
                status: NodeStatus.Normal
              },
              {
                id: `node_${i}_3`,
                comboId: `${comboId}_2`,
                status: NodeStatus.Error
              },
              {
                id: `node_${i}_4`,
                comboId: `${comboId}_2`,
                status: NodeStatus.Error
              }
            ]
          : [],
      status
    };
  });
};
const createEdges = () => {
  return new Array(nodeCount * 1).fill(0).map((_, i) => {
    // 随机 0 - 10 之间的整数
    return {
      source: `node_${Math.floor(Math.random() * nodeCount)}`,
      target: `node_${Math.floor(Math.random() * nodeCount)}`,
      count: Math.floor(Math.random() * 100),
      type: i % 7 ? EdgeStatus.Include : EdgeStatus.Invoke
      //  x
    };
  });
};
const createCombos = () => {
  return new Array(comboCount).fill(0).map((_, i) => {
    let status = ComboStatus.Instance;
    if (i === comboCount - 2) {
      status = ComboStatus.Host;
    } else if (i === comboCount - 1) {
      status = ComboStatus.DataCenter;
    }
    return {
      id: `combo_${i}`,
      label: `${status} ${i}`,
      status
    };
  });
};
export default {
  nodes: createNodes(),
  edges: createEdges(),
  combos: createCombos()
};
