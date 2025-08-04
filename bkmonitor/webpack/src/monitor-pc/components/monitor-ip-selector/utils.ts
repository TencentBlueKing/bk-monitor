import type { IHost, IIpV6Value, INode, INodeType, ITarget, TargetObjectType } from './typing';

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
export const PanelTargetMap = {
  staticTopo: 'INSTANCE',
  dynamicTopo: 'TOPO',
  serviceTemplate: 'SERVICE_TEMPLATE',
  setTemplate: 'SET_TEMPLATE',
  manualInput: 'INSTANCE',
  dynamicGroup: 'DYNAMIC_GROUP',
};
export const NodeTypeByMonitorKeyMap = {
  host_list: 'INSTANCE',
  node_list: 'TOPO',
  service_template_list: 'SERVICE_TEMPLATE',
  set_template_list: 'SET_TEMPLATE',
  dynamic_group_list: 'DYNAMIC_GROUP',
};

export function getPanelListByObjectType(objectType: TargetObjectType) {
  if (objectType === 'SERVICE') {
    return ['dynamicTopo', 'serviceTemplate', 'setTemplate'];
  }
  return ['staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'manualInput'];
}
/**
 * 转换成标准的IP选择器的选中数据
 */
export function toSelectorNode(nodes: ITarget[], nodeType: INodeType) {
  if (!nodeType) return nodes;

  switch (nodeType) {
    case 'INSTANCE':
      return nodes.map(item => {
        // 增量数据只需使用host_id
        if (item.bk_host_id) return { host_id: item.bk_host_id };
        // 兼容旧数据 没有bk_host_id的情况下 把ip和cloud_id传给组件 提供组件内部定位host_id
        return { host_id: undefined, ip: item.ip, cloud_id: item.bk_cloud_id };
      });
    case 'TOPO':
      return nodes.map(item => ({
        object_id: item.bk_obj_id,
        instance_id: item.bk_inst_id,
      }));
    case 'SERVICE_TEMPLATE':
    case 'SET_TEMPLATE':
      return nodes.map(item => ({
        id: item.bk_inst_id,
      }));
    case 'DYNAMIC_GROUP':
      return nodes.map(item => ({
        id: item.dynamic_group_id,
      }));
    default:
      return [];
  }
}

export function transformCacheMapToOriginData(
  data: any[],
  key: keyof typeof NodeTypeByMonitorKeyMap,
  cacheMap = {}
): any | IIpV6Value {
  const nodeType = NodeTypeByMonitorKeyMap[key];
  if (!nodeType) return data;
  switch (nodeType) {
    case 'DYNAMIC_GROUP':
      return data.map(item => cacheMap?.[nodeType]?.[item.id] || item);
    default:
      return data;
  }
}
export function transformMonitorToValue(data: any[], nodeType: INodeType): any | IIpV6Value {
  if (!nodeType) return {};
  switch (nodeType) {
    case 'INSTANCE':
      return {
        host_list: data.map(item =>
          // 增量数据只需使用host_id
          // if (item.bk_host_id) return { host_id: item.bk_host_id };
          // // 兼容旧数据 没有bk_host_id的情况下 把ip和cloud_id传给组件 提供组件内部定位host_id
          // return { host_id: undefined, ip: item.ip, cloud_id: item.bk_cloud_id };
          ({
            host_id: item.bk_host_id,
            ip: 'ip' in item ? item.ip : item.bk_target_ip,
            cloud_id: 'bk_cloud_id' in item ? item.bk_cloud_id : item.bk_target_cloud_id,
            cloud_area: { id: 'bk_cloud_id' in item ? item.bk_cloud_id : item.bk_target_cloud_id },
          })
        ),
      };
    case 'TOPO':
      return {
        node_list: data.map(item => ({
          object_id: item.bk_obj_id,
          instance_id: item.bk_inst_id,
        })),
      };
    case 'SET_TEMPLATE':
      return {
        set_template_list: data.map(item => ({
          id: item.bk_inst_id,
        })),
      };
    case 'SERVICE_TEMPLATE':
      // 查服务模板的id 要用 SERVICE_TEMPLATE 不是用 bk_inst_id
      return {
        service_template_list: data.map(item => ({
          id: item.SERVICE_TEMPLATE || item.bk_inst_id,
        })),
      };
    case 'DYNAMIC_GROUP':
      return {
        dynamic_group_list: data.map(item => ({
          id: item.dynamic_group_id || item.id,
        })),
      };
    default:
      return [];
  }
}
export function transformOriginDataToCacheMap(value: any[], nodeType: INodeType) {
  if (!nodeType) return [];
  switch (nodeType) {
    case 'DYNAMIC_GROUP':
      return value.reduce((prev, curr) => {
        prev[curr.id] = curr;
        return prev;
      }, {});
    default:
      return {};
  }
}

export function transformValueToMonitor(value: IIpV6Value, nodeType: INodeType) {
  if (!nodeType) return [];
  switch (nodeType) {
    case 'INSTANCE':
      return value.host_list.map((item: IHost) => ({
        bk_host_id: item.host_id,
        ip: item.ip,
        bk_cloud_id: item.cloud_area.id,
      }));
    case 'TOPO':
      return value.node_list.map((item: INode) => ({
        bk_obj_id: item.object_id,
        bk_inst_id: item.instance_id,
      }));
    case 'SERVICE_TEMPLATE':
      return value.service_template_list.map((item: INode) => ({
        bk_obj_id: nodeType,
        bk_inst_id: item.id,
      }));
    case 'SET_TEMPLATE':
      return value.set_template_list.map((item: INode) => ({
        bk_obj_id: nodeType,
        bk_inst_id: item.id,
      }));
    case 'SERVICE_INSTANCE':
      return value.service_instance_list.map((item: INode) => item.service_instance_id);
    case 'DYNAMIC_GROUP':
      return value.dynamic_group_list.map((item: INode) => ({
        dynamic_group_id: item.id,
      }));
    default:
      return [];
  }
}
