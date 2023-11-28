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
const nodeCount = 10;
// const comboCount = 6;
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
    let comboId = 6;
    if (i < 3) {
      comboId = 1;
    } else if (i < 6) {
      comboId = 2;
    } else if (i === 6) {
      comboId = 3;
    } else if (i === 7) {
      comboId = 4;
    } else if (i === 8) {
      comboId = 5;
    }
    let status = i % 2 === 0 ? NodeStatus.Error : NodeStatus.Normal;
    if (i === 0) {
      status = NodeStatus.Root;
    }
    return {
      id: `node_${i}`,
      comboId: `combo_${comboId.toString()}`,
      status
    };
  });
};
const nodes = createNodes();
const createEdges = () => {
  return nodes
    .map((node, i) => {
      if (i >= nodes.length - 1) return undefined;
      const curComboId = node.comboId.toString().replace('combo_', '');
      const nextComboId = `combo_${(+curComboId + 1).toString()}`;
      const curComboNodes = nodes.filter(node => node.comboId === `combo_${curComboId}`);
      const nextComboNodes = nodes.filter(node => node.comboId === nextComboId);
      return {
        source: curComboNodes[Math.floor(Math.random() * curComboNodes.length)].id,
        target: nextComboNodes[Math.floor(Math.random() * nextComboNodes.length)].id,
        count: Math.floor(Math.random() * 100),
        type: i % 7 ? EdgeStatus.Include : EdgeStatus.Invoke
      };
    })
    .filter(Boolean);
};
const createCombos = () => {
  const groupCombos = [
    {
      name: '服务',
      id: 'service',
      combos: ['服务模块']
    },
    {
      name: '主机/云平台',
      id: 'host',
      combos: ['K8s', '操作系统']
    },
    {
      name: '数据中心',
      id: 'datacenter',
      combos: ['Rack', 'IDC Unit', 'IDC']
    }
  ];
  let index = 0;
  let groupName = '';
  return groupCombos.reduce((acc, combo) => {
    const list = combo.combos.map(label => {
      index += 1;
      let name = '';
      if (groupName !== combo.name) {
        groupName = combo.name;
        name = groupName;
      }
      return {
        id: `combo_${index.toString()}`,
        title: label,

        subTitle: `${6} / ${index + 1}`,
        groupName: name,
        groupId: combo.id
      };
    });
    return [...acc, ...list];
  }, []);
};
export default {
  nodes,
  edges: createEdges(),
  combos: createCombos()
};

export const StatusNodeMap = {
  [NodeStatus.Normal]: {
    groupAttrs: {
      fill: 'rgba(197, 197, 197, 0.2)',
      stroke: '#979BA5'
    },
    rectAttrs: {
      stroke: '#EAEBF0',
      fill: '#313238'
    },
    textAttrs: {
      fill: '#fff'
    }
  },
  [NodeStatus.Error]: {
    groupAttrs: {
      fill: 'rgba(255, 102, 102, 0.4)',
      stroke: '#F55555'
    },
    rectAttrs: {
      stroke: '#F55555',
      fill: '#313238'
    },
    textErrorAttrs: {
      fill: '#313238'
    },
    textNormalAttrs: {
      fill: '#fff'
    }
  },
  [NodeStatus.Root]: {
    groupAttrs: {
      fill: '#F55555',
      stroke: '#F55555'
    },
    rectAttrs: {
      stroke: '#3A3B3D',
      fill: '#F55555'
    },
    textAttrs: {
      fill: '#fff'
    }
  }
};
