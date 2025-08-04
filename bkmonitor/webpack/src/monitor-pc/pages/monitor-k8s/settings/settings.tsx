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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deleteSceneView, getSceneView, getSceneViewList, updateSceneView } from 'monitor-api/modules/scene_view';
import { deepClone } from 'monitor-common/utils/utils';

import { SETTINGS_POP_Z_INDEX } from '../utils';
import SettingsDashboard from './settings-dashboard/settings-dashboard';
import SettingsTab from './settings-tab/settings-tab';
import SettingsVar from './settings-var/settings-var';

import type { IBookMark, ISettingTpl, SettingsDashboardType, SettingsWrapType } from '../typings';
import type { SettingsTabType, SettingsVarType, SettingType } from '../typings/settings';

import './settings.scss';

/**
 * k8s视图设置组件
 */
@Component
export default class SettingsWrapper extends tsc<SettingsWrapType.IProps, SettingsWrapType.IEvents> {
  /** 页签数据 */
  @Prop({ default: () => [], type: Array }) bookMarkData: IBookMark[];
  /** 侧栏 */
  @Prop({ default: 'edit-tab', type: String }) active: SettingType;
  /** 选中的页签 */
  @Prop({ default: '', type: String }) activeTab: string;
  /** 视图类型 */
  @Prop({ default: 'overview', type: String }) viewType: string;
  /* 场景id */
  @Prop({ default: 'host', type: String }) sceneId: string;
  /** 视图设置页面是否为跳转到自动添加页面 */
  @Prop({ default: false, type: Boolean }) initAddSetting: boolean;
  /* 是否开启自动分组 */
  @Prop({ default: false, type: Boolean }) enableAutoGrouping: boolean;
  /** 场景名称 */
  @Prop({ default: '', type: String }) title: string;
  @Ref() settingsVarRef: SettingsVar;
  @Ref() settingsTabRef: SettingsTab;
  @Ref() settingsDashBoardRef: SettingsDashboard;

  loading = false;

  /** 设置页面的切换 */
  localActive: SettingType = 'edit-tab';
  /** 设置页签的切换 */
  localActiveTab = '';
  /** 首次通过dashboard进入设置页面的页签数据，用户比较设置弹窗关闭后判断是否需要更新页签 */
  sourceTabData: Record<string, any> = {};
  localBookMarkData: IBookMark[] = [];
  isShowPanelChange = false;

  /** 判断是否存在编辑未保存 true为有未保存数据 */
  get hasDiff() {
    /** 编辑页签 */
    if (this.active === 'edit-tab') {
      return this.settingsTabRef?.localTabListIsDiff;
    }
    /** 编辑变量 */
    if (this.active === 'edit-variate') {
      return this.settingsVarRef?.localVarListIsDiff;
    }
    /** 编辑视图 */
    if (this.active === 'edit-dashboard') {
      return this.settingsDashBoardRef?.localDashBoardIsDiff;
    }
    return false;
  }

  /** 判断是否可新增删除页签 目前未动态配置 暂时由前端配置 采集、自定义指标支持 */
  get canAddTab() {
    // 匹配采集场景
    return this.sourceTabData?.options?.view_editable;
  }

  created() {
    this.localActive = this.active;
    this.localActiveTab = this.activeTab;
    const curBookMark = this.bookMarkData.find(item => item.id === this.localActiveTab);
    this.isShowPanelChange = curBookMark.show_panel_count;
    this.getTabDetail(this.localActiveTab, true);
  }

  @Watch('active')
  activeChange() {
    this.handleLocalActive();
  }

  async getTabList() {
    await getSceneViewList({
      scene_id: this.sceneId,
      type: this.viewType,
    })
      .then(res => {
        const newArr = [];
        res.forEach(item => {
          const curData = this.localBookMarkData.find(val => val.id === item.id);
          if (curData) newArr.push({ ...item, ...curData });
          else newArr.push(item);
        });
        this.localBookMarkData.splice(0, this.localBookMarkData.length, ...newArr);
      })
      .catch(() => []);
  }

  /**
   * @description: 获取页签数据
   * @param {string} tabId 页签id
   * @param {boolean} isInit 是否首次获取
   */
  async getTabDetail(tabId: string, isInit?: boolean) {
    this.loading = true;
    const data = await getSceneView({
      scene_id: this.sceneId,
      type: this.viewType,
      id: tabId,
    }).catch(err => {
      console.info(err);
    });
    this.loading = false;
    isInit ? this.initBookMark(data) : this.updateBookMark(data);
  }

  /**
   * @description: 首次加载页签数据初始化
   * @param {IBookMark} newData 视图配置详情
   */
  initBookMark(newData: IBookMark) {
    // 记录从视图进入设置页面数据，用于判断弹窗关闭后是否需要更新视图
    this.sourceTabData = deepClone(newData);

    this.localBookMarkData = this.bookMarkData.map((tab: any) => {
      const temp = {
        ...tab,
        variables: [],
        panels: [],
      };
      if (newData && tab.id === newData.id) {
        Object.assign(temp, { ...newData, isReady: true });
      }
      return temp;
    });
  }

  /**
   * @description: 保存后更新页签数据
   * @param {IBookMark} newData 视图配置详情
   */
  async updateBookMark(newData: IBookMark) {
    if (newData) {
      const index = this.localBookMarkData.findIndex(book => book.id === newData.id);
      const target = { ...this.localBookMarkData[index], ...{ ...newData, isReady: true } };
      await this.checkActiveDiff(newData);
      this.localBookMarkData.splice(index, 1, target);
    }
  }

  /**
   * @description: 保存后判断弹窗关闭后是否需要更新视图
   * @param {IBookMark} data 视图配置详情
   */
  checkActiveDiff(data) {
    // 判断有无页签是否显示数字被更改 有任一页签此设置被更改都需要更新
    const curBookMark = this.bookMarkData.find(item => item.id === data.id);
    if (curBookMark?.show_panel_count !== this.isShowPanelChange) {
      this.handlePanelChange(true);
      return;
    }

    if (data.id !== this.activeTab) return;

    const isPanelChange = JSON.stringify(this.sourceTabData) !== JSON.stringify(data);
    this.handlePanelChange(isPanelChange);
  }

  /**
   * @description: 提醒用户未保存设置
   */
  handleLocalActive() {
    /** 离开变量设置 并且存在未保存操作时*/
    if (this.hasDiff) {
      this.$bkInfo({
        zIndex: SETTINGS_POP_Z_INDEX,
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => (this.localActive = this.active),
        cancelFn: () => this.handleActiveChange(this.localActive),
      });
      return;
    }
    this.localActive = this.active;
  }

  @Emit('activeChange')
  handleActiveChange(active: SettingType) {
    return active;
  }

  @Emit('panelChange')
  handlePanelChange(isChange: boolean) {
    return isChange;
  }

  /**
   * @description: 保存当前页签的配置
   * @param {SettingsTabType} data 变量数据
   */
  handleSaveTabList(data: SettingsTabType.IEvents['onSave']) {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { id, name, view_order } = data;
    const tabData = { id, name, view_order };
    const config: SettingsWrapType.ISettingsSaveConfig = {
      options: {
        show_panel_count: data.show_panel_count,
      },
    };
    this.isShowPanelChange = data.show_panel_count;
    this.handleSaveConfig(config, tabData).then(async () => {
      const newTabData = await this.getTabList();
      const curPageData = this.localBookMarkData.find(item => item.id === data.id);
      const isPanelChange = JSON.stringify(newTabData) !== JSON.stringify(this.bookMarkData);
      curPageData && (curPageData.show_panel_count = data.show_panel_count);
      this.handlePanelChange(isPanelChange);
      if (view_order.length) {
        // 页签顺序被改变 需要重新排序
        const sortArr = [];
        view_order.forEach(val => {
          const data = this.localBookMarkData.find(item => item.id === val);
          sortArr.push(data);
        });
        this.localBookMarkData.splice(0, this.localBookMarkData.length, ...sortArr);
        setTimeout(() => {
          this.checkTabSrotChange(view_order);
        }, 10);
      }
    });
  }

  /**
   * @description: 判断页签顺序是否被改变
   * @param {Array} sort
   */
  checkTabSrotChange(sort: string[]) {
    const originSort = this.bookMarkData.map(data => data.id);
    if (JSON.stringify(sort) !== JSON.stringify(originSort)) this.handlePanelChange(true);
  }

  /**
   * @description: 删除页签
   * @param {string} id 页签id
   */
  async handleDeleteTab(id: string) {
    const params = {
      scene_id: this.sceneId, // 场景分类
      type: this.viewType,
      id,
    };
    await deleteSceneView(params).then(async () => {
      this.handlePanelChange(true);
      await this.getTabList();
      this.localActiveTab = this.localBookMarkData[0].id;
      this.settingsTabRef?.handleSelectItem(this.localBookMarkData[0]);
    });
  }

  /**
   * @description: 保存变量 只保存当前页签的配置
   * @param {SettingsVarType} data 变量数据
   * @return {SettingsVarType}
   */
  handleSaveVarList(data: SettingsVarType.IEvents['onSave']) {
    const config: SettingsWrapType.ISettingsSaveConfig = {
      variables: data.data.map(item => ({
        title: item.alias,
        type: 'list',
        targets: [
          {
            datasource: 'dimension',
            dataType: 'list',
            api: 'scene_view.getSceneViewDimensionValue',
            data: {
              field: item.groupBy,
              where: item.where.filter(item => !!item.key),
            },
            fields: {
              id: item.groupBy,
            },
          },
        ],
      })),
    };
    const { name, id } = data;
    const tabData = { id, name };
    this.handleSaveConfig(config, tabData).then(() => {
      this.$emit('saveVar', data);
    });
  }

  /**
   * @description: 保存视图配置
   * @param {SettingsDashboardType.IPanelGroup} order 变量数据
   */
  handleSaveOrder(order: SettingsDashboardType.IPanelData) {
    const { id, name, data } = order;
    const tabData = { id, name };
    const config: SettingsWrapType.ISettingsSaveConfig = {
      order: data,
    };
    this.handleSaveConfig(config, tabData);
  }

  /**
   * @description: 新建配置
   * @param {string} id
   * @param {string} name
   * @param {SettingsWrapType} config
   * @return {*}
   */
  // handleAddConfig(id: string, name: string, config: SettingsWrapType.ISettingsSaveConfig) {

  // }
  /**
   * @description: 新建编辑-保存页签、变量、视图配置
   */
  handleSaveConfig(config: SettingsWrapType.ISettingsSaveConfig, tabData: any): Promise<any> {
    // const { id, name } = this.currentBookMark;
    const params = {
      scene_id: this.sceneId, // 场景分类
      type: this.viewType,
      config, // 设置配置
    };
    Object.assign(params, tabData);
    return updateSceneView(params).then(() => {
      this.getTabDetail(tabData.id);
      this.$bkMessage({ message: this.$t('保存成功'), theme: 'success', extCls: 'common-settings-z-index' });
    });
  }

  /**
   * @description: 渲染对应的设置组件
   */
  renderSettingsComponents() {
    /** 设置弹窗 */
    const settingMap: ISettingTpl = {
      /** 编辑页签 */
      'edit-tab': (
        <SettingsTab
          key={this.active}
          ref='settingsTabRef'
          activeTab={this.localActiveTab}
          bookMarkData={this.localBookMarkData}
          canAddTab={this.canAddTab}
          needAutoAdd={this.initAddSetting}
          title={this.title}
          onDelete={this.handleDeleteTab}
          onSave={this.handleSaveTabList}
        />
      ),
      /** 编辑变量 */
      'edit-variate': (
        <SettingsVar
          ref='settingsVarRef'
          activeTab={this.activeTab}
          bookMarkData={this.localBookMarkData}
          getTabDetail={this.getTabDetail}
          needAutoAdd={this.initAddSetting}
          sceneId={this.sceneId}
          title={this.title}
          viewType={this.viewType}
          onSave={this.handleSaveVarList}
        />
      ),
      /** 编辑视图 */
      'edit-dashboard': (
        <SettingsDashboard
          ref='settingsDashBoardRef'
          activeTab={this.localActiveTab}
          bookMarkData={this.localBookMarkData}
          enableAutoGrouping={this.enableAutoGrouping}
          title={this.title}
          on-tab-change={tab => (this.localActiveTab = tab)}
          onGetTabDetail={this.getTabDetail}
          onSave={this.handleSaveOrder}
        />
      ),
    };
    return settingMap[this.localActive];
  }
  render() {
    return (
      <div
        class='k8s-settings-wrap'
        v-bkloading={{ isLoading: this.loading, zIndex: 2000 }}
      >
        {this.renderSettingsComponents()}
      </div>
    );
  }
}
