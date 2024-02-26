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
import { Component, Mixins, Prop, Provide } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';
import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';
import { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import authorityMixinCreate from '../../mixins/authorityMixin';
import NoDataGuide from '../application/app-add/no-data-guide';

import * as authorityMap from './../home/authority-map';

import './service-add.scss';

interface IProps {
  pluginId: string;
  appName: string;
}

Component.registerHooks(['beforeRouteEnter']);
@Component
class ServiceAdd extends Mixins(authorityMixinCreate(authorityMap)) {
  @Prop({ type: String, default: '' }) pluginId: IProps['pluginId'];
  @Prop({ type: String, default: '' }) appName: IProps['appName'];

  @Provide('authority') authority;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;

  routeList: INavItem[] = [];

  /** 页面权限校验实例资源 */
  get authorityResource() {
    return { application_name: this.$route.params?.appName || '' };
  }

  beforeRouteEnter(from, to, next) {
    const { params: formParams } = from;
    const appName = (formParams.appName as string) || '';
    next((vm: ServiceAdd) => {
      vm.routeList = [
        {
          id: 'home',
          name: 'APM'
        },
        {
          id: 'application',
          name: `${window.i18n.tc('应用')}：${appName}`,
          query: {
            'filter-app_name': appName
          }
        },
        {
          id: 'service-add',
          name: vm.$t('接入服务')
        }
      ];
    });
  }

  render() {
    return (
      <div class='service-add'>
        <CommonNavBar
          slot='nav'
          class='service-configuration-nav'
          routeList={this.routeList}
          needShadow={true}
          needBack={false}
        />
        <div class='monitor-k8s-detail service-add-content'>
          <NoDataGuide
            appName={this.appName}
            type='service'
          />
        </div>
      </div>
    );
  }
}

export default tsx.ofType<IProps>().convert(ServiceAdd);
