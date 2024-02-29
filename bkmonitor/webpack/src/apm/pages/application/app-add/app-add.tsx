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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { createApplication, metaConfigInfo } from 'monitor-api/modules/apm_meta';
import { Debounce } from 'monitor-common/utils/utils';
import { INavItem, IRouteBackItem } from 'monitor-pc/pages/monitor-k8s/typings';
import Viewer from 'monitor-ui/markdown-editor/viewer';

import { ICreateAppFormData } from '../../home/app-list';
import NavBar from '../../home/nav-bar';

import PluginStatusTag from './plugin-status-tag';
import SelectSystem, { ICardItem, IListDataItem } from './select-system';
import SettingParams, { IEsClusterInfo } from './setting-params';
import SideSlider from './side-slider';
import { SystemData } from './utils';

import './app-add.scss';

export interface ISetupData {
  index_prefix_name: string;
  es_retention_days: {
    default: number;
    default_es_max: number;
    private_es_max: number;
  };
  es_number_of_replicas: {
    default: number;
    default_es_max: number;
    private_es_max: number;
  };
}
export interface IPluginItem {
  is_official: boolean; // 是否为官方插件
  author: string; // 作者
  update_by: string; // 更新者
  description_md: string; // 描述md
  id: string;
}
@Component
export default class AppAdd extends tsc<{}> {
  // @Prop({ default: '', type: String }) appInfo: string;

  loading = false;

  /** 面包屑数据 */
  routeList: INavItem[] = [
    {
      id: 'home',
      name: 'APM'
    },
    {
      id: '',
      name: window.i18n.tc('新建应用')
    }
  ];
  /** 步骤数据 */
  steps = [
    { title: window.i18n.t('基本信息'), icon: 1 },
    { title: window.i18n.t('参数设置'), icon: 2 }
  ];
  /** 当前步骤 */
  currentStep: 1 | 2 | 3 = 1;

  systemData: SystemData = null;

  /** 环境选择页面渲染数据 */
  listData: IListDataItem[] = [
    {
      title: '支持插件',
      list: []
    },
    {
      title: '支持语言',
      multiple: true,
      list: []
    },
    {
      title: '支持环境',
      children: [
        {
          title: '容器环境',
          list: []
        },
        {
          title: '物理环境',
          list: []
        }
      ]
    }
  ];

  /** 集群信息 索引名 过期时间 副本数 */
  setupData: ISetupData = {
    index_prefix_name: '',
    es_retention_days: {
      default: 0,
      default_es_max: 0,
      private_es_max: 0
    },
    es_number_of_replicas: {
      default: 0,
      default_es_max: 0,
      private_es_max: 0
    }
  };

  /** 倒计时 */
  countdown = 3;
  countdownTimer = null;

  /** 选中的环境数据 */
  isCheckedItemList: ICardItem[] = [];

  /** 插件数据 */
  pluginsList: IPluginItem[] = [];

  routeBackItem: IRouteBackItem = {
    id: '',
    name: ''
  };

  appInfo: ICreateAppFormData = {
    name: '',
    enName: '',
    desc: '',
    pluginId: 'opentelemetry',
    plugin_config: {
      target_node_type: 'INSTANCE',
      target_object_type: 'HOST',
      target_nodes: [],
      data_encoding: '',
      paths: ['']
    }
  };

  /** 插件状态 */
  pluginStatusList = [
    {
      icon: 'icon-mc-check-fill',
      text: window.i18n.tc('官方'),
      checked: true,
      tips: window.i18n.tc('来源')
    },
    // {
    //   icon: 'icon-danger',
    //   text: '未认证',
    //   checked: false
    // },
    // {
    //   icon: 'icon-windows',
    //   text: 'windows',
    //   checked: false
    // },
    {
      icon: 'icon-mc-user-one',
      text: '',
      checked: false,
      tips: window.i18n.tc('创建人')
    },
    {
      icon: 'icon-bianji',
      text: '',
      checked: false,
      fontSize: 22,
      tips: window.i18n.tc('最近更新人')
    }
  ];
  pluginDescMd = '';
  currentPlugin: IPluginItem | null = null;

  // get appInfoData(): ICreateAppFormData {
  //   try {
  //     return JSON.parse(this.appInfo);
  //   } catch (error) {
  //     return null;
  //   }
  // }

  mounted() {
    this.getPluginList();
    this.initRouteBackChange();
  }

  /** 更新插件描述信息 */
  handlePluginDesc() {
    this.pluginStatusList[0].checked = this.currentPlugin?.is_official ?? false;
    this.pluginStatusList[1].text = this.currentPlugin?.author ?? '';
    this.pluginStatusList[2].text = this.currentPlugin?.update_by ?? '';
    this.pluginDescMd = this.currentPlugin?.description_md ?? '';
  }

  /**
   * 获取应用、语言等列表数据
   * 20231107 现在这里用作 setting-params 的 存储索引名 里显示 业务 名称。
   */
  async getPluginList() {
    this.loading = true;
    const data = await metaConfigInfo().catch(() => null);
    this.pluginsList = data.plugins;
    this.currentPlugin = this.pluginsList?.[0];
    this.handlePluginDesc();
    this.systemData = new SystemData(data);
    this.systemData.handleCheckedPlugin(this.appInfo?.pluginId);
    this.listData = this.systemData.addAppSystemData;
    /** 集群信息 */
    this.setupData = data.setup;
    this.loading = false;
  }

  /** 开始倒计时 */
  handleCountdownStart() {
    this.countdown = 3;
    this.countdownTimer = setInterval(() => {
      if (!this.countdown) {
        clearInterval(this.countdownTimer);
        this.countdownTimer = null;
        this.handleToAppDetail();
      } else {
        this.countdown -= 1;
      }
    }, 1000);
  }

  /** 跳转应用详情 */
  handleToAppDetail() {
    clearTimeout(this.countdownTimer);
    this.countdownTimer = null;
    this.$router.push({
      name: 'application',
      query: {
        'filter-app_name': this.appInfo.name
      }
      // path: `/application?filter-app_name=${this.appInfoData.enName}`
    });
  }

  /**
   * 提交操作
   * @param clusterInfo 集群数据
   */
  @Debounce(200)
  async handleSubmit(clusterInfo: IEsClusterInfo) {
    this.loading = true;
    const { deploymentIds, languageIds } = this.getSystemIds();
    const params: { [key: string]: any } = {
      app_name: this.appInfo?.name, // 应用名
      app_alias: this.appInfo?.enName, // 应用别名
      description: this.appInfo?.desc, // 应用描述
      plugin_id: this.appInfo?.pluginId, // 插件id
      enable_profiling: this.appInfo.enableProfiling,
      enable_tracing: this.appInfo.enableTracing,
      deployment_ids: deploymentIds, // 环境id
      language_ids: languageIds, // 语言
      datasource_option: clusterInfo
    };
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const plugin_config = {
      target_node_type: this.appInfo?.plugin_config?.target_node_type,
      target_object_type: this.appInfo?.plugin_config?.target_object_type,
      // TOOD：这里需要过滤一下
      target_nodes: this.appInfo?.plugin_config?.target_nodes,
      data_encoding: this.appInfo?.plugin_config?.data_encoding,
      paths: this.appInfo?.plugin_config?.paths
    };
    if (this.appInfo?.pluginId === 'log_trace') params.plugin_config = plugin_config;
    createApplication(params)
      .then(() => {
        this.currentStep = 3;
        this.handleCountdownStart();
      })
      .catch(err => {
        console.log(err);
      })
      .finally(() => (this.loading = false));
  }

  // 20230925 由于该页面没有 插件、语言、环境 列表，相关代码将没有作用。
  /** 处理环境选中值 */
  getSystemIds() {
    const languageIds = [];
    const deploymentIds = [];
    let pluginId = '';
    this.isCheckedItemList.forEach(item => {
      if (item.checked && item.theme === 'lang') {
        languageIds.push(item.id);
      } else if (item.checked && item.theme === 'system') {
        deploymentIds.push(item.id);
      } else if (item.checked && item.theme === 'plugin') {
        pluginId = item.id;
      }
    });
    return {
      pluginId,
      deploymentIds,
      languageIds
    };
  }

  // 20230925 由于该页面没有 插件、语言、环境 列表，相关代码将没有作用。
  /** 获取已经选中的环境配置 */
  getCheckedList(): ICardItem[] {
    const fn = list =>
      list.reduce((total, item) => {
        if (item.list) total.push(...item.list);
        if (item.children) total.push(...fn(item.children));
        return total;
      }, []);
    const list = fn(this.listData);
    return list.filter(item => item.checked);
  }

  /** 下一步 */
  handleNext() {
    // 20230925 由于该页面没有 插件、语言、环境 列表，相关代码将没有作用。
    // this.isCheckedItemList = this.getCheckedList();
    this.currentStep = 2;
  }

  /** 路由跳转 */
  initRouteBackChange() {
    if (!this.appInfo) {
      this.routeBackItem = {
        id: 'home'
      };
    }
  }

  render() {
    return (
      <div class='app-add-wrap'>
        <NavBar
          routeList={this.routeList}
          handlerPosition={'center'}
        >
          <bk-steps
            class='app-add-steps-list'
            slot='handler'
            steps={this.steps}
            cur-step={this.currentStep}
          ></bk-steps>
        </NavBar>
        <div class='app-add-content'>
          <div
            class='app-add-content-main'
            style={`background-color: ${this.currentStep !== 1 ? '#fff' : ''}`}
          >
            {
              [
                <SelectSystem
                  loading={this.loading}
                  listData={this.listData}
                  onNextStep={this.handleNext}
                  onChange={info => (this.appInfo = info)}
                ></SelectSystem>,
                <SettingParams
                  loading={this.loading}
                  appInfoData={this.appInfo}
                  setupData={this.setupData}
                  onPreStep={() => (this.currentStep = 1)}
                  currentPlugin={this.currentPlugin}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  onSubmit={this.handleSubmit}
                ></SettingParams>
              ][this.currentStep - 1]
            }
            {this.currentStep === 3 && (
              <div class='add-success-tips'>
                <i class='icon-monitor icon-check'></i>
                <div class='success-text'>{this.$t('新建应用成功')}</div>
                <i18n
                  tag='div'
                  class='jump-link-row'
                  path='{0}秒后将自动跳转至{1}'
                >
                  <span class='time'>{this.countdown}</span>
                  <span
                    class='link'
                    onClick={this.handleToAppDetail}
                  >
                    {this.$t('应用详情')}
                  </span>
                </i18n>
              </div>
            )}
          </div>
          {this.currentStep === 2 && (
            <SideSlider>
              <div class='plugin-desc-content'>
                <div class='plugin-desc-title'>{this.$t('插件描述')}</div>
                <div class='plugin-status-list'>
                  <div class='plugin-status-main'>
                    {this.pluginStatusList.map(item => (
                      <PluginStatusTag
                        class='status-item'
                        icon={item.icon}
                        checked={item.checked}
                        text={item.text}
                        iconFontSize={item.fontSize}
                        tips={item.tips}
                      />
                    ))}
                  </div>
                </div>
                <Viewer
                  value={this.pluginDescMd}
                  class='md-viewer'
                ></Viewer>
              </div>
            </SideSlider>
          )}
        </div>
      </div>
    );
  }
}
