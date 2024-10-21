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

import NavBar from '../nav-bar';
import AppAddForm from './add-app-form';

import type { INavItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './add-app.scss';

@Component
export default class AddApp extends tsc<object> {
  /** 面包屑数据 */
  routeList: INavItem[] = [
    {
      id: '',
      name: window.i18n.tc('新建应用'),
    },
  ];

  handleSuccess() {
    this.$router.push({
      name: 'home',
    });
  }

  render() {
    return (
      <div class='app-add-page'>
        <NavBar
          handlerPosition={'center'}
          needBack={true}
          routeList={this.routeList}
        />
        <div class='app-add-content'>
          <div class='app-add-desc'>
            <div class='app-add-question'>{this.$t('什么是应用？')}</div>
            <div class='app-add-answer'>
              {this.$t('应用一般是拥有独立的站点，由多个Service共同组成，提供完整的产品功能，拥有独立的软件架构。 ')}
            </div>
            <div class='app-add-answer'>
              {this.$t(
                '从技术方面来说应用是Trace数据的存储隔离，在同一个应用内的数据将进行统计和观测。更多请查看产品文档。'
              )}
            </div>
          </div>
          <AppAddForm
            onCancel={() => this.$router.back()}
            onSuccess={() => this.handleSuccess()}
          />
        </div>
      </div>
    );
  }
}
