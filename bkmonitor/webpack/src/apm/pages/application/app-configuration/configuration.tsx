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
import { Component, Mixins, Prop, Ref } from 'vue-property-decorator';

import { applicationInfoByAppName, listEsClusterGroups, metaConfigInfo } from 'monitor-api/modules/apm_meta';
import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';

import ConfigurationNav from '../../../components/configuration-nav/configuration-nav';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as authorityMap from '../../home/authority-map';
import BasicConfiguration from './basic-configuration';
import ConfigurationView from './configuration-view';
import DataStatus from './data-state/data-state';
import StorageState from './storage-state/storage-state';

import type { IAppInfo, IClusterItem, IMenuItem } from './type';
import type { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './configuration.scss';

@Component
export default class ApplicationConfiguration extends Mixins(authorityMixinCreate(authorityMap)) {
  @Ref() contentRef: HTMLElement;
  @Prop({ type: String, default: '' }) appName: string;
  routeList: INavItem[] = []; // 导航条设置
  activeMenu = 'basicConfiguration'; // 当前设置菜单
  loading = false;
  firstLoad = true; // 是否首次加载
  pluginDesc = null; // 插件说明
  /** 应用详情 */
  appInfo: IAppInfo = {
    application_id: null,
    app_name: '',
    app_alias: '',
    description: '',
    application_apdex_config: {
      apdex_default: 0,
      apdex_http: 0,
      apdex_db: 0,
      apdex_rpc: 0,
      apdex_backend: 0,
      apdex_messaging: 0,
    },
    owner: '',
    is_enabled: false,
    es_storage_index_name: '',
    application_datasource_config: {
      es_number_of_replicas: 0,
      es_retention: 1,
      es_storage_cluster: 0, // 存储集群
      es_shards: 1, // 分片数
    },
    create_user: '',
    create_time: '',
    update_time: '',
    update_user: '', // 更新人
    no_data_period: 0,
    application_sampler_config: {
      sampler_type: '',
      sampler_percentage: 0,
    },
    application_instance_name_config: {
      instance_name_composition: [],
    },
    application_db_config: [],
    application_db_system: [],
    plugin_id: '',
    plugin_config: {
      target_node_type: 'INSTANCE',
      target_nodes: [],
      target_object_type: 'HOST',
      data_encoding: '',
      paths: [''],
      bk_biz_id: window.bk_biz_id,
      bk_data_id: '',
      subscription_id: '',
    },
  };
  /** 历史记录弹窗配置 */
  recordData: Record<string, string> = {};
  /** 插件使用说明侧栏配置 */
  configurationView: {
    isActive: boolean;
    range: number[];
    rightWidth: number | string;
    show: boolean;
  } = {
    rightWidth: '33%',
    range: [300, 1200],
    isActive: false,
    show: false,
  };
  menuList: IMenuItem[] = [
    // { id: 'baseInfo', name: window.i18n.tc('基本信息') },
    { id: 'basicConfiguration', name: window.i18n.tc('基础配置') },
    { id: 'storageState', name: window.i18n.tc('存储状态') },
    { id: 'dataStatus', name: window.i18n.tc('数据状态') },
    // { id: 'indicatorDimension', name: window.i18n.tc('指标维度') }
  ];
  clusterList: IClusterItem[] = []; // 存储集群列表

  get rightWidth() {
    const { show, rightWidth } = this.configurationView;

    return show ? (typeof rightWidth === 'string' ? rightWidth : `${rightWidth}px`) : '0px';
  }
  get positionText() {
    return `${window.i18n.tc('应用')}：${this.appInfo.app_name}`;
  }

  beforeRouteEnter(from, to, next) {
    next((vm: ApplicationConfiguration) => {
      vm.routeList = [
        // {
        //   id: 'home',
        //   name: 'APM'
        // },
        // {
        //   id: 'application',
        //   name: '',
        //   query: {
        //     'filter-app_name': ''
        //   }
        // },
        // {
        //   id: 'configuration',
        //   name: window.i18n.tc('应用设置')
        // }
        {
          id: 'configuration',
          name: window.i18n.tc('route-配置应用'),
        },
      ];
    });
  }

  async created() {
    await this.getAppBaseInfo();
    const { query } = this.$route;
    // this.activeMenu = (query.active as string) || 'baseInfo';
    this.activeMenu = (query.active as string) || 'basicConfiguration';
    this.getEsCluster();
  }

  /**
   * @desc 获取应用基本信息
   */
  async getAppBaseInfo() {
    if (this.appName) {
      this.loading = this.firstLoad;
      const res = await applicationInfoByAppName({
        app_name: this.appName,
      }).catch(() => {});
      // 特殊处理。应该后端的 bug 。
      if ((res as IAppInfo).application_db_config.length === 0) {
        res.application_db_config.push({
          db_system: '',
          trace_mode: 'closed',
          length: 10000,
          threshold: 500,
          enabled_slow_sql: true,
        });
      }
      Object.assign(this.appInfo, res);
      this.authority.MANAGE_AUTH = res?.permission?.manage_apm_application_v2 || false;
      const {
        // app_name: appName,
        create_user: createUser,
        create_time: createTime,
        update_time: updateTime,
        update_user: updateUser,
      } = this.appInfo;
      // this.routeList[1].name = `${this.$t('应用')}：${appName}`;
      // this.routeList[1].query['filter-app_name'] = appName;
      this.recordData = { createUser, createTime, updateTime, updateUser };
      this.getPluginDesc(res.plugin_id || '');
      this.loading = false;
      this.firstLoad = false;
    }
  }
  /**
   * @desc 获取es集群列表
   */
  async getEsCluster() {
    const list = await listEsClusterGroups().catch(() => []);
    this.clusterList = list;
  }
  /**
   * @desc 获取应用配置插件说明
   * @param { stirng } pluginId 插件id
   */
  async getPluginDesc(pluginId: string) {
    if (pluginId) {
      const data = await metaConfigInfo().catch(() => null);
      const pluginList = data?.plugins;
      const target = pluginList.find(plugin => plugin.id === pluginId);
      this.pluginDesc = target?.access_md || '';
    }
  }
  /**
   * @desc 左侧菜单选中
   * @param { string } active
   */
  handleMenuClick(active: string) {
    const { name, params } = this.$route;
    this.activeMenu = active;
    this.$router.replace({ name, params, query: { active } });
  }
  handleClickAlert() {
    this.$router.push({
      name: 'application',
      query: {
        'filter-app_name': this.appInfo.app_name,
      },
    });
  }
  /**
   * @desc 插件使用说明侧栏开启/关闭
   * @param { MouseEvent } e
   */
  handleMouseDown(e: MouseEvent) {
    const node = e.target as HTMLElement;
    const parentNode = node.parentNode as HTMLElement;

    if (!parentNode) return;

    const nodeRect = node.getBoundingClientRect();
    const rect = parentNode.getBoundingClientRect();
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    const handleMouseMove = event => {
      this.configurationView.isActive = true;
      const [min, max] = this.configurationView.range;
      const newWidth = rect.right - event.clientX + nodeRect.width;
      if (newWidth < min) {
        this.configurationView.rightWidth = min;
      } else if (newWidth > max) {
        this.configurationView.rightWidth = max;
      } else {
        this.configurationView.rightWidth = Math.min(newWidth, max);
      }
    };
    const handleMouseUp = () => {
      this.configurationView.isActive = false;
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
  /**
   * @desc 动态计算左右面板宽度样式
   * @param { string } direction
   */
  handleContentStyle(direction: string) {
    const width = direction === 'left' ? `calc(100% - ${this.rightWidth})` : this.rightWidth;
    return {
      width,
      flexBasis: width,
    };
  }
  /**
   * @desc 配置面板
   */
  getContentPanel() {
    switch (this.activeMenu) {
      case 'basicConfiguration': // 基本信息
        return (
          <BasicConfiguration
            data={this.appInfo}
            recordData={this.recordData}
            on-change={this.getAppBaseInfo}
          />
        );
      case 'storageState': // 存储状态
        return (
          <StorageState
            clusterList={this.clusterList}
            data={this.appInfo}
            on-change={this.getAppBaseInfo}
          />
        );
      case 'dataStatus': // 数据状态
        return <DataStatus data={this.appInfo} />;
      // case 'indicatorDimension': // 指标维度
      //   return <IndicatorDimension />;
      default:
        return '';
    }
  }
  handleTrigger() {
    this.configurationView.show = !this.configurationView.show;
  }

  render() {
    return (
      <div
        class='application-configuration'
        v-bkloading={{ isLoading: this.loading }}
      >
        <CommonNavBar
          class='application-configuration-nav'
          navMode={'display'}
          needBack={true}
          positionText={this.positionText}
          routeList={this.routeList}
          needCopyLink
        >
          {
            <span
              class={['application-configuration-detail-trigger', { active: this.configurationView.show }]}
              slot='append'
              onClick={this.handleTrigger}
            >
              <i class='icon-monitor icon-mc-detail' />
            </span>
          }
        </CommonNavBar>
        <div
          ref='contentRef'
          class='application-configuration-page'
        >
          <div
            style={this.handleContentStyle('left')}
            class='configuration-content-left'
          >
            <ConfigurationNav
              active={this.activeMenu}
              menuList={this.menuList}
              onAlertClick={this.handleClickAlert}
              onMenuClick={this.handleMenuClick}
            >
              {!this.firstLoad && this.getContentPanel()}
            </ConfigurationNav>
          </div>
          <div
            style={this.handleContentStyle('right')}
            class='configuration-content-right'
          >
            <div class='right-wrapper'>
              <div
                class={['drag', { active: this.configurationView.isActive }]}
                on-mousedown={this.handleMouseDown}
              />
              <ConfigurationView
                data={this.pluginDesc}
                onShrink={() => (this.configurationView.show = !this.configurationView.show)}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
}
