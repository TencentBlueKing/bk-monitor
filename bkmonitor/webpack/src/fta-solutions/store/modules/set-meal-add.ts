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
/* eslint-disable new-cap */
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';
import store from '@store/store';
import {
  getConvergeFunction,
  getDimensions,
  getPlugins,
  getPluginTemplates,
  getTemplateDetail,
  getVariables
} from 'monitor-api/modules/action';
import { createActionConfig, retrieveActionConfig, updateActionConfig } from 'monitor-api/modules/model';
import { getNoticeWay } from 'monitor-api/modules/notice_group';
import { transformDataKey } from 'monitor-common/utils/utils';

const { i18n } = window;
export interface ISetMealAddState {
  noticeWayList: any;
  getNoticeWayList: any;
}

@Module({ name: 'set-meal-add', dynamic: true, namespaced: true, store })
class SetMealAdd extends VuexModule implements ISetMealAddState {
  // 编辑状态
  isEdit = false;

  // 通知方式表格
  noticeWayList = [];

  // 收敛维度
  dimensions = [];

  // 收敛方法列表
  convergeFunctions = [];

  // 输入变量列表
  messageTemplateList = [];

  // 周边系统id
  peripheralIdMap: number[] = [];
  // 告警通知插件id
  noticeId: number = null;
  // http 回调id
  callbackId: number = null;

  // 套餐类型列表
  mealTypeList = [];

  // 变量列表数据
  variableData = {
    variablePanels: [],
    variableTable: {}
  };

  levelList = [
    { id: 1, name: i18n.t('致命') },
    { id: 2, name: i18n.t('预警') },
    { id: 3, name: i18n.t('提醒') }
  ];

  // 变量数据
  variables = [];

  pluginDescription = {}; // 套餐类型md文档

  public get getNoticeWayList() {
    return this.noticeWayList;
  }
  public get getDimensions() {
    return this.dimensions;
  }
  public get getConvergeFunctions() {
    return this.convergeFunctions;
  }
  public get getVariablePanels() {
    return this.variableData.variablePanels;
  }
  public get getVariableTable() {
    return this.variableData.variableTable;
  }
  public get getIsEdit() {
    return this.isEdit;
  }
  public get getPeripheralIdMap() {
    return this.peripheralIdMap;
  }
  public get getNoticeId() {
    return this.noticeId;
  }
  public get getCallbackId() {
    return this.callbackId;
  }
  public get getMessageTemplateList() {
    return this.messageTemplateList;
  }
  public get mealTypeListData() {
    return this.mealTypeList;
  }
  public get getLevelList() {
    return this.levelList;
  }
  public get getPluginDescription() {
    return this.pluginDescription;
  }
  public get getVariables() {
    return this.variables;
  }

  /**
   * 修改state值
   * @param expr 表达式
   * @param value 值
   * @param context 上下文 默认为this
   */
  @Mutation
  public setData({ expr, value, context = this }: { expr: string; value: any; context?: any }) {
    expr.split('.').reduce((data, curKey, index, arr) => {
      if (index === arr.length - 1) {
        // 给表达式最后一个赋值
        return (data[curKey] = value);
      }
      return data[curKey];
    }, context);
  }

  // 设置插件类型id
  @Mutation
  public setPluginId(data) {
    this.peripheralIdMap = data.peripheralIdMap;
    this.noticeId = data.noticeId;
    this.callbackId = data.callbackId;
  }

  // 获取套餐
  @Action
  public async retrieveActionConfig(params: any) {
    const res: any = await retrieveActionConfig(params).catch(() => ({}));
    const isPeripheral = res.plugin_type !== '' && !['notice', 'webhook'].includes(res.plugin_type);
    const result: any = transformDataKey(res);
    if (isPeripheral) {
      result.executeConfig.templateDetail = res.execute_config.template_detail;
    }
    return result;
  }

  // 创建套餐
  @Action
  public async createActionConfig(params: any) {
    const result = await createActionConfig(params).catch(() => ({}));
    return result;
  }

  // 修改套餐
  @Action
  public async updateActionConfig(v) {
    const { configId, params } = v;
    const result = await updateActionConfig(configId, params).catch(() => ({}));
    return result;
  }

  /**
   * 获取套餐类型下拉列表
   */
  @Action
  public async getMealTypeList() {
    const result = await getPlugins().catch(() => []);
    this.setData({ expr: 'mealTypeList', value: result });
    this.setPluginDescription(result);
    return result;
  }
  /**
   * 获取周边系统下拉列表
   * @param id 套餐列表id
   */
  @Action
  public async getPluginTemplates(id: number) {
    return getPluginTemplates({ plugin_id: id });
  }

  @Action
  public async getTemplateDetail(params: { pluginId: number; templateId: number }) {
    return getTemplateDetail({ plugin_id: params.pluginId, template_id: params.templateId }).catch(() => ({}));
  }

  @Action
  public async getDimensionList() {
    const list = await getDimensions().catch(() => []);
    this.setDimension(list);
  }

  @Action
  public async getConvergeFunctionList() {
    const list = await getConvergeFunction().catch(() => []);
    this.setConvergeFunction(list);
  }

  // 获取变量列表
  @Action
  public async getVariableDataList() {
    const data = await getVariables().catch(() => []);
    const variableTable: any = {};
    const variablePanels = [];
    data.forEach(item => {
      variableTable[item.group] = item.items.map(opt => ({
        name: opt.name,
        desc: opt.desc,
        example: opt.example,
        tip: '变量示例：未恢复 &#91点击复制变量]'
      }));
      variablePanels.push({
        name: item.group,
        label: item.name
      });
    });
    this.setVariableTable(variableTable);
    this.setVariablePanels(variablePanels);
    this.setMessageTemplateList(data);
    this.setVariables(data);
  }

  // 获取通知方式表格
  @Action
  public async getNoticeWay() {
    const data = await getNoticeWay().catch(() => []);
    this.setNoticeWay(data);
  }

  @Mutation
  public setDimension(list) {
    this.dimensions = list;
  }

  @Mutation
  public setConvergeFunction(list) {
    this.convergeFunctions = list;
  }

  @Mutation
  public setVariablePanels(v) {
    this.variableData.variablePanels = v;
  }

  @Mutation
  public setVariableTable(v) {
    this.variableData.variableTable = v;
  }

  @Mutation
  public setMessageTemplateList(data) {
    let res = data.reduce((total, cur) => {
      total = total.concat(cur.items.map(item => ({ ...item, group: cur.group })));
      return total;
    }, []);
    res = res.map(item => ({
      id: item.name,
      name: item.desc,
      example: item.example,
      group: item.group
    }));
    this.messageTemplateList = res;
  }

  @Mutation
  public setNoticeWay(data) {
    this.noticeWayList = data.map(item => {
      const data = {
        ...item,
        type: item.type,
        label: item.label,
        icon: item.icon,
        tip: undefined,
        channel: item.channel,
        width: undefined
      };
      if (item.type === 'wxwork-bot') {
        data.tip = i18n.t(
          "获取会话ID方法:<br/>1.群聊列表右键添加群机器人: {name}<br/>2.手动 @{name} 并输入关键字'会话ID'<br/>3.将获取到的会话ID粘贴到输入框，使用逗号分隔",
          { name: item.name }
        );
      }
      if (item.type === 'bkchat') {
        data.tip = i18n.tc(
          '支持将告警信息发送至外部，包括企业微信群机器人、QQ、Slack、钉钉、飞书、微信公众号以及外部邮箱等多种告警通知方式。'
        );
        data.width = 240;
      }

      return data;
    });
  }

  @Mutation
  public setPluginDescription(data) {
    data.forEach(child => {
      child.children.forEach(item => {
        this.pluginDescription[item.id] = item.description;
      });
    });
  }

  @Mutation
  public setVariables(data) {
    const res = data.map(item => ({
      name: item.name,
      description: item.desc,
      items: item.items.map(child => ({
        description: child.example,
        id: child.name,
        name: child.desc
      }))
    }));
    this.variables = res;
  }
}
export default getModule(SetMealAdd);
