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
import Vue from 'vue';

import { getLabel, getMainlineObjectTopo } from 'monitor-api/modules/commons';
import { getGraphQueryConfig } from 'monitor-api/modules/data_explorer';
import { createQueryHistory, destroyQueryHistory, listQueryHistory } from 'monitor-api/modules/model';
import { deepClone, random, transformDataKey } from 'monitor-common/utils/utils';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import { handleTimeRange } from '../../utils/index';
import store from '../store';

import type {
  IAggMethodList,
  IGetQueryConfigParams,
  IHistoryListItem,
  IQueryConfigsItem,
} from '../../pages/data-retrieval/index';

@Module({ name: 'data-retrieval', dynamic: true, namespaced: true, store })
class DataRetrieval extends VuexModule {
  // curTab
  public curTab = 'data-query-conditions';
  // 监控指标默认计算公式
  public defaultMethodList: IAggMethodList[] = [
    {
      id: 'SUM',
      name: 'SUM',
    },
    {
      id: 'AVG',
      name: 'AVG',
    },
    {
      id: 'MAX',
      name: 'MAX',
    },
    {
      id: 'MIN',
      name: 'MIN',
    },
    {
      id: 'COUNT',
      name: 'COUNT',
    },
  ];
  // 历史数据
  public historyList: IHistoryListItem[] = [];

  // 缓存上一次操作的监控对象
  public labelCache = 'service_module';

  // 监控对象列表
  public labelList: any = [];

  // 页面loading
  public loading = false;

  // 监控目标名字数据
  public mainlineObjectTopo: any = [];

  // 全屏loading promise list
  public promiseListFullPage: Promise<any>[] = [];

  // 校验promise list
  public promiseListValidator: Promise<any>[] = [];

  // 配置查询结果
  public queryConfigsResult: any = {};

  // 查询所需的数据
  public queryData: IGetQueryConfigParams = {
    bkBizId: store.getters.bizId,
    queryConfigs: [],
    compareConfig: { type: 'none', split: true },
    target: [],
    targetType: 'INSTANCE',
    tools: {
      timeRange: 1 * 60 * 60 * 1000,
      refreshInterval: -1,
    },
    startTime: 0,
    endTime: 0,
  };

  // 查询耗时
  queryTime = 0;

  // 指标数据选项
  public timeSeriesMetricMap: any = {};

  public get curTabGetter() {
    return this.curTab;
  }

  public get defaultMethodListGetter() {
    return this.defaultMethodList;
  }

  public get historyListData() {
    return this.historyList;
  }

  public get labelListGetter() {
    return this.labelList;
  }

  public get mainlineObjectTopoGetter() {
    return this.mainlineObjectTopo;
  }

  public get queryConfigs() {
    return this.queryConfigsResult;
  }

  public get queryDataGetter() {
    return this.queryData;
  }

  public get queryTimeGetter() {
    return this.queryTime;
  }

  public get refreshInterval() {
    return this.queryData.tools.refreshInterval;
  }

  public get timeSeriesMetric() {
    return this.timeSeriesMetricMap;
  }

  public get validatorPromiseList() {
    return this.promiseListValidator;
  }

  // 将promise添加进promiseListFullPage队列
  @Mutation
  public addPromiseListFullPage(p: Promise<any>) {
    this.promiseListFullPage.push(p);
  }

  // 查询队列校验队列
  @Mutation
  public addPromiseListValidator(p: Promise<any>) {
    this.promiseListValidator.push(p);
  }

  // 保存查询按钮
  @Mutation
  public addQueryHistory() {
    this.historyList.unshift({
      bkBizId: store.getters.bizId,
      name: '',
      config: deepClone(this.queryData),
    });
    this.curTab = 'data-query-history';
  }

  // 清理promise list
  @Mutation
  public clearPromiseListFullPage() {
    this.promiseListFullPage = [];
    // this.loading = false
  }

  // 清理promise list
  @Mutation
  public clearPromiseListValidator() {
    this.promiseListValidator = [];
  }

  // 清理历史缓存
  @Mutation
  public clearQueryHistoryCache() {
    this.historyList = this.historyList.filter(item => item.name);
  }

  // 清空指标信息
  @Mutation
  public clearQueryItem(index) {
    const item = this.queryData.queryConfigs[index];
    item.label = this.labelCache;
    item.metricField = '';
    item.method = 'AVG';
    item.interval = 60;
    item.resultTableId = '';
    item.dataSourceLabel = '';
    item.dataTypeLabel = '';
    item.groupBy = null;
    item.where = null;
  }

  // 删除查询历史
  @Action
  public async deleteQueryHistory(index: number) {
    const { id } = this.historyList[index];
    const data = await destroyQueryHistory(id).catch(() => []);
    const value = deepClone(this.historyList);
    value.splice(index, 1);
    this.setData({ expr: 'historyList', value });
    return data;
  }

  // 监控对象列表
  @Action
  public async getLabelList() {
    const value = await getLabel().catch(() => []);
    this.setData({ expr: 'labelList', value });
  }

  // 查询历史列表
  @Action
  public async getListQueryHistory() {
    const value = await listQueryHistory({}).catch(() => []);
    this.setData({ expr: 'historyList', value });
    return value;
  }

  // 获取监控目标名字数据
  @Action
  public async getMainlineObjectTopo() {
    const value = await getMainlineObjectTopo().catch(() => []);
    this.setData({ expr: 'mainlineObjectTopo', value });
    return value;
  }

  // 新增一条查询条件
  @Mutation
  public handleAddCondition(data: any = {}) {
    this.queryData.queryConfigs.push({
      key: random(10),
      hidden: false,
      label: data.label || this.labelCache,
      metricField: data.metricField || '',
      method: data.method || 'AVG',
      interval: data.interval || 60,
      resultTableId: data.resultTableId || '',
      dataSourceLabel: data.dataSourceLabel || '',
      dataTypeLabel: data.dataTypeLabel || '',
      groupBy: data.groupBy || null,
      where: data.where || null,
    });
  }

  // 克隆一条查询条件
  @Mutation
  public handleCloneQueryConfig(data: IQueryConfigsItem) {
    data.key = random(10);
    this.queryData.queryConfigs.push(data);
  }

  // 删除一条查询条件
  @Mutation
  public handleDeleteQueryConfig(index: number) {
    this.queryData.queryConfigs.splice(index, 1);
  }

  // 控制查询条件显隐
  @Mutation
  public handleHiddenQueryConfig(index: number) {
    const temp = this.queryData.queryConfigs[index];
    temp.hidden = !temp.hidden;
  }

  // 查询操作
  @Action
  public async handleQuery() {
    // 没选择查询条件不进行请求
    // if (!this.queryData.queryConfigs.filter(item => !item.hidden).every(item => item.metricField)) return
    // 通知更新where
    // Vue.prototype.$bus.$emit('get-conditions-value')
    this.updateStartEndTime(this.queryData.tools.timeRange);
    const temp = deepClone(this.queryData);
    temp.queryConfigs = temp.queryConfigs.filter((item: any) => !item.hidden && item.metricField);
    const targetFieldMap = {
      INSTANCE: 'ip',
      TOPO: 'host_topo_node',
      SERVICE_TEMPLATE: 'host_template_node',
      SET_TEMPLATE: 'host_template_node',
    };
    const value =
      this.queryData.targetType === 'INSTANCE'
        ? temp.target.map((item: any) => ({
            ip: item.ip,
            bk_cloud_id: item.bk_cloud_id,
            bk_supplier_id: item.bk_supplier_id,
          }))
        : temp.target.map((item: any) => ({
            bk_inst_id: item.bk_inst_id,
            bk_obj_id: item.bk_obj_id,
          }));
    // 监控目标格式转换
    temp.target = [
      [
        {
          field: targetFieldMap[this.queryData.targetType],
          method: 'eq',
          value,
        },
      ],
    ];
    if (!temp.queryConfigs.length) {
      this.setData({ expr: 'queryConfigsResult', value: {} });
      return;
    }
    // 清空查询结果
    this.setData({ expr: 'queryConfigsResult', value: {} });
    const params = transformDataKey(temp, true);
    this.setData({ expr: 'loading', value: true });
    const queryStartTime = +new Date();
    const { data, tips } = await getGraphQueryConfig(params, { needRes: true })
      .catch(() => [])
      .finally(() => {
        this.setData({ expr: 'queryTime', value: +new Date() - queryStartTime });
        this.setData({ expr: 'loading', value: false });
      });
    // 查询结果数据
    this.setData({ expr: 'queryConfigsResult', value: data });
    if (tips?.length) {
      Vue.prototype.$bkMessage({
        theme: 'warning',
        message: tips,
      });
    }
    return data;
  }

  // 初始化检索数据
  @Mutation
  public initStoreData() {
    this.queryData = {
      bkBizId: store.getters.bizId,
      queryConfigs: [],
      compareConfig: { type: 'none', split: true },
      target: [],
      targetType: 'INSTANCE',
      tools: {
        timeRange: 1 * 60 * 60 * 1000,
        refreshInterval: -1,
      },
      startTime: 0,
      endTime: 0,
    };
    this.queryConfigsResult = {};
    this.labelCache = 'service_module';
  }

  // 再次查询
  @Action
  public async queryAgain(index) {
    const mapList = [
      { expr: 'queryData', value: deepClone(this.historyList[index].config) },
      { expr: 'curTab', value: 'data-query-conditions' },
      { expr: 'queryConfigsResult', value: {} },
    ];
    this.setDataList(mapList);
    await Vue.nextTick();
    this.handleQuery();
  }

  // 保存查询条件
  @Action
  public async saveQueryHistory(name) {
    const params = {
      name,
      bk_biz_id: store.getters.bizId,
      config: this.historyList[0].config,
    };
    const data = await createQueryHistory(params).catch(() => {});
    this.setData({ expr: 'historyList.0.name', value: name });
    this.setData({ expr: 'historyList.0.id', value: data.id });
    return data;
  }

  @Mutation
  public setCompareConfig(payload: { timeOffset: string; type: string }) {
    this.queryData.compareConfig = { type: payload.type, split: true, timeOffset: payload.timeOffset };
  }

  /**
   * 修改state值
   * @param expr 表达式
   * @param value 值
   * @param context 上下文 默认为this
   */
  @Mutation
  public setData({ expr, value, context = this }: { context?: any; expr: string; value: any }) {
    expr.split('.').reduce((data, curKey, index, arr) => {
      if (index === arr.length - 1) {
        // 给表达式最后一个赋值
        return (data[curKey] = value);
      }
      return data[curKey];
    }, context);
  }

  // 批量赋值state操作
  @Action
  public async setDataList(list: { expr: string; value: any }[]) {
    list.forEach(item => {
      const { expr, value } = item;
      this.setData({ expr, value });
    });
  }

  // 更新查询条件数据
  @Action
  public async setQueryConfigItem({ index, expr, value }: { expr: string; index: number; value: any }) {
    const tempItem = this.queryData.queryConfigs[index];
    this.setData({ expr, value, context: tempItem });
  }

  // 处理时间范围
  @Mutation
  public updateStartEndTime(timeRange: number | string | string[]) {
    const { startTime, endTime } = handleTimeRange(timeRange);
    this.queryData.endTime = endTime;
    this.queryData.startTime = startTime;
  }
}

export default getModule(DataRetrieval);
