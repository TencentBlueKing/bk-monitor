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

import type { IOverseasConfig } from '../../types/common/common';

import './overseas-logo.scss';

interface IOverseasLogoProps {
  globalList: [] | IOverseasConfig[];
}

@Component
export default class OverseasLogo extends tsc<IOverseasLogoProps> {
  @Prop({ default: [] }) globalList: [] | IOverseasConfig[];
  // 处理链接跳转
  handleLink(item: IOverseasConfig) {
    item.url && window.open(item.url, '_blank');
  }

  render() {
    return (
      <bk-popover
        always={false}
        arrow={false}
        offset='15'
        placement='bottom-start'
        theme='light common-monitor overseas-logo'
      >
        <div class='header-global'>
          <span class='icon-monitor icon-mc-global' />
        </div>
        <div
          class='monitor-navigation-global'
          slot='content'
        >
          {this.globalList.map((config, index) => (
            <div
              key={index}
              class='nav-item'
              onClick={() => this.handleLink(config)}
            >
              <div>{config.title}</div>
              <span class='nav-item-subtitle'>{config.subtitle}</span>
              {config.icon && <div class='nav-item-icon icon-monitor icon-mc-goto' />}
            </div>
          ))}
        </div>
      </bk-popover>
    );
  }
}
