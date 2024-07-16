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

import NoPermission from '../../components/no-permission/no-permission';
import DataPipeline from '../data-pipeline/data-pipeline';
import ResourceRegister from '../resource-register/resource-register';
import * as authorityMap from './authority-map';

import './platform-setting.scss';

enum ENavId {
  dataPipeline = 'dataPipeline',
  resourceRegister = 'resourceRegister',
}

@Component
export default class PlatformSetting extends tsc<object> {
  navList = [
    {
      id: ENavId.dataPipeline,
      name: window.i18n.tc('链路管理'),
    },
    {
      id: ENavId.resourceRegister,
      name: window.i18n.tc('资源注册'),
    },
  ];
  curNav = '';

  created() {
    if (this.navList.map(item => item.id).includes(this.$route.query?.nav as any)) {
      this.curNav = this.$route.query.nav as ENavId;
    } else {
      this.curNav = this.navList[0].id;
    }
  }

  handleNavChange(item) {
    if (this.curNav !== item.id) {
      this.curNav = item.id;
      this.$router.replace({
        query: {
          nav: item.id,
        },
      });
    }
  }

  render() {
    return (
      <div class='platform-setting-page'>
        <div class='setting-header'>{this.navList.find(item => item.id === this.curNav).name}</div>
        <div class='setting-content'>
          <div class='setting-content-left'>
            {this.navList.map(item => (
              <div
                key={item.id}
                class={['menu-item', { active: item.id === this.curNav }]}
                onClick={() => this.handleNavChange(item)}
              >
                {item.name}
              </div>
            ))}
          </div>
          <div class='setting-content-right'>
            {(() => {
              if (this.curNav === ENavId.dataPipeline) {
                return <DataPipeline />;
              }
              if (this.curNav === ENavId.resourceRegister) {
                return <ResourceRegister />;
              }
              return <NoPermission actionIds={authorityMap.MANAGE_GLOBAL_SETTING} />;
            })()}
          </div>
        </div>
      </div>
    );
  }
}
