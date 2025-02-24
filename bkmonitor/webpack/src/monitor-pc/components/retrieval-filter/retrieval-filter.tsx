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

import ResidentSetting from './resident-setting';
import UiSelector from './ui-selector';
import { EMode, type IFilterField, type IGetValueFnParams, type IWhereValueOptionsItem, MODE_LIST } from './utils';

import './retrieval-filter.scss';

interface IProps {
  fields: IFilterField[];
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
}

@Component
export default class RetrievalFilter extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;

  /* 展示常驻设置 */
  showResidentSetting = false;
  /* 当前查询模式 */
  mode = EMode.ui;
  /* 是否展开常驻设置 */
  residentSettingActive = false;

  handleChangeMode() {
    this.mode = this.mode === EMode.ui ? EMode.ql : EMode.ui;
  }
  handleShowResidentSetting() {
    this.residentSettingActive = !this.residentSettingActive;
  }
  render() {
    return (
      <div class='retrieval-filter__component'>
        <div class='retrieval-filter__component-main'>
          <div
            class='component-left'
            onClick={() => this.handleChangeMode()}
          >
            {MODE_LIST.filter(item => item.id === this.mode).map(item => [
              <span
                key={`${item.id}_0`}
                class='text'
              >
                {item.name}
              </span>,
              <div
                key={`${item.id}_1`}
                class='mode-icon'
              >
                <span class='icon-monitor icon-switch' />
              </div>,
            ])}
          </div>
          <div class='filter-content'>
            {this.mode === EMode.ui ? (
              <UiSelector
                fields={this.fields}
                getValueFn={this.getValueFn}
              />
            ) : undefined}
          </div>
          <div class='component-right'>
            {this.mode === EMode.ui && (
              <div
                class={['setting-btn', { 'btn-active': this.residentSettingActive }]}
                v-bk-tooltips={{
                  content: window.i18n.tc('常驻筛选'),
                  delay: 300,
                }}
                onClick={() => this.handleShowResidentSetting()}
              >
                <span class='icon-monitor icon-tongyishezhi' />
              </div>
            )}
            {false && (
              <div class='favorite-btn'>
                <span class='icon-monitor icon-mc-uncollect' />
              </div>
            )}
            <div class='search-btn'>
              <span class='icon-monitor icon-mc-search' />
            </div>
          </div>
        </div>
        {this.residentSettingActive && <ResidentSetting fields={this.fields} />}
      </div>
    );
  }
}
