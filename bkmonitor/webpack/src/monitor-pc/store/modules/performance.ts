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
import { getTopoTree } from 'monitor-api/modules/commons';
import { createUserConfig, listUserConfig, partialUpdateUserConfig } from 'monitor-api/modules/model';
import {
  hostPerformance,
  hostPerformanceDetail,
  hostTopoNodeDetail,
  searchHostInfo,
  searchHostMetric,
} from 'monitor-api/modules/performance';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

// import { savePanelOrder, deletePanelOrder } from 'monitor-api/modules/data_explorer';
import store from '../store';

export interface ICurNode {
  bkInstId?: number | string;
  bkObjId?: string;
  cloudId?: number | string;
  id: string; // ip + cloudId 或者 bkInstId + bkObjId
  ip?: string;
  osType?: number;
  processId?: number | string;
  type: 'host' | 'node'; // host类型时：IP、bkCloudId不为空；node类型时：bkInstId、bkObjId不为空
}
interface IConditionValue {
  condition: '<' | '<=' | '=' | '>' | '>=';
  value: number;
}

interface IHostData {
  hosts: any[];
}

interface ISearchItem {
  id: string;
  value: (number | string)[] | IConditionValue[] | number | string;
}
interface IUpdateConfig {
  id: number;
  value: string;
}

interface IUserConfig {
  id?: number;
  key: string;
  username?: string;
  value: string;
}
// todo 老代码
export const SET_PERFORMANCE_HOST = 'SET_PERFORMANCE_HOST';
export const SET_PERFORMANCE_ROW = 'SET_PERFORMANCE_ROW';
export const SET_PERFORMANCE_PROCESS = 'SET_PERFORMANCE_PROCESS';
export const SET_PERFORMANCE_VIEWTYPE = 'SET_PERFORMANCE_VIEWTYPE';
export const SET_URL_QUERY = 'SET_URL_QUERY';

@Module({ name: 'performance', dynamic: true, namespaced: true, store })
class Performance extends VuexModule {
  // 列表条件
  public conditions: ISearchItem[] = [];
  // 当前节点信息
  public curNode: ICurNode = { id: '', type: 'host' };
  // 主机仪表盘配置列表
  public hostConfigList = [];
  // 主机仪表盘配置排序列表
  public hostOrderList = [];
  // 主机列表
  public hosts: Readonly<any[]> = [];

  // 主机拓扑树数据
  public hostToppTreeData = [];
  // todo 老代码
  public list: any[] = [];

  public proc = '';
  // 进程仪表盘视图配置列表
  public processConfigList = [];
  // 主机进程列表
  public processList = [];
  // 进程仪表盘配置排序列表
  public processOrderList = [];
  public rows: any = null;
  public storeFilterList: Readonly<any[]> = [];

  public storeKeyword = '';
  public type = 'performance';

  // 当前主机状态信息
  public get curHostStatus() {
    return this.hosts.find(item => item.bk_host_innerip === this.curNode.ip) || {};
  }

  public get curProcess() {
    return this.curNode?.processId;
  }
  public get curProcessList() {
    return this.processList || [];
  }

  public get dashboardConfigList() {
    return this.hostConfigList;
  }

  public get dashboardHostOrderList() {
    return this.hostOrderList;
  }
  public get dashboardProcessOrderList() {
    return this.processOrderList;
  }

  // 筛选主机列表
  public get filterHostList() {
    return this.storeFilterList;
  }
  // 拓扑树
  public get filterHostTopoTreeList() {
    return this.hostToppTreeData;
  }

  public get hostList() {
    return this.list;
  }

  // 搜索keyword
  public get keyword() {
    return this.storeKeyword;
  }

  public get process() {
    return this.proc;
  }

  public get processDashboardConfigList() {
    return this.processConfigList;
  }
  public get row() {
    return this.rows;
  }
  public get targetList() {
    return this.list.map(item => ({ id: `${item.bk_cloud_id}-${item.bk_host_innerip}`, name: item.bk_host_innerip }));
  }

  // 获取URL参数
  public get urlQuery() {
    return this.conditions.length ? `?search=${JSON.stringify(this.conditions)}` : '';
  }
  public get viewType() {
    return this.type;
  }

  // 创建用户置顶配置
  @Action
  public async createUserConfig(params: IUserConfig) {
    const result = await createUserConfig(params).catch(() => ({}));
    return result;
  }

  // 获取主机详情
  @Action
  public async getHostDetail(params) {
    const data = await hostPerformanceDetail(params).catch(() => ({}));
    return data;
  }

  // 获取主机列表信息
  @Action
  public async getHostPerformance(): Promise<any[]> {
    const hosts: any[] = await searchHostInfo().catch(() => []);
    if (this.curNode.cloudId === -1) {
      this.setCurNode({
        ...this.curNode,
        cloudId: (hosts.find((item: any) => item.bk_host_innerip === this.curNode.ip) || { bk_cloud_id: -1 })
          .bk_cloud_id,
      });
    }
    // 大数据排序有性能问题
    // this.setHostList(data.hosts.sort((a: any, b: any) => {
    //   const ip1 = a.bk_host_innerip.split('.').map(el => el.padStart(3, '0'))
    //     .join('')
    //   const ip2 = b.bk_host_innerip.split('.').map(el => el.padStart(3, '0'))
    //     .join('')
    //   return ip1 - ip2
    // }))
    this.setHostList(hosts);
    this.setKeyWord(this.storeKeyword);
    return hosts;
  }

  // 带有指标的全量主机信息
  @Action
  public async getHostPerformanceMetric(): Promise<IHostData> {
    const data: IHostData = await hostPerformance().catch(() => ({
      hosts: [],
      update_time: '',
    }));
    return data;
  }

  // 获取节点详情
  @Action
  public async getNodeDetail(params) {
    const data = await hostTopoNodeDetail(params).catch(() => ({}));
    return data;
  }

  // 获取主机拓扑树列表
  @Action
  public async getTopoTree(
    params = {
      instance_type: 'host',
      remove_empty_nodes: true,
    }
  ) {
    const data = await getTopoTree(params).catch(() => []);
    this.setTopoTreeList(data);
    return data;
  }

  // 获取用户置顶配置
  @Action
  public async getUserConfigList(params): Promise<IUserConfig[]> {
    const data = await listUserConfig(params).catch(() => []);
    return data;
  }

  @Action
  public async searchHostMetric(params: any) {
    const hostsMap = await searchHostMetric(params).catch(() => []);
    return hostsMap;
  }
  @Mutation
  public [SET_PERFORMANCE_HOST](hostList = []) {
    this.list = hostList;
  }

  @Mutation
  public [SET_PERFORMANCE_PROCESS](process = '') {
    this.proc = process;
  }
  @Mutation
  public [SET_PERFORMANCE_ROW](row) {
    this.rows = row;
  }

  @Mutation
  public [SET_PERFORMANCE_VIEWTYPE](viewType = 'performance') {
    this.type = viewType;
  }

  @Mutation
  public setConditions(data = []) {
    this.conditions = data;
  }

  @Mutation
  public setCurNode(data: ICurNode) {
    this.curNode = data;
  }

  // 设置主机仪表盘配置列表
  @Mutation
  public setHostConfigList(data) {
    this.hostConfigList = data;
  }

  // 主机列表数据
  @Mutation
  public setHostList(data: any[] = []) {
    this.hosts = Object.freeze(data);
  }

  @Mutation
  public setHostOrderList(data) {
    this.hostOrderList = data;
  }
  @Mutation
  public setKeyWord(keyword: string) {
    this.storeKeyword = keyword;
    this.storeFilterList = keyword
      ? this.hosts.filter(item =>
          [
            'bk_host_innerip',
            'bk_host_outerip',
            'k_host_name',
            'bk_os_name',
            'bk_biz_name',
            'bk_cluster',
            'module',
            'component',
          ].some(key => {
            let hostProp = item[key] || '';
            if (typeof hostProp === 'string') {
              return hostProp.includes(keyword);
            }
            if (key === 'module' || key === 'bk_cluster') {
              hostProp = item.module;
              return hostProp.some(set => set.topo_link_display.some(child => child.includes(keyword)));
            }
            return hostProp.some(set => set.display_name.includes(keyword));
          })
        )
      : this.hosts;
  }
  // 设置进程仪表盘配置列表
  @Mutation
  public setProcessConfigList(data) {
    this.processConfigList = data;
  }

  // 设置主机进程缓存
  @Mutation
  public setProcessId(processId: number | string) {
    this.curNode = {
      ...this.curNode,
      processId,
    };
  }

  // 设置主机进程缓存
  @Mutation
  public setProcessList(data) {
    this.processList = data;
  }

  @Mutation
  public setProcessOrderList(data) {
    this.processOrderList = data;
  }

  // @Action
  // public async getHostDashboardConfig(params) {
  //   const { data, tips } =      this.curNode.type === 'host'
  //     ? await getHostDashboardConfig(params, { needRes: true }).catch(() => ({ data: { panels: [], order: [] } }))
  //     : await getTopoNodeDashboardConfig(params, { needRes: true }).catch(() => ({
  //       data: { panels: [], order: [] }
  //     }));
  //   if (tips?.length) {
  //     Vue.prototype.$bkMessage({
  //       theme: 'warning',
  //       message: tips
  //     });
  //   }
  //   if (params.type === 'host') {
  //     this.setHostConfigList(data.panels);
  //     this.setHostOrderList(data.order);
  //   } else if (params.type === 'process') {
  //     this.setProcessConfigList(data.panels);
  //     this.setProcessOrderList(data.order);
  //   }
  // }

  @Mutation
  public setTopoTreeList(treeData: any) {
    this.hostToppTreeData = treeData;
  }

  // 更新用户置顶配置
  @Action
  public async updateUserConfig(params: IUpdateConfig) {
    const result = await partialUpdateUserConfig(params.id, { value: params.value })
      .then(() => true)
      .catch(() => false);
    return result;
  }
}

export default getModule(Performance);
