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

import TemplateEdit from './template-edit';
import TemplatePush from './template-push';

import './template-details.scss';

interface IProps {
  show?: boolean;
  onShowChange?: (v: boolean) => void;
}

@Component
export default class TemplateDetails extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;

  tabList = [
    {
      label: '基本信息',
      name: 'basic',
    },
    {
      label: '关联服务 & 告警',
      name: 'service',
    },
  ];
  tabActive = 'basic';

  templatePush = {
    show: false,
  };
  templateEdit = {
    show: false,
  };

  handleShowChange(v: boolean) {
    this.$emit('showChange', v);
  }

  handleChangeTab(name) {
    this.tabActive = name;
  }

  handleShowTemplatePush() {
    this.templatePush.show = true;
  }
  handleShowTemplateEdit() {
    this.templateEdit.show = true;
  }

  render() {
    return (
      <bk-sideslider
        width={640}
        ext-cls={'template-details-side-component'}
        before-close={() => {
          this.handleShowChange(false);
        }}
        isShow={this.show}
        quick-close
      >
        <div
          class='template-details-header'
          slot='header'
        >
          <span class='header-left'>
            <span class='header-title'>{this.$t('模板详情')}</span>
            <span class='split-line' />
            <span class='header-desc'>主调成功率</span>
          </span>
          <span class='header-right'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={() => {
                this.handleShowTemplatePush();
              }}
            >
              {this.$t('下发')}
            </bk-button>
            <bk-button
              theme='primary'
              outline
              onClick={() => {
                this.handleShowTemplateEdit();
              }}
            >
              {this.$t('编辑')}
            </bk-button>
          </span>
        </div>
        <div
          class='template-details-content'
          slot='content'
        >
          <div class='tabs'>
            {this.tabList.map(item => (
              <div
                key={item.name}
                class={['tab-item', { active: this.tabActive === item.name }]}
                onClick={() => this.handleChangeTab(item.name)}
              >
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div class='tab-content'>
            {(() => {
              switch (this.tabActive) {
                case 'basic':
                  return <div>基本信息</div>;
                case 'service':
                  return <div>关联服务 & 告警</div>;
                default:
                  return undefined;
              }
            })()}
          </div>
          <TemplatePush
            show={this.templatePush.show}
            onShowChange={v => {
              this.templatePush.show = v;
            }}
          />
          <TemplateEdit
            show={this.templateEdit.show}
            onShowChange={v => {
              this.templateEdit.show = v;
            }}
          />
        </div>
      </bk-sideslider>
    );
  }
}
