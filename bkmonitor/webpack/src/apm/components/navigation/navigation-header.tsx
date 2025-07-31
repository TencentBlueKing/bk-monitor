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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './navigation-header.scss';

export interface IFtaNavigationHeaderProps {
  active: string;
  list: INavItem[];
}
interface INavItem {
  id: string;
  name: string;
}
@Component
export default class FtaNavigationHeader extends tsc<IFtaNavigationHeaderProps> {
  @Prop({ required: true }) list: INavItem[];
  @Prop({ required: true }) active: string;

  handleNavChange(id: string) {
    if (this.$route.name === 'id') return;
    this.$router.push({ name: id });
  }

  render() {
    return (
      <div class='fta-navigation-header'>
        <div class='nav-header'>
          <i class='nav-header-icon' />
          <span class='nav-header-title'>{this.$t('故障自愈')}</span>
        </div>
        <ul class='nav-list'>
          {this.list.map(item => (
            <li
              key={item.id}
              class={{ 'nav-list-item': true, 'nav-active': this.active === item.id }}
              onClick={() => this.handleNavChange(item.id)}
            >
              {item.name}
            </li>
          ))}
        </ul>
      </div>
    );
  }
}
