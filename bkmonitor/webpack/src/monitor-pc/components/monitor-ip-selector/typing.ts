/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

export type CommonParams = Record<string, any>;
export type CountInstanceName = 'host' | 'service_instance';
export interface ICloudArea {
  id: number;
  name: string;
}
export interface IFetchNode {
  dynamic_group_list?: Record<string, any>[];
  node_list: INode[];
}
export interface IGroupHost {
  alive: number;
  cloud_area: ICloudArea;
  cloud_id: number;
  host_id: number;
  host_name: string;
  ip: string;
  ipv6: string;
  meta?: IMeta;
  os_name: string;
}

export interface IGroupHostQuery {
  id: string;
  page_siza: number;
  strart: number;
}

export interface IGroupItem {
  id: string;
  meta?: IMeta;
  name: string;
}
export interface IHost {
  cloud_area: ICloudArea;
  display_name?: string;
  host_id: number;
  ip: string;
  meta: IMeta;
}
export interface IIpV6Value {
  dynamic_group_list?: any[];
  host_list?: IHost[];
  node_list?: INode[];
  service_instance_list?: any[];
  service_template_list?: any[];
  set_template_list?: any[];
}

export interface IMeta {
  bk_biz_id: number;
  scope_id: string;
  scope_type: 'biz' | 'space';
}
export interface INode {
  id?: number;
  instance_id: number;
  meta: IMeta;
  object_id: 'biz' | 'module' | 'set';
  service_instance_id?: string;
}

export type INodeType =
  | 'DYNAMIC_GROUP'
  | 'INSTANCE'
  | 'SERVICE_INSTANCE'
  | 'SERVICE_TEMPLATE'
  | 'SET_TEMPLATE'
  | 'TOPO';

export type IObjectType = 'HOST' | 'SERVICE';

export type IpSelectorConfig = {
  hostMemuExtends?: IpSelectorHostMenuExtend[];
  // 自定义主机列表列
  hostTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  // 主机列表显示列（默认值：['ip', 'ipv6', 'alive', 'osName']），按配置顺序显示列
  // 内置所有列的 key ['ip', 'ipv6', 'cloudArea', 'alive', 'hostName',
  //  'osName', 'coludVerdor', 'osType', 'hostId', 'agentId']
  hostTableRenderColumnList?: string[];
  hostViewFieldRender?: (v: IHost, b: string) => any;
  // 字段命名风格（'camelCase', 'kebabCase'）
  nameStyle?: IpSelectorNameStyle;
  nodeTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  // 需要支持的面板（'staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'manualInput'）
  panelList?: string[];
  serviceConfigError?: boolean;
  serviceTemplateTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  setTemplateTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  // 面板选项的值是否唯一
  unqiuePanelValue?: boolean;
};
export type IpSelectorHostMenuExtend = {
  action?: () => void;
  name?: string;
};
export type IpSelectorHostTableCustomColumn = {
  field: string;
  index: number;
  key: string;
  label: string;
  renderCell: (h, row) => VNode;
  renderHead: (h) => VNode;
  width: string;
};
export type IpSelectorMode = 'dialog' | 'section';
export type IpSelectorNameStyle = 'camelCase' | 'kebabCase';
export type IpSelectorService = {
  fetchConfig?: (params: CommonParams) => Promise<any>;
  fetchCustomSettings?: (params: CommonParams) => Promise<any>;
  fetchDynamicGroups?: (params: CommonParams) => Promise<any>;
  fetchHostAgentStatisticsDynamicGroups?: (params: CommonParams) => Promise<any>;
  fetchHostAgentStatisticsNodes?: (params: CommonParams) => Promise<any>;
  fetchHostAgentStatisticsServiceTemplate?: (params: CommonParams) => Promise<any>;
  fetchHostAgentStatisticsSetTemplate?: (params: CommonParams) => Promise<any>;
  fetchHostCheck?: (params: CommonParams) => Promise<any>;
  fetchHostsDetails?: (params: CommonParams) => Promise<any>;
  fetchHostsDynamicGroup?: (params: CommonParams) => Promise<any>;
  fetchHostServiceTemplate?: (params: CommonParams) => Promise<any>;
  fetchHostSetTemplate?: (params: CommonParams) => Promise<any>;
  fetchNodesQueryPath?: (params: CommonParams) => Promise<any>;
  fetchNodesServiceTemplate?: (params: CommonParams) => Promise<any>;
  fetchNodesSetTemplate?: (params: CommonParams) => Promise<any>;
  fetchSeriviceInstanceDetails?: (params: CommonParams) => Promise<any>;
  fetchSeriviceInstanceList?: (params: CommonParams) => Promise<any>;
  fetchServiceTemplates?: (params: CommonParams) => Promise<any>;
  fetchSetTemplates?: (params: CommonParams) => Promise<any>;
  fetchTopologyHostCount?: (params: CommonParams) => Promise<any>;
  fetchTopologyHostIdsNodes?: (params: CommonParams) => Promise<any>;
  fetchTopologyHostsNodes?: (params: CommonParams) => Promise<any>;
  fetchTopologyServiceInstance?: (params: CommonParams) => Promise<any>;
  updateCustomSettings?: (params: CommonParams) => Promise<any>;
};
export interface IQuery {
  // 以上 IP-selector标准参数
  all_scope?: boolean;
  id?: number;
  node_list: INode[];
  page_size?: number;
  saveScope?: boolean;
  search_content?: string;
  start?: number;
  search_limit?: {
    host_ids?: number[];
    node_list?: INode[];
  }; // 灰度策略的限制范围
}
export interface IScope {
  // object_type?: IObjectType
  node_type: INodeType;
  nodes: ITarget[];
}
export interface IScopeItem {
  scope_id: string;
  scope_type: string;
}
export interface ISelectorValue {
  dynamic_group_list: Record<string, any>[];
  host_list: IHost[];
  node_list: INode[];
}
export type IStatic = 'alive_count' | 'not_alive_count' | 'total_count';

export type IStatistics = Record<IStatic, number>;
export interface ITarget {
  biz_inst_id?: string;
  // node_type = 'INSTANCE' => bk_host_id  ||  'TOPO' => bk_obj_id && bk_inst_id
  bk_biz_id: number;
  bk_cloud_id?: number;
  bk_host_id?: number;
  bk_inst_id?: number;
  bk_obj_id?: 'module' | 'set';
  children?: ITarget[];
  dynamic_group_id?: string;
  ip?: string;
  meta?: IMeta;
  path?: string;
}
export interface ITemplateHost {
  count: number;
  data: IHost[];
  page_size: number;
  start: number;
}
export interface ITemplateItem {
  id: number;
  meta?: IMeta;
  name: string;
  service_category: string;
  template_type: INodeType;
}
export interface ITemplateNode {
  count: number;
  data: ITemplateNodeItem[];
  page_size: number;
  start: number;
}
export interface ITemplateNodeItem {
  instance_id: number;
  instance_name: number;
  meta?: IMeta;
  object_id: string;
  object_name: string;
  template_id: number;
}

export interface ITreeItem extends INode {
  child: ITreeItem[];
  count: number;
  expanded: boolean;
  instance_name: string;
  object_name: string;
}
export type TargetObjectType = 'HOST' | 'SERVICE';
