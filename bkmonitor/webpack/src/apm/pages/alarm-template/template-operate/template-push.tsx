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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './template-push.scss';

interface IProps {
  show?: boolean;
  onShowChange?: (v: boolean) => void;
}

@Component
export default class TemplatePush extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;

  tabList = [
    {
      name: 'service',
      label: '已关联的服务',
      count: 0,
    },
    {
      name: 'unservice',
      label: '未关联的服务',
      count: 0,
    },
  ];
  activeTab = 'service';

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }

  handleSubmit() {}

  render() {
    return (
      <bk-sideslider
        width={1000}
        ext-cls={'template-push-side-component'}
        before-close={() => {
          this.handleShowChange(false);
        }}
        isShow={this.show}
        quick-close
      >
        <div
          class='template-push-header'
          slot='header'
        >
          <span class='header-left'>
            <span class='header-title'>{this.$t('下发')}</span>
            <span class='split-line' />
            <span class='header-desc'>主调成功率</span>
          </span>
        </div>
        <div
          class='template-push-content'
          slot='content'
        >
          <bk-tab active={this.activeTab}>
            {this.tabList.map(item => (
              <bk-tab-panel
                key={item.name}
                name={item.name}
              >
                <template slot='label'>
                  <span>{item.label}</span>
                  <span>{`(${item.count})`}</span>
                </template>
                <div class='panel-content'>xxxx</div>
              </bk-tab-panel>
            ))}
          </bk-tab>
        </div>
        <div
          class='template-push-footer'
          slot='footer'
        >
          <bk-button
            class='mr-8 ml-24'
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.$t('一键生成')}
          </bk-button>
          <bk-button>{this.$t('取消')}</bk-button>
        </div>
      </bk-sideslider>
    );
  }
}
