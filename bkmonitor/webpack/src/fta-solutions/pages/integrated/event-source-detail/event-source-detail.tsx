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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import { getPluginDetail } from './mock'
import { getEventPluginInstance } from '../../../../monitor-api/modules/event_plugin';
import { random } from '../../../../monitor-common/utils/utils';
import Viewer from '../../../../monitor-ui/markdown-editor/viewer';

import Config from './config/config';
import DataStatus from './data-status/data-status';
import HeaderFunctional from './detail-header/detail-header';
import TestControl from './test-control/test-control';
import {
  bgColorMap,
  EStatusMap,
  fontColorMap,
  IAlertConfigTable,
  IBaseInfo,
  INormalizationTable,
  IPushConfigData,
  ITabListItem,
  StatusType,
  textMap
} from './types';

import './event-source-detail.scss';

const { i18n } = window;

interface IDetail {
  value?: boolean;
  id: string;
  version?: string;
  onInstall?: (data: IBaseInfo) => void;
}

enum ETabKey {
  'desc' = 1,
  'config',
  'dataStatus'
}

/**
 * 故障资源首页（插件管理）
 */
@Component
export default class EventSourceDetail extends tsc<IDetail> {
  @Model('show-change', { type: Boolean }) readonly value;
  @Prop({ default: null, type: String }) readonly id;
  @Prop({ default: '', type: String }) version: string;

  isLoading = false;
  // 初始化高度
  height = 720;
  isShowTest = false;

  // 状态
  statusKey: StatusType = 'AVAILABLE';
  // 基础信息
  baseInfo: IBaseInfo = {
    name: '',
    pluginId: '',
    label: [],
    createUser: '',
    popularity: 0,
    updateUser: '',
    updateTime: '',
    pluginType: null,
    logo: '',
    version: '',
    sourceCode: '',
    pluginTypeDisplay: '',
    categoryDisplay: '',
    scenario: null,
    isInstalled: false
  };
  // 概述md文档
  descMd = '';
  httpEditorData: any = {};
  // push类型字段映射表
  normalizationTable: INormalizationTable[] = [];
  // push类型告警名称列表
  alertConfigTable: IAlertConfigTable[] = [];
  // push类型data
  pushConfigData: IPushConfigData = {
    sourceFormat: '',
    ingesterHost: '',
    pluginId: '',
    pushUrl: ''
  };
  /* pull 类型下 配置表单 */
  paramsSchema = [];
  instanceParamsSchema = [];
  // 接入引导md
  tutorialMd = '';
  /* 是否安装 */
  isInstalled = false;
  instanceId = 0;

  // tab数据
  tabActive = ETabKey.desc;

  tabList: ITabListItem[] = [
    { id: 1, name: i18n.tc('概述') },
    { id: 2, name: i18n.tc('配置') },
    { id: 3, name: i18n.tc('数据状态'), warning: false }
  ];

  configKey = random(8);

  get curStatus(): string {
    return EStatusMap[this.isInstalled ? 'ENABLED' : this.statusKey];
  }
  get curColor(): string {
    return bgColorMap[this.curStatus];
  }
  get curFontColor(): string {
    return fontColorMap[this.curStatus];
  }
  get curStatusText(): string {
    return textMap[this.curStatus];
  }
  get getContentMainHeight() {
    return this.height - 212;
  }

  @Watch('value', { immediate: true })
  valueChange(v: boolean) {
    if (v) {
      this.tabActive = ETabKey.desc;
      this.tabList = [
        { id: 1, name: i18n.tc('概述') },
        { id: 2, name: i18n.tc('配置') },
        { id: 3, name: i18n.tc('数据状态'), warning: false }
      ];
      this.getMinHeight();
      this.getPluginDetail();
    }
  }

  @Emit('show-change')
  emitShowChange(v: boolean) {
    return v;
  }

  created() {
    this.getMinHeight();
  }

  // 获取插件详情数据
  async getPluginDetail() {
    this.isLoading = true;
    const data: any = await getEventPluginInstance(this.id, { version: this.version })
      .catch(() => {
        this.handleHidden();
      })
      .finally(() => (this.isLoading = false));
    if (!data) return;
    const {
      status,
      plugin_display_name: pluginDisplayName,
      tags,
      author,
      popularity,
      update_user: updateUser,
      update_time: updateTime,
      plugin_type: pluginType,
      plugin_type_display: pluginTypeDisplay,
      logo,
      description,
      ingest_config: ingestConfig,
      normalization_config: normalizationConfig,
      alert_config: alertConfig,
      tutorial,
      plugin_id: pluginId,
      category_display: categoryDisplay,
      scenario,
      params_schema: paramsSchema,
      is_installed: isInstalled,
      instances
    } = data;
    // 插件状态及其基本信息
    this.statusKey = status as StatusType;
    this.baseInfo.name = pluginDisplayName || pluginId;
    this.baseInfo.pluginId = pluginId;
    this.baseInfo.label = tags;
    this.baseInfo.createUser = author;
    this.baseInfo.popularity = popularity;
    this.baseInfo.updateUser = updateUser;
    this.baseInfo.updateTime = updateTime;
    this.baseInfo.pluginTypeDisplay = pluginTypeDisplay;
    this.baseInfo.pluginType = pluginType;
    this.baseInfo.logo = logo;
    this.baseInfo.categoryDisplay = categoryDisplay;
    this.baseInfo.scenario = scenario;
    this.baseInfo.isInstalled = isInstalled;
    // 概述md文档
    this.descMd = this.handleMdMediaSrc(description);
    this.paramsSchema = paramsSchema;
    this.instanceParamsSchema = instances?.[0]?.params_schema || [];
    this.normalizationTable = normalizationConfig || [];
    this.alertConfigTable = alertConfig || [];
    const { source_format: sourceFormat, ingester_host: ingesterHost, push_url: pushUrl } = ingestConfig;
    this.pushConfigData.ingesterHost = ingesterHost;
    this.pushConfigData.sourceFormat = sourceFormat;
    this.pushConfigData.pluginId = pluginId;
    this.pushConfigData.pushUrl = pushUrl;
    // 接入引导md
    this.tutorialMd = this.handleMdMediaSrc(tutorial);
    this.isInstalled = isInstalled;
    this.instanceId = instances?.[0]?.id || 0;
    if (!isInstalled) {
      this.tabList = [
        { id: 1, name: i18n.tc('概述') },
        { id: 2, name: i18n.tc('配置') }
      ];
    }
    this.configKey = random(8);
  }

  // 获取初始化高度
  getMinHeight() {
    this.height = document.documentElement.clientHeight - 48;
  }

  // 隐藏详情
  handleHidden() {
    this.statusKey = null;
    this.emitShowChange(false);
  }

  // 切换tab栏
  tabChange(tab) {
    if (this.tabActive === tab.id) return;
    this.tabActive = tab.id;
  }

  // 处理md文档的相对路径资源
  handleMdMediaSrc(mdStr: string) {
    const { siteUrl } = this.$store.getters;
    // [gogogo](./media/pic.png)
    let res = mdStr.replace(
      /\[(.+?)\]\((.+?)\)/g,
      (...args) => `[${args[1]}](${siteUrl}fta/plugin/event/${this.id}/media/${args[2].replace(/^\.\/?/, '')})`
    );
    // href="" src=""
    res = res.replace(/(href|src)=('|")(.+?)('|")/g, (...args) => {
      if (/(ht|f)tps?/.test(args[3])) return args[0];
      return `${args[1]}="${siteUrl}fta/plugin/event/${this.id}/media/${args[3].replace(/^\.\/?/, '')}"`;
    });
    return res;
  }

  handleClose(v) {
    if (v) return;
    this.emitShowChange(v);
  }
  viewEvent() {
    const url = location.href.replace(location.hash, '#/event-center');
    window.open(`${url}?queryString=${i18n.t('告警源')} : "${this.baseInfo.pluginId}"`, '_blank');
  }

  @Emit('install')
  handleInstall() {
    return {
      version: this.version,
      pluginId: this.id,
      paramsSchema: this.paramsSchema,
      pluginDisplayName: this.baseInfo.name
    };
  }

  protected render() {
    return (
      <bk-dialog
        show-mask={true}
        show-footer={false}
        mask-close={true}
        position={{ top: 24 }}
        width={1000}
        transfer={true}
        ext-cls='event-source-detail-wrap'
        value={this.value}
        {...{ on: { 'value-change': this.handleClose } }}
      >
        <div
          v-bkloading={{ isLoading: this.isLoading }}
          class={['event-source-main', this.curStatus]}
          style={`height: ${this.height}px;`}
        >
          <span
            class='close-btn'
            onClick={this.handleHidden}
          >
            <i class='icon-monitor icon-mc-close'></i>
          </span>
          <div
            class='status-bar'
            style={this.statusKey && this.statusKey !== 'AVAILABLE' ? `background-color: ${this.curColor}` : ''}
          ></div>
          {/* 头部 */}
          <HeaderFunctional
            data={this.baseInfo}
            curColor={this.curColor}
            curFontColor={this.curFontColor}
            curStatusText={this.curStatusText}
            onInstall={() => this.handleInstall()}
            onViewEvent={this.viewEvent}
          ></HeaderFunctional>
          <div class='line'></div>
          {/* 详情内容区域 */}
          <div class='event-source-content'>
            {/* tab */}
            <div class='content-tab-wrap'>
              {this.tabList.map(tab => (
                <div
                  class={['content-tab-item', { 'content-tab-item-active': this.tabActive === tab.id }]}
                  onClick={() => this.tabChange(tab)}
                >
                  <div class='content-tab-item-mian'>
                    <span class={['tab-item-name', { 'tab-item-name-warning': tab.warning }]}>
                      {tab.name}
                      {tab.warning && <i class='icon-monitor icon-tixing'></i>}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div
              class='event-source-content-main'
              style={`height: ${this.getContentMainHeight}px;`}
            >
              {/* 概述 */}
              {this.tabActive === ETabKey.desc ? (
                <div>
                  {this.descMd ? (
                    <Viewer
                      class='md-viewer'
                      value={this.descMd}
                      flowchartStyle={true}
                    ></Viewer>
                  ) : (
                    <div style='padding: 20px 10px;'>{this.$t('暂无')}</div>
                  )}
                </div>
              ) : undefined}
              {/* 数据状态 */}
              {!!this.isInstalled && (
                <DataStatus
                  style={`display: ${this.tabActive === ETabKey.dataStatus ? 'block' : 'none'}`}
                  pluginId={this.id}
                ></DataStatus>
              )}
              {/* 配置 */}
              {
                <Config
                  v-show={this.tabActive === ETabKey.config}
                  id={this.id}
                  isShow={this.value}
                  type={this.baseInfo.pluginType}
                  httpData={this.httpEditorData}
                  normalizationTable={this.normalizationTable}
                  alertConfigTable={this.alertConfigTable}
                  pushConfigData={this.pushConfigData}
                  tutorialMd={this.tutorialMd}
                  paramsSchema={this.instanceParamsSchema}
                  instanceId={this.instanceId}
                  isInstalled={this.isInstalled}
                  key={this.configKey}
                ></Config>
              }
            </div>
          </div>
          {/* 测试控件 */}
          {false && this.tabActive === ETabKey.config && <TestControl v-model={this.isShowTest}></TestControl>}
        </div>
      </bk-dialog>
    );
  }
}
