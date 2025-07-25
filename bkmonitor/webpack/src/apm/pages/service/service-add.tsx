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
import { Component, Mixins, Prop } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';

import authorityMixinCreate from '../../mixins/authorityMixin';
import * as authorityMap from './../home/authority-map';
import ServiceApply from './data-guide';

import type { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './service-add.scss';

interface IProps {
  appName: string;
  pluginId: string;
}

Component.registerHooks(['beforeRouteEnter']);
@Component
class ServiceAdd extends Mixins(authorityMixinCreate(authorityMap)) {
  @Prop({ type: String, default: '' }) pluginId: IProps['pluginId'];
  @Prop({ type: String, default: '' }) appName: IProps['appName'];
  guideUrl: string;
  routeList: INavItem[] = [];

  /** 页面权限校验实例资源 */
  get authorityResource() {
    return { application_name: this.$route.params?.appName || '' };
  }

  beforeRouteEnter(from, to, next) {
    next((vm: ServiceAdd) => {
      vm.routeList = [
        {
          id: 'service-add',
          name: vm.$t('接入服务'),
        },
      ];
    });
  }
  handleUpdateGuideUrl(url: string) {
    this.guideUrl = url;
  }
  render() {
    return (
      <div class='service-add'>
        <CommonNavBar
          class='service-configuration-nav'
          slot='nav'
          navMode={'display'}
          needBack={true}
          routeList={this.routeList}
        >
          <div slot='custom'>
            {this.$t('接入服务')}
            <div
              class='service-add-link'
              onClick={() => this.guideUrl && window.open(this.guideUrl)}
            >
              <i class='icon-monitor icon-mc-detail' />
              {this.$tc('完整接入指引')}
            </div>
          </div>
        </CommonNavBar>
        <div class='monitor-k8s-detail service-add-content'>
          {this.appName && (
            <ServiceApply
              defaultAppName={this.appName}
              onUpdateGuideUrl={this.handleUpdateGuideUrl}
            />
          )}
        </div>
      </div>
    );
  }
}

export default tsx.ofType<IProps>().convert(ServiceAdd);
