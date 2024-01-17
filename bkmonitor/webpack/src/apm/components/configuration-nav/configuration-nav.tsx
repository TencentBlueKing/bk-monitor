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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorTab from '../../../monitor-pc/components/monitor-tab/monitor-tab';

import './configuration-nav.scss';

interface IMenuItem {
  id: string;
  name: string;
}

interface IConfiguratioNavProps {
  active: string;
  menuList: IMenuItem[];
}

interface IConfiguratioNavEvent {
  onMenuClick: string;
  onAlertClick: void;
}

@Component
export default class ConfigurationNav extends tsc<IConfiguratioNavProps, IConfiguratioNavEvent> {
  @Prop({ type: Array, default: [] }) menuList: IMenuItem[];
  @Prop({ type: String, default: '' }) active: string;

  @Emit('menuClick')
  handleClickMenu(active) {
    return active;
  }
  @Emit('alertClick')
  handleClickAlert() {}

  render() {
    return (
      <div class='configuration-nav'>
        <MonitorTab
          active={this.active}
          on-tab-change={this.handleClickMenu}
        >
          {this.menuList.map(item => (
            <bk-tab-panel
              key={item.id}
              name={item.id}
              label={item.name}
            ></bk-tab-panel>
          ))}
        </MonitorTab>
        <bk-alert class='info-alert'>
          <i18n
            slot='title'
            path='数据上报好了，去 {0}'
          >
            <span
              class='link'
              onClick={this.handleClickAlert}
            >
              {this.$t('查看数据')}
            </span>
          </i18n>
        </bk-alert>
        <div class='configuration-main'>{this.$slots.default}</div>
      </div>
    );
  }
}
