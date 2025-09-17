/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import AppAddForm from './add-app-form';

import './add-app-side.scss';

interface IEvent {
  onShowChange?: (show: boolean) => void;
  onSuccess?: (appName: string, appId: string) => void;
}

interface IProps {
  isShow: boolean;
}

@Component
export default class AddApplication extends tsc<IProps, IEvent> {
  @Prop({ default: false, type: Boolean }) isShow: boolean;
  // 指南页面首次新建应用

  @Emit('showChange')
  handleShowChange(v: boolean) {
    return v;
  }

  handleSuccess(v: string, appId: string) {
    this.handleShowChange(false);
    this.$emit('success', v, appId);
  }

  handleMoreClick() {
    window.open('', '_blank');
  }

  render() {
    return (
      <bk-sideslider
        class='add-app-side'
        isShow={this.isShow}
        quickClose={true}
        showMask={true}
        {...{ on: { 'update:isShow': this.handleShowChange } }}
        width={640}
      >
        <div slot='header'>{this.$t('新建应用')}</div>
        <div
          class='content-main'
          slot='content'
        >
          <div class='content-tip-wrap'>
            <i class='icon-monitor icon-hint' />
            <span class='content-tip'>
              {this.$t(
                '应用一般是拥有独立的站点，由多个 Service 共同组成，提供完整的产品功能，拥有独立的软件架构。从技术方面来说应用是 Trace 数据的存储隔离，在同一个应用内的数据将进行统计和观测。'
              )}
              <div class='more'>
                {this.$t('更多请')}
                <span
                  class='more-link'
                  onClick={this.handleMoreClick}
                >
                  {this.$t('查看产品文档')}
                </span>
              </div>
            </span>
          </div>
          <AppAddForm
            onCancel={() => this.handleShowChange(false)}
            onSuccess={this.handleSuccess}
          />
        </div>
      </bk-sideslider>
    );
  }
}
