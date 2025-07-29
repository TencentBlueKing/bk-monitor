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

import { computed, defineComponent } from 'vue';

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

import { useAppStore } from '../../store/modules/app';
import {
  type CommomParams,
  type IFetchNode,
  type IHost,
  type INode,
  type IQuery,
  type IScopeItme,
  type IStatistics,
  type ITemplateHost,
  type ITemplateItem,
  type ITemplateNode,
  type ITreeItem,
  componentProps,
} from './typing';
import create from './vue3.x';

import './monitor-ip-selector.scss';
import '@blueking/ip-selector/dist/styles/vue2.6.x.css';
const BkIpSelector: any = create({
  version: '4',
  serviceConfigError: false,
});

export default defineComponent({
  name: 'MonitorIpSelector',
  props: componentProps,
  setup(props) {
    const store = useAppStore();
    const scopeList: IScopeItme[] = [
      {
        scope_type: 'biz',
        scope_id: store.bizId as string,
      },
    ];
    const ipSelectorServices = {
      fetchTopologyHostCount, // 拉取topology
      fetchTopologyHostsNodes, // 静态拓扑 - 选中节点

      fetchNodesQueryPath, // 动态拓扑 - 勾选节点
      fetchHostAgentStatisticsNodes, // 动态拓扑 - 勾选节点
      fetchTopologyHostIdsNodes, // 根据多个拓扑节点与搜索条件批量分页查询所包含的主机
      fetchHostsDetails, // 静态 - IP选择回显(host_id查不到时显示失效)
      fetchHostCheck, // 手动输入 - 根据用户手动输入的`IP`/`IPv6`/`主机名`/`host_id`等关键字信息获取真实存在的机器信息
      // fetchDynamicGroups: this.fetchDynamicGroup, // 动态分组列表
      // fetchHostsDynamicGroup: this.fetchDynamicGroupHost, // 动态分组下的节点
      // fetchHostAgentStatisticsDynamicGroups: this.fetchBatchGroupAgentStatistics,
      fetchTopologyServiceInstance, // 拉取服务实例topology
      fetchSeriviceInstanceList, // 拉取服务实例topology
      fetchSeriviceInstanceDetails, // 拉取服务实例topology
      fetchServiceTemplates,
      fetchNodesServiceTemplate,
      fetchHostServiceTemplate,
      fetchHostAgentStatisticsServiceTemplate,
      fetchSetTemplates,
      fetchNodesSetTemplate,
      fetchHostSetTemplate,
      fetchHostAgentStatisticsSetTemplate,
      fetchCustomSettings,
      updateCustomSettings,
      fetchConfig,
      fetchDynamicGroups, // 动态分组列表
      fetchHostsDynamicGroup, // 动态分组下的节点
      fetchHostAgentStatisticsDynamicGroups,
      ...props.service,
    };
    const ipSelectorConfig = computed(() => ({
      // 需要支持的面板（'staticTopo', 'dynamicTopo', 'dynamicGroup', 'serviceTemplate', 'setTemplate', 'manualInput'）
      panelList: props.panelList ?? [
        'staticTopo',
        'dynamicTopo',
        // 'dynamicGroup',
        'serviceTemplate',
        'setTemplate',
        'manualInput',
      ],
      // 面板选项的值是否唯一
      unqiuePanelValue: props.unqiuePanelValue,
      // 字段命名风格（'camelCase', 'kebabCase'）
      nameStyle: props.nameStyle,
      // 自定义主机列表列
      hostTableCustomColumnList: props.hostTableCustomColumnList ?? [],
      nodeTableCustomColumnList: props.nodeTableCustomColumnList ?? [],
      serviceTemplateTableCustomColumnList: props.serviceTemplateTableCustomColumnList ?? [],
      setTemplateTableCustomColumnList: props.setTemplateTableCustomColumnList ?? [],
      hostMemuExtends: props.hostMemuExtends ?? [],
      // 主机列表显示列（默认值：['ip', 'ipv6', 'alive', 'osName']），按配置顺序显示列
      // 内置所有列的 key ['ip', 'ipv6', 'cloudArea', 'alive', 'hostName',
      //  'osName', 'coludVerdor', 'osType', 'hostId', 'agentId']
      hostTableRenderColumnList: props.hostTableRenderColumnList ?? [],
      hostViewFieldRender,
      serviceConfigError: true,
    }));

    // 动态分组api
    async function fetchDynamicGroups(p) {
      const data = await groupsIpChooserDynamicGroup(
        transformParams({
          scope_list: scopeList,
          ...p,
        })
      );
      return data;
    }
    async function fetchHostsDynamicGroup(p) {
      const data = await executeIpChooserDynamicGroup(
        transformParams({
          scope_list: scopeList,
          ...p,
        })
      );
      return data;
    }
    async function fetchHostAgentStatisticsDynamicGroups(p) {
      const data = await agentStatisticsIpChooserDynamicGroup(
        transformParams({
          scope_list: scopeList,
          ...p,
        })
      );
      return data;
    }
    /**
     * @description 拉取topology
     * @returns
     */
    async function fetchTopologyHostCount() {
      return await treesIpChooserTopo(transformParams({ scope_list: scopeList })).catch(() => []);
    }
    async function fetchTopologyHostsNodes(params: IQuery) {
      const { search_content, ...p } = params;
      const data = {
        scope_list: scopeList,
        ...(search_content ? params : p),
      };
      return await queryHostsIpChooserTopo(data).catch(() => []);
    }
    /**
     * @description 动态拓扑 - 勾选节点(查询多个节点拓扑路径)
     * @param node
     * @returns
     */
    async function fetchNodesQueryPath(node: IFetchNode): Promise<Array<INode>[]> {
      return await queryPathIpChooserTopo({
        scope_list: scopeList,
        ...node,
      }).catch(() => []);
    }
    /**
     * @description 动态拓扑 - 勾选节点(获取多个拓扑节点的主机 Agent 状态统计信息)
     * @param node
     * @returns
     */
    async function fetchHostAgentStatisticsNodes(
      node: IFetchNode
    ): Promise<{ agent_statistics: IStatistics; node: INode }[]> {
      return await agentStatisticsIpChooserTopo({
        scope_list: scopeList,
        ...node,
      }).catch(() => []);
    }
    /**
     * 获取拓扑图中主机的ID和节点信息
     * @param params - 查询参数对象
     * @returns 主机ID和节点信息的数组
     */
    async function fetchTopologyHostIdsNodes(params: IQuery) {
      const { search_content, ...p } = params;
      const data = {
        scope_list: scopeList,
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
    /**
     * @description 用于获取主机的详细信息
     * @param node
     * @returns
     */
    async function fetchHostsDetails(node) {
      return await detailsIpChooserHost({
        scope_list: scopeList,
        ...node,
      }).catch(() => []);
    }
    /**
     * @description 手动输入
     * @param node
     * @returns
     */
    async function fetchHostCheck(node: IFetchNode) {
      return await checkIpChooserHost({
        scope_list: scopeList,
        ...node,
      }).catch(() => []);
    }
    /**
     * @description 获取服务实例左侧树topo数据
     * @returns
     */
    async function fetchTopologyServiceInstance(): Promise<ITreeItem[]> {
      return await treesIpChooserTopo({
        scope_list: scopeList,
        count_instance_type: 'service_instance',
      }).catch(() => []);
    }
    /**
     * @description 获取服务实例列表
     * @param params
     * @returns
     */
    async function fetchSeriviceInstanceList(params: CommomParams): Promise<ITreeItem[]> {
      return await queryServiceInstancesIpChooserTopo({
        scope_list: scopeList,
        ...params,
      }).catch(() => []);
    }
    /**
     * @description 获取服务实例详情
     * @param params
     * @returns
     */
    async function fetchSeriviceInstanceDetails(params: CommomParams): Promise<ITreeItem[]> {
      return await detailsIpChooserServiceInstance({
        scope_list: scopeList,
        ...params,
      }).catch(() => []);
    }
    /**
     * @description 获取服务模板列表
     * @param params
     * @returns
     */
    async function fetchServiceTemplates(params: Record<string, any>): Promise<Array<ITemplateItem>[]> {
      return await templatesIpChooserTemplate(
        transformParams({
          scope_list: scopeList,
          template_type: 'SERVICE_TEMPLATE',
          ...params,
        })
      ).catch(() => []);
    }
    /**
     * @description 获取服务模板下各个节点
     * @param query
     * @returns
     */
    async function fetchNodesServiceTemplate(query: IQuery): Promise<Array<ITemplateNode>[]> {
      return await nodesIpChooserTemplate({
        scope_list: scopeList,
        template_type: 'SERVICE_TEMPLATE',
        ...query,
      }).catch(() => []);
    }
    /**
     * @description 获取服务模板下各个主机
     * @param query
     * @returns
     */
    async function fetchHostServiceTemplate(query: IQuery): Promise<Array<ITemplateHost>[]> {
      return await hostsIpChooserTemplate({
        scope_list: scopeList,
        template_type: 'SERVICE_TEMPLATE',
        template_id: query.id,
        ...query,
      }).catch(() => []);
    }
    // 获取服务模板Agent统计状态
    async function fetchHostAgentStatisticsServiceTemplate(query: CommomParams) {
      const params = {
        scope_list: scopeList,
        template_type: 'SERVICE_TEMPLATE',
        ...query,
      };
      if (props.countInstanceType === 'service_instance') {
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
    /**
     * @description 获取集群模板列表
     * @param query
     * @returns
     */
    async function fetchSetTemplates(query: IQuery): Promise<Array<ITemplateItem>[]> {
      return await templatesIpChooserTemplate(
        transformParams({
          scope_list: scopeList,
          template_type: 'SET_TEMPLATE',
          ...query,
        })
      ).catch(() => []);
    }
    /**
     * @description 获取集群模板下各个节点
     * @param query
     * @returns
     */
    async function fetchNodesSetTemplate(query: IQuery): Promise<Array<ITemplateNode>[]> {
      return await nodesIpChooserTemplate({
        scope_list: scopeList,
        template_type: 'SET_TEMPLATE',
        ...query,
      }).catch(() => []);
    }
    /**
     * @description 获取集群模板下各个主机
     * @param query
     * @returns
     */
    async function fetchHostSetTemplate(query: IQuery): Promise<Array<ITemplateHost>[]> {
      return await hostsIpChooserTemplate({
        scope_list: scopeList,
        template_type: 'SET_TEMPLATE',
        template_id: query.id,
        ...query,
      }).catch(() => []);
    }
    /**
     * @description 获取集群模板Agent统计状态
     * @param query
     * @returns
     */
    async function fetchHostAgentStatisticsSetTemplate(query: CommomParams) {
      const params = {
        scope_list: scopeList,
        template_type: 'SET_TEMPLATE',
        ...query,
      };
      if (props.countInstanceType === 'service_instance') {
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
    /**
     * @description 自定义设置
     * @param params
     * @returns
     */
    async function fetchCustomSettings(params: CommomParams) {
      return await batchGetIpChooserConfig(params).catch(() => ({}));
    }
    /**
     * @description 更新自定义设置
     * @param params
     * @returns
     */
    async function updateCustomSettings(params: CommomParams) {
      return await updateConfigIpChooserConfig(params).catch(() => ({}));
    }
    async function fetchConfig() {
      const { CC_ROOT_URL } = await globalConfigIpChooserConfig().catch(() => ({}));
      const { bizId } = store;
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
    function hostViewFieldRender(host: IHost, primaryField: string) {
      return host[primaryField] ? undefined : host.display_name || host.ip;
    }
    /**
     * 将参数进行转换处理
     * @param params - 需要转换的参数对象
     * @returns 转换后的参数对象
     */
    function transformParams(params: Record<string, any>) {
      if (props.countInstanceType === 'service_instance') {
        return {
          ...params,
          count_instance_type: props.countInstanceType,
        };
      }
      return params;
    }
    return {
      ipSelectorServices,
      ipSelectorConfig,
      scopeList,
    };
  },
  render() {
    return (
      <BkIpSelector
        class='monitor-ip-selector'
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
        onChange={this.onChange}
        onCloseDialog={this.onCloseDialog}
        // onOutputField-change={this.onOutPutFieldChange}
        // onPanelChange={this.onPanelChange}
      />
    );
  },
});
