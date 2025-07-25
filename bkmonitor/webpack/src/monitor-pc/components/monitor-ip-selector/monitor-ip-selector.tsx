/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import create from '@blueking/ip-selector/dist/index.esm';
import {
  agentStatisticsIpChooserDynamicGroup,
  agentStatisticsIpChooserTemplate,
  agentStatisticsIpChooserTopo,
  batchGetIpChooserConfig,
  checkIpChooserHost,
  detailsIpChooserHost,
  detailsIpChooserServiceInstance,
  executeIpChooserDynamicGroup,
  globalConfigIpChooserConfig,
  groupsIpChooserDynamicGroup,
  hostsIpChooserTemplate,
  nodesIpChooserTemplate,
  queryHostIdInfosIpChooserTopo,
  queryHostsIpChooserTopo,
  queryPathIpChooserTopo,
  queryServiceInstancesIpChooserTopo,
  serviceInstanceCountIpChooserTemplate,
  templatesIpChooserTemplate,
  treesIpChooserTopo,
  updateConfigIpChooserConfig,
} from 'monitor-api/modules/model';

import { PanelTargetMap, transformCacheMapToOriginData, transformOriginDataToCacheMap } from './utils';

import type {
  CommomParams,
  CoutIntanceName,
  IFetchNode,
  IHost,
  IIpV6Value,
  INode,
  INodeType,
  IpSelectorConfig,
  IpSelectorHostMemuExtend,
  IpSelectorHostTableCustomColumn,
  IpSelectorMode,
  IpSelectorNameStyle,
  IpSelectorService,
  IQuery,
  IScopeItme,
  IStatistics,
  ITemplateHost,
  ITemplateItem,
  ITemplateNode,
  ITreeItem,
} from './typing';

import '@blueking/ip-selector/dist/styles/index.css';

const BkIpSelector = create({
  version: '3',
  serviceConfigError: false,
});
export interface IMonitorIpSelectorEvents {
  onChange: (v: Record<string, INode[]>) => void;
  onCloseDialog: (v: boolean) => void;
  onOutputFieldChange: (v: string[]) => void;
  onTargetTypeChange: (v: INodeType) => void;
}
export interface IMonitorIpSelectorProps {
  countInstanceType?: CoutIntanceName;
  defaultOutputFieldList?: string[];
  enableOriginData?: boolean;
  extractScene?: boolean;
  height?: number;
  hostMemuExtends?: IpSelectorHostMemuExtend[];
  hostTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  hostTableRenderColumnList?: string[];
  keepHostFieldOutput?: boolean;
  mode?: IpSelectorMode;
  nameStyle?: IpSelectorNameStyle;
  nodeTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  originalValue?: IIpV6Value;
  outputFieldList?: string[];
  outputFieldOptionalHostTableColumn?: string[];
  panelList?: string[];
  readonly?: boolean;
  service?: IpSelectorService;
  serviceTemplateTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  setTemplateTableCustomColumnList?: IpSelectorHostTableCustomColumn[];
  showDialog?: boolean;
  showView?: boolean;
  showViewDiff?: boolean;
  singleHostSelect?: boolean;
  unqiuePanelValue?: boolean;
  value?: IIpV6Value;
  viewSearchKey?: string;
  disableDialogSubmitMethod?: () => void;
  disableHostMethod?: () => void;
}

@Component({
  components: {
    BkIpSelector,
  },
})
export default class MonitorIpSelector extends tsc<IMonitorIpSelectorProps, IMonitorIpSelectorEvents> {
  // 需要支持的面板（'staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate',
  // 'serviceInstance', 'manualInput'）
  @Prop({ default: () => ['staticTopo', 'dynamicTopo', 'serviceTemplate', 'setTemplate', 'manualInput'], type: Array })
  panelList: string[];
  @Prop({ default: () => ({}), type: Object }) value: IIpV6Value;
  // 自定义主机列表列
  @Prop({ type: Array }) hostTableCustomColumnList: IpSelectorHostTableCustomColumn[];
  @Prop({ type: Array }) nodeTableCustomColumnList: IpSelectorHostTableCustomColumn[];
  @Prop({ type: Array }) serviceTemplateTableCustomColumnList: IpSelectorHostTableCustomColumn[];
  @Prop({ type: Array }) setTemplateTableCustomColumnList: IpSelectorHostTableCustomColumn[];
  // 自定义menu
  @Prop({ type: Array }) hostMemuExtends: IpSelectorHostMemuExtend[];
  // 主机列表显示列（默认值：['ip', 'ipv6', 'alive', 'osName']），按配置顺序显示列
  // 内置所有列的 key ['ip', 'ipv6', 'cloudArea', 'alive', 'hostName', 'osName', 'coludVerdor', 'osType', 'hostId', 'agentId']
  @Prop({ type: Array }) hostTableRenderColumnList: string[];
  // 编辑状态的初始值，用于和最新选择的值进行对比
  @Prop({ type: Object }) originalValue: IIpV6Value;
  // IP 选择的交互模式
  @Prop({ default: 'section', type: String }) mode: IpSelectorMode;
  // 字段命名风格（'camelCase', 'kebabCase'）
  @Prop({ default: 'camelCase', type: String }) nameStyle: IpSelectorNameStyle;
  // mode 为 dialog 时弹出 dialog
  @Prop({ default: false, type: Boolean }) showDialog: boolean;
  // 面板选项的值是否唯一
  @Prop({ default: true, type: Boolean }) unqiuePanelValue: boolean;
  // IP 选择完成后是否显示结果
  @Prop({ default: false, type: Boolean }) showView: boolean;
  // change 事件回调时输出完整的主机字段
  @Prop({ default: false, type: Boolean }) keepHostFieldOutput: boolean;
  // 是否在选择结果面板显示数据对比
  @Prop({ default: false, type: Boolean }) showViewDiff: boolean;
  // 只读
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  // 静态拓扑主机单选
  @Prop({ default: false, type: Boolean }) singleHostSelect: boolean;
  // Dialog 确定按钮是否禁用
  @Prop({ type: Function }) disableDialogSubmitMethod: () => void;
  // 静态拓扑主机是否禁用
  @Prop({ type: Function }) disableHostMethod: () => void;
  // 在选择结果面板搜索主机
  @Prop({ default: '', type: String }) viewSearchKey: string;
  @Prop({ default: 'host', type: String }) countInstanceType: string;
  // 覆盖组件初始的数据源配置
  @Prop({ type: Object }) service: IpSelectorService;
  // 高度
  @Prop({ type: Number }) height: number;
  // 字段提取场景 拓扑树与节点主机需要通过定制接口获取
  @Prop({ type: Boolean, default: false }) extractScene: boolean;
  // 默认主机输出字段
  @Prop({ type: Array }) defaultOutputFieldList: string[];
  // 蓝鲸监控场景下主机输出备选字段列表 （为空则可选所有主机字段，值为主机 column 的 key）
  @Prop({ type: Array }) outputFieldOptionalHostTableColumn: string[];
  // 配置主机输出字段（如果要开启该功能则值不能为空）
  @Prop({ type: Array }) outputFieldList: string[];
  // 配置 change 事件回调参数是否为原始数据
  @Prop({ type: Boolean, default: false }) enableOriginData;

  scopeList: IScopeItme[] = [
    {
      scope_type: 'biz',
      scope_id: this.$store.getters.bizId,
    },
  ];
  ipSelectorServices: IpSelectorService = {};
  ipSelectorConfig: IpSelectorConfig = {};
  // 初始的数据源缓存(未经 ip 选择器处理的原始数据)
  serverOriginDataMapForChange: any = {};
  created() {
    this.ipSelectorServices = {
      fetchTopologyHostCount: this.fetchTopologyHostCount, // 拉取topology
      fetchTopologyHostsNodes: this.fetchTopologyHostsNodes, // 静态拓扑 - 选中节点

      fetchNodesQueryPath: this.fetchNodesQueryPath, // 动态拓扑 - 勾选节点
      fetchHostAgentStatisticsNodes: this.fetchHostAgentStatisticsNodes, // 动态拓扑 - 勾选节点
      fetchTopologyHostIdsNodes: this.fetchTopologyHostIdsNodes, // 根据多个拓扑节点与搜索条件批量分页查询所包含的主机
      fetchHostsDetails: this.fetchHostsDetails, // 静态 - IP选择回显(host_id查不到时显示失效)
      fetchHostCheck: this.fetchHostCheck, // 手动输入 - 根据用户手动输入的`IP`/`IPv6`/`主机名`/`host_id`等关键字信息获取真实存在的机器信息
      // fetchDynamicGroups: this.fetchDynamicGroup, // 动态分组列表
      // fetchHostsDynamicGroup: this.fetchDynamicGroupHost, // 动态分组下的节点
      // fetchHostAgentStatisticsDynamicGroups: this.fetchBatchGroupAgentStatistics,
      fetchTopologyServiceInstance: this.fetchTopologyServiceInstance, // 拉取服务实例topology
      fetchSeriviceInstanceList: this.fetchSeriviceInstanceList, // 拉取服务实例topology
      fetchSeriviceInstanceDetails: this.fetchSeriviceInstanceDetails, // 拉取服务实例topology
      fetchServiceTemplates: this.fetchServiceTemplates,
      fetchNodesServiceTemplate: this.fetchNodesServiceTemplate,
      fetchHostServiceTemplate: this.fetchHostServiceTemplate,
      fetchHostAgentStatisticsServiceTemplate: this.fetchHostAgentStatisticsServiceTemplate,
      fetchSetTemplates: this.fetchSetTemplates,
      fetchNodesSetTemplate: this.fetchNodesSetTemplate,
      fetchHostSetTemplate: this.fetchHostSetTemplate,
      fetchHostAgentStatisticsSetTemplate: this.fetchHostAgentStatisticsSetTemplate,
      fetchCustomSettings: this.fetchCustomSettings,
      updateCustomSettings: this.updateCustomSettings,
      fetchConfig: this.fetchConfig,
      fetchDynamicGroups: this.fetchDynamicGroups, // 动态分组列表
      fetchHostsDynamicGroup: this.fetchHostsDynamicGroup, // 动态分组下的节点
      fetchHostAgentStatisticsDynamicGroups: this.fetchHostAgentStatisticsDynamicGroups,
      ...this.service,
    };
    this.ipSelectorConfig = {
      // 需要支持的面板（'staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'manualInput'）
      panelList: this.panelList ?? [
        'staticTopo',
        'dynamicTopo',
        // 'dynamicGroup',
        'serviceTemplate',
        'setTemplate',
        'manualInput',
      ],
      // 面板选项的值是否唯一
      unqiuePanelValue: this.unqiuePanelValue,
      // 字段命名风格（'camelCase', 'kebabCase'）
      nameStyle: this.nameStyle,
      // 自定义主机列表列
      hostTableCustomColumnList: this.hostTableCustomColumnList ?? [],
      nodeTableCustomColumnList: this.nodeTableCustomColumnList ?? [],
      serviceTemplateTableCustomColumnList: this.serviceTemplateTableCustomColumnList ?? [],
      setTemplateTableCustomColumnList: this.setTemplateTableCustomColumnList ?? [],
      hostMemuExtends: this.hostMemuExtends ?? [],
      // 主机列表显示列（默认值：['ip', 'ipv6', 'alive', 'osName']），按配置顺序显示列
      // 内置所有列的 key ['ip', 'ipv6', 'cloudArea', 'alive', 'hostName',
      //  'osName', 'coludVerdor', 'osType', 'hostId', 'agentId']
      hostTableRenderColumnList: this.hostTableRenderColumnList ?? [],
      hostViewFieldRender: this.hostViewFieldRender,
      serviceConfigError: true,
    };
  }
  // 动态分组api
  async fetchDynamicGroups(p) {
    const data = await groupsIpChooserDynamicGroup(
      this.transformParams({
        scope_list: this.scopeList,
        ...p,
      })
    );
    const nodeType = 'DYNAMIC_GROUP';
    this.serverOriginDataMapForChange[nodeType] = transformOriginDataToCacheMap(data, nodeType);
    return data;
  }
  async fetchHostsDynamicGroup(p) {
    const data = await executeIpChooserDynamicGroup(
      this.transformParams({
        scope_list: this.scopeList,
        ...p,
      })
    );
    return data;
  }
  async fetchHostAgentStatisticsDynamicGroups(p) {
    const data = await agentStatisticsIpChooserDynamicGroup(
      this.transformParams({
        scope_list: this.scopeList,
        ...p,
      })
    );
    return data;
  }

  // 拉取topology
  async fetchTopologyHostCount(): Promise<ITreeItem[]> {
    return await treesIpChooserTopo(this.transformParams({ scope_list: this.scopeList })).catch(() => []);
  }
  // 选中节点(根据多个拓扑节点与搜索条件批量分页查询所包含的主机信息)
  async fetchTopologyHostsNodes(params: IQuery) {
    const { search_content, ...p } = params;
    const data = {
      scope_list: this.scopeList,
      ...(search_content ? params : p),
    };
    return await queryHostsIpChooserTopo(data).catch(() => []);
  }

  async fetchTopologyHostIdsNodes(params: IQuery) {
    const { search_content, ...p } = params;
    const data = {
      scope_list: this.scopeList,
      ...(search_content ? params : p),
    };
    return await queryHostIdInfosIpChooserTopo(data).then(list => {
      return {
        ...list,
        data:
          list?.data?.map(item => {
            return {
              cloud_area: {
                id: item.cloud_id,
              },
              ...item,
            };
          }) || [],
      };
    });
  }

  // 动态拓扑 - 勾选节点(查询多个节点拓扑路径)
  async fetchNodesQueryPath(node: IFetchNode): Promise<Array<INode>[]> {
    return await queryPathIpChooserTopo(
      this.transformParams({
        scope_list: this.scopeList,
        ...node,
      })
    ).catch(() => []);
  }
  // 动态拓扑 - 勾选节点(获取多个拓扑节点的主机 Agent 状态统计信息)
  async fetchHostAgentStatisticsNodes(node: IFetchNode): Promise<{ agent_statistics: IStatistics; node: INode }[]> {
    return await agentStatisticsIpChooserTopo({
      scope_list: this.scopeList,
      ...node,
    }).catch(() => []);
  }
  async fetchHostsDetails(node) {
    return await detailsIpChooserHost({
      scope_list: this.scopeList,
      ...node,
    }).catch(() => []);
  }
  // 手动输入
  async fetchHostCheck(node: IFetchNode) {
    return await checkIpChooserHost({
      scope_list: this.scopeList,
      ...node,
    }).catch(() => []);
  }
  // // 获取动态分组列表
  // async fetchDynamicGroup(): Promise<Array<IGroupItem>[]> {
  //   const res = await $http.request('ipChooser/dynamicGroups', { data: { scope_list: this.scopeList } });
  //   return res?.data || [];
  // }
  // // 获取动态分组下的主机列表
  // async fetchDynamicGroupHost(query: IGroupHostQuery): Promise<Array<IGroupHost>[]> {
  //   const data = {
  //     scope_list: this.scopeList,
  //     ...query
  //   };
  //   const res = await $http.request('ipChooser/executeDynamicGroup', { data });
  //   return res?.data || [];
  // }
  // 获取多个动态分组下的主机Agent状态统计信息
  // async fetchBatchGroupAgentStatistics(node: IFetchNode): Promise<{
  //   agentStatistics: IStatistics,
  //   dynamicGroup: IGroupItem
  // }[]> {
  //   const data = {
  //     scope_list: this.scopeList,
  //     ...node
  //   };
  //   const res = await $http.request('ipChooser/groupAgentStatistics', { data });
  //   return res?.data || [];
  // }
  // 获取服务模板列表
  async fetchServiceTemplates(params: Record<string, any>): Promise<Array<ITemplateItem>[]> {
    return await templatesIpChooserTemplate(
      this.transformParams({
        scope_list: this.scopeList,
        template_type: 'SERVICE_TEMPLATE',
        ...params,
      })
    ).catch(() => []);
  }
  // 获取服务模板下各个节点
  async fetchNodesServiceTemplate(query: IQuery): Promise<Array<ITemplateNode>[]> {
    return await nodesIpChooserTemplate(
      this.transformParams({
        scope_list: this.scopeList,
        template_type: 'SERVICE_TEMPLATE',
        ...query,
      })
    ).catch(() => []);
  }
  // 获取服务模板下各个主机
  async fetchHostServiceTemplate(query: IQuery): Promise<Array<ITemplateHost>[]> {
    return await hostsIpChooserTemplate({
      scope_list: this.scopeList,
      template_type: 'SERVICE_TEMPLATE',
      template_id: query.id,
      ...query,
    }).catch(() => []);
  }
  // 获取服务模板Agent统计状态
  async fetchHostAgentStatisticsServiceTemplate(query: CommomParams) {
    const params = {
      scope_list: this.scopeList,
      template_type: 'SERVICE_TEMPLATE',
      ...query,
    };
    if (this.countInstanceType === 'service_instance') {
      return await serviceInstanceCountIpChooserTemplate(params)
        .then(data =>
          data.map(item => ({
            ...item,
            host_count: item.count,
            node_count: item.node_count || 0,
            agent_statistics: {
              total_count: item.count,
            },
            service_template: query.service_template_list[0],
          }))
        )
        .catch(() => []);
    }
    return await agentStatisticsIpChooserTemplate(params).catch(() => []);
  }
  // 获取集群模板列表
  async fetchSetTemplates(query: IQuery): Promise<Array<ITemplateItem>[]> {
    return await templatesIpChooserTemplate(
      this.transformParams({
        scope_list: this.scopeList,
        template_type: 'SET_TEMPLATE',
        ...query,
      })
    ).catch(() => []);
  }
  // 获取集群模板下各个节点
  async fetchNodesSetTemplate(query: IQuery): Promise<Array<ITemplateNode>[]> {
    return await nodesIpChooserTemplate(
      this.transformParams({
        scope_list: this.scopeList,
        template_type: 'SET_TEMPLATE',
        ...query,
      })
    ).catch(() => []);
  }
  // 获取集群模板下各个主机
  async fetchHostSetTemplate(query: IQuery): Promise<Array<ITemplateHost>[]> {
    return await hostsIpChooserTemplate({
      scope_list: this.scopeList,
      template_type: 'SET_TEMPLATE',
      template_id: query.id,
      ...query,
    }).catch(() => []);
  }
  // 获取集群模板Agent统计状态
  async fetchHostAgentStatisticsSetTemplate(query: CommomParams) {
    const params = {
      scope_list: this.scopeList,
      template_type: 'SET_TEMPLATE',
      ...query,
    };
    if (this.countInstanceType === 'service_instance') {
      return await serviceInstanceCountIpChooserTemplate(params)
        .then(data =>
          data.map(item => ({
            ...item,
            host_count: item.count,
            node_count: item.node_count || 0,
            agent_statistics: {
              total_count: item.count,
            },
            set_template: query.set_template_list[0],
          }))
        )
        .catch(() => []);
    }
    return await agentStatisticsIpChooserTemplate(params).catch(() => []);
  }
  async fetchCustomSettings(params: CommomParams) {
    return await batchGetIpChooserConfig(params).catch(() => ({}));
  }
  async updateCustomSettings(params: CommomParams) {
    return await updateConfigIpChooserConfig(params).catch(() => ({}));
  }
  async fetchConfig() {
    const { CC_ROOT_URL } = await globalConfigIpChooserConfig().catch(() => ({}));
    const { bizId } = this.$store.getters;
    return {
      // CMDB 动态分组链接
      bk_cmdb_dynamic_group_url: `${CC_ROOT_URL}/#/business/${bizId}/custom-query`,
      // CMDB 拓扑节点链接
      bk_cmdb_static_topo_url: `${CC_ROOT_URL}/#/business/${bizId}/index`,
      // CMDB 服务模板链接
      bk_cmdb_service_template_url: `${CC_ROOT_URL}/#/business/${bizId}/service/template`,
      // CMDB 集群模板链接
      bk_cmdb_set_template_url: `${CC_ROOT_URL}/#/business/${bizId}/set/template`,
    };
  }
  // 获取服务实例左侧树topo数据
  async fetchTopologyServiceInstance(): Promise<ITreeItem[]> {
    return await treesIpChooserTopo({
      scope_list: this.scopeList,
      count_instance_type: 'service_instance',
    }).catch(() => []);
  }
  // 获取服务实例列表
  async fetchSeriviceInstanceList(params: CommomParams): Promise<ITreeItem[]> {
    return await queryServiceInstancesIpChooserTopo({
      scope_list: this.scopeList,
      ...params,
    }).catch(() => []);
  }
  // 获取服务实例详情
  async fetchSeriviceInstanceDetails(params: CommomParams): Promise<ITreeItem[]> {
    return await detailsIpChooserServiceInstance({
      scope_list: this.scopeList,
      ...params,
    }).catch(() => []);
  }
  transformParams(params: Record<string, any>) {
    if (this.countInstanceType === 'service_instance') {
      return {
        ...params,
        count_instance_type: this.countInstanceType,
      };
    }
    return params;
  }
  @Emit('change')
  change(value: Record<string, INode[]>) {
    if (!this.enableOriginData) {
      return value;
    }
    return Object.fromEntries(
      Object.entries(value).map(([key, value]) => [
        key,
        // @ts-ignore
        transformCacheMapToOriginData(value, key, this.serverOriginDataMapForChange),
      ])
    );
  }
  @Emit('targetTypeChange')
  panelChange(v: string) {
    return PanelTargetMap[v] || 'TOPO';
  }
  @Emit('closeDialog')
  closeDialog() {
    return false;
  }
  @Emit('outputFieldChange')
  outPutFieldChange(v: string[]) {
    return v;
  }
  hostViewFieldRender(host: IHost, primaryField: string) {
    return host[primaryField] ? undefined : host.display_name || host.ip;
  }
  render() {
    return (
      <BkIpSelector
        config={this.ipSelectorConfig}
        defaultOutputFieldList={this.defaultOutputFieldList}
        disableDialogSubmitMethod={this.disableDialogSubmitMethod}
        disableHostMethod={this.disableHostMethod}
        keepHostFieldOutput={this.keepHostFieldOutput}
        mode={this.mode}
        originalValue={this.originalValue}
        outputFieldList={this.outputFieldList}
        outputFieldOptionalHostTableColumn={this.outputFieldOptionalHostTableColumn}
        readonly={this.readonly}
        service={this.ipSelectorServices}
        showDialog={this.showDialog}
        showView={this.showView}
        showViewDiff={this.showViewDiff}
        singleHostSelect={this.singleHostSelect}
        value={this.value}
        viewSearchKey={this.viewSearchKey}
        on-change={this.change}
        on-close-dialog={this.closeDialog}
        on-output-field-change={this.outPutFieldChange}
        on-panel-change={this.panelChange}
      />
    );
  }
}
