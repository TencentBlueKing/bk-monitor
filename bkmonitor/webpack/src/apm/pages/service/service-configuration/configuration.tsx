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
import { Component, Mixins, Provide } from 'vue-property-decorator';

import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';
import { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import ConfigurationNav from '../../../components/configuration-nav/configuration-nav';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as authorityMap from '../../home/authority-map';
import BasicInfo from './basic-info';

import './configuration.scss';

@Component
export default class ApplicationConfiguration extends Mixins(authorityMixinCreate(authorityMap)) {
  @Provide('authority') authority;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;

  activeMenu = 'baseInfo';
  appName = '';
  serviceName = '';
  // 导航条设置
  routeList: INavItem[] = [];
  menuList = [{ id: 'baseInfo', name: window.i18n.tc('基本设置') }];

  /** 页面权限校验实例资源 */
  get authorityResource() {
    return { application_name: this.$route.query?.app_name || '' };
  }
  get positonText() {
    return `${window.i18n.tc('服务')}：${this.serviceName}`;
  }

  beforeRouteEnter(from, to, next) {
    const { query: formQuery } = from;
    const appName = (formQuery.app_name as string) || '';
    const serviceName = (formQuery.service_name as string) || '';
    next((vm: ApplicationConfiguration) => {
      vm.routeList = [
        // {
        //   id: 'home',
        //   name: 'APM'
        // },
        // {
        //   id: 'application',
        //   name: `${window.i18n.tc('应用')}：${appName}`,
        //   query: {
        //     'filter-app_name': appName
        //   }
        // },
        // {
        //   id: 'service',
        //   name: `${window.i18n.tc('服务')}：${serviceName}`,
        //   query: {
        //     'filter-app_name': appName,
        //     'filter-service_name': serviceName
        //   }
        // },
        // {
        //   id: 'configuration',
        //   name: window.i18n.tc('服务设置')
        // }
        {
          id: 'configuration',
          name: window.i18n.tc('route-配置服务'),
        },
      ];
      vm.appName = appName;
      vm.serviceName = serviceName;
    });
  }

  getContentPanel() {
    switch (this.activeMenu) {
      case 'baseInfo':
        return <BasicInfo />;
      default:
        return '';
    }
  }
  handleClickAlert() {
    this.$router.push({
      name: 'service',
      query: {
        'filter-app_name': this.appName,
        'filter-service_name': this.serviceName,
      },
    });
  }

  render() {
    return (
      <div class='service-configuration'>
        <CommonNavBar
          class='service-configuration-nav'
          slot='nav'
          navMode={'display'}
          needBack={true}
          needShadow={true}
          positionText={this.positonText}
          routeList={this.routeList}
          needCopyLink
        />
        <div class='configuration-content'>
          <ConfigurationNav
            active={this.activeMenu}
            menuList={this.menuList}
            onAlertClick={this.handleClickAlert}
          >
            {this.getContentPanel()}
          </ConfigurationNav>
        </div>
      </div>
    );
  }
}
