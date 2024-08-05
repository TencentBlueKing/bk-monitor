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
import type { VNode } from 'vue';

export type CommomParams = Record<string, any>;
export type IObjectType = 'HOST' | 'SERVICE';
export type INodeType =
  | 'DYNAMIC_GROUP'
  | 'INSTANCE'
  | 'SERVICE_INSTANCE'
  | 'SERVICE_TEMPLATE'
  | 'SET_TEMPLATE'
  | 'TOPO';
export type CoutIntanceName = 'host' | 'service_instance';
export interface IScopeItme {
  scope_type: string;
  scope_id: string;
}

export interface IMeta {
  bk_biz_id: number;
  scope_id: string;
  scope_type: 'biz' | 'space';
}

export interface INode {
  id?: number;
  instance_id: number;
  object_id: 'biz' | 'module' | 'set';
  service_instance_id?: string;
  meta: IMeta;
}
export interface IHost {
  host_id: number;
  ip: string;
  cloud_area: ICloudArea;
  meta: IMeta;
  display_name?: string;
}
export interface ITarget {
  // node_type = 'INSTANCE' => bk_host_id  ||  'TOPO' => bk_obj_id && bk_inst_id
  bk_biz_id: number;
  bk_obj_id?: 'module' | 'set';
  bk_inst_id?: number;
  bk_host_id?: number;
  biz_inst_id?: string;
  dynamic_group_id?: string;
  path?: string;
  children?: ITarget[];
  meta?: IMeta;
  ip?: string;
  bk_cloud_id?: number;
}

export interface ITreeItem extends INode {
  count: number;
  expanded: boolean;
  object_name: string;
  instance_name: string;
  child: ITreeItem[];
}
export interface IFetchNode {
  node_list: INode[];
  dynamic_group_list?: Record<string, any>[];
}

export type IStatic = 'alive_count' | 'not_alive_count' | 'total_count';

export type IStatistics = Record<IStatic, number>;

export interface IQuery {
  id?: number;
  start?: number;
  page_size?: number;
  search_content?: string;
  node_list: INode[];
  saveScope?: boolean;
  // 以上 IP-selector标准参数
  all_scope?: boolean;
  search_limit?: {
    node_list?: INode[];
    host_ids?: number[];
  }; // 灰度策略的限制范围
}
export interface ISelectorValue {
  dynamic_group_list: Record<string, any>[];
  host_list: IHost[];
  node_list: INode[];
}
export interface IScope {
  // object_type?: IObjectType
  node_type: INodeType;
  nodes: ITarget[];
}
export interface IGroupItem {
  id: string;
  name: string;
  meta?: IMeta;
}
export interface ICloudArea {
  id: number;
  name: string;
}
export interface IGroupHost {
  meta?: IMeta;
  ip: string;
  ipv6: string;
  host_name: string;
  alive: number;
  cloud_id: number;
  host_id: number;
  os_name: string;
  cloud_area: ICloudArea;
}
export interface IGroupHostQuery {
  id: string;
  strart: number;
  page_siza: number;
}
export interface ITemplateItem {
  id: number;
  name: string;
  service_category: string;
  template_type: INodeType;
  meta?: IMeta;
}
export interface ITemplateNodeItem {
  instance_id: number;
  instance_name: number;
  object_id: string;
  object_name: string;
  template_id: number;
  meta?: IMeta;
}
export interface ITemplateNode {
  start: number;
  count: number;
  page_size: number;
  data: ITemplateNodeItem[];
}
export interface ITemplateHost {
  start: number;
  count: number;
  page_size: number;
  data: IHost[];
}

export type IpSelectorMode = 'dialog' | 'section';
export type IpSelectorNameStyle = 'camelCase' | 'kebabCase';
export type IpSelectorService = {
  fetchTopologyHostCount?: (params: CommomParams) => Promise<any>;
  fetchTopologyServiceInstance?: (params: CommomParams) => Promise<any>;
  fetchSeriviceInstanceList?: (params: CommomParams) => Promise<any>;
  fetchSeriviceInstanceDetails?: (params: CommomParams) => Promise<any>;
  fetchTopologyHostsNodes?: (params: CommomParams) => Promise<any>;
  fetchTopologyHostIdsNodes?: (params: CommomParams) => Promise<any>;
  fetchHostsDetails?: (params: CommomParams) => Promise<any>;
  fetchHostCheck?: (params: CommomParams) => Promise<any>;
  fetchNodesQueryPath?: (params: CommomParams) => Promise<any>;
  fetchHostAgentStatisticsNodes?: (params: CommomParams) => Promise<any>;
  fetchDynamicGroups?: (params: CommomParams) => Promise<any>;
  fetchHostsDynamicGroup?: (params: CommomParams) => Promise<any>;
  fetchHostAgentStatisticsDynamicGroups?: (params: CommomParams) => Promise<any>;
  fetchServiceTemplates?: (params: CommomParams) => Promise<any>;
  fetchNodesServiceTemplate?: (params: CommomParams) => Promise<any>;
  fetchHostServiceTemplate?: (params: CommomParams) => Promise<any>;
  fetchHostAgentStatisticsServiceTemplate?: (params: CommomParams) => Promise<any>;
  fetchSetTemplates?: (params: CommomParams) => Promise<any>;
  fetchNodesSetTemplate?: (params: CommomParams) => Promise<any>;
  fetchHostSetTemplate?: (params: CommomParams) => Promise<any>;
  fetchHostAgentStatisticsSetTemplate?: (params: CommomParams) => Promise<any>;
  fetchCustomSettings?: (params: CommomParams) => Promise<any>;
  updateCustomSettings?: (params: CommomParams) => Promise<any>;
  fetchConfig?: (params: CommomParams) => Promise<any>;
};
export type IpSelectorConfig = {
  // 需要支持的面板（'staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'manualInput'）
  panelList?: string[];
  // 面板选项的值是否唯一
  unqiuePanelValue?: boolean;
  // 字段命名风格（'camelCase', 'kebabCase'）
  nameStyle?: IpSelectorNameStyle;
  // 自定义主机列表列
  hostTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  nodeTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  serviceTemplateTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  setTemplateTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  hostMemuExtends?: IpSelectorHostMemuExtend[];
  // 主机列表显示列（默认值：['ip', 'ipv6', 'alive', 'osName']），按配置顺序显示列
  // 内置所有列的 key ['ip', 'ipv6', 'cloudArea', 'alive', 'hostName',
  //  'osName', 'coludVerdor', 'osType', 'hostId', 'agentId']
  hostTableRenderColumnList?: string[];
  hostViewFieldRender?: (v: IHost, b: string) => any;
  serviceConfigError?: boolean;
};
export type IpSelectorHostTableCustomColumn = {
  key: string;
  index: number;
  width: string;
  label: string;
  renderHead: (h) => VNode;
  field: string;
  renderCell: (h, row) => VNode;
};
export type IpSelectorHostMemuExtend = {
  name?: string;
  action?: () => void;
};

export interface IIpV6Value {
  dynamic_group_list?: any[];
  host_list?: IHost[];
  node_list?: INode[];
  service_template_list?: any[];
  set_template_list?: any[];
  service_instance_list?: any[];
}
export type TargetObjectType = 'HOST' | 'SERVICE';
