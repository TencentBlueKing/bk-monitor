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

import { Component, Emit, Prop, PropSync, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import Schema from 'async-validator';

import ErrorMsg from '../../../components/error-msg/error-msg';

import type { AnomalyDetectionBase, SchemeItem } from '../types';

import './single-indicator.scss';

interface SingleIndicatorProps {
  data: AnomalyDetectionBase;
  isEdit: boolean;
  isSingle?: boolean;
  schemeList: SchemeItem[];
}

@Component
export default class SingleIndicator extends tsc<SingleIndicatorProps> {
  @PropSync('data', { type: Object, required: true }) baseConfig: AnomalyDetectionBase;
  @Prop({ default: [], type: Array }) schemeList: SchemeItem[];
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  @Prop({ default: false, type: Boolean }) isSingle: boolean;

  @Ref('schemeSelect') schemeSelectEl;
  @Emit('change')
  handleBaseConfigChange() {
    return this.baseConfig;
  }

  // eslint-disable-next-line @typescript-eslint/member-ordering
  errorsMsg = {
    defaultPlanId: '',
  };

  handleFocusStrategyName() {
    this.schemeSelectEl.$refs?.input?.focus();
  }

  // 校验方法
  public validate(): Promise<any> {
    return new Promise((resolve, reject) => {
      const descriptor = {
        defaultPlanId: [{ required: true, message: this.$tc('必填项') }],
      };
      const validator = new Schema(descriptor);
      validator.validate({ defaultPlanId: this.baseConfig.default_plan_id }, {}, (errors, fields) => {
        if (!errors) {
          this.errorsMsg = { defaultPlanId: '' };
          resolve(null);
        } else {
          this.errorsMsg = { defaultPlanId: '' };
          for (const item of errors) {
            this.errorsMsg[item.field] = item.message;
          }
          this.handleFocusStrategyName();
          reject({ errors, fields });
        }
      });
    });
  }

  // 清除校验
  public clearErrorMsg() {
    this.errorsMsg = {
      defaultPlanId: '',
    };
  }

  render() {
    return (
      <div class='single-indicator-form'>
        {!this.isSingle && (
          <div class='single-indicator-item'>
            <div class='item-label'>{this.$t('是否启用')}</div>
            <div class='item-container no-width'>
              {this.isEdit ? (
                <bk-switcher
                  v-model={this.baseConfig.is_enabled}
                  behavior='simplicity'
                  disabled={!this.isEdit}
                  size='small'
                  theme='primary'
                  on-change={this.handleBaseConfigChange}
                />
              ) : (
                <span>{this.baseConfig.is_enabled ? this.$t('开启') : this.$t('关闭')}</span>
              )}
              <span class='right-tip'>
                <span class='icon-monitor icon-hint' />
                <span class='tip-text'>
                  {this.isSingle
                    ? this.$t('启用后可在监控策略中配置此类告警')
                    : this.$t('启用后将自动进行主机异常检测，也可在监控策略中配置此类告警')}
                </span>
              </span>
            </div>
          </div>
        )}
        {/* 通知对象 */}
        {this.$slots.notification && (
          <div class='single-indicator-item'>
            <div class='item-label'>{this.$t('关闭检测的对象')}</div>
            <div class='item-container'>{this.$slots.notification}</div>
          </div>
        )}
        {/* 默认方案 */}
        <div class={['single-indicator-item', { mb0: this.isSingle }]}>
          <div class='item-label item-required'>{this.$t(this.isSingle ? '默认方案' : '方案')}</div>
          <div class='item-container'>
            {this.isEdit ? (
              <ErrorMsg
                style='width: 100%;'
                message={this.errorsMsg.defaultPlanId}
              >
                <bk-select
                  ref='schemeSelect'
                  v-model={this.baseConfig.default_plan_id}
                  clearable={false}
                  disabled={!this.isEdit}
                  ext-popover-cls='scheme-select'
                  searchable
                  on-change={this.handleBaseConfigChange}
                >
                  {this.schemeList.map(item => (
                    <bk-option
                      id={item.id}
                      key={item.id}
                      style='width: 100%;'
                      name={item.name}
                    >
                      <bk-popover
                        style='width: 100%;'
                        ext-cls='programme-item-popover'
                        placement='right-end'
                        theme='light'
                      >
                        <div style='width: 100%;'>{item.name}</div>
                        <div slot='content'>
                          <div class='content-item'>
                            <span class='content-item-title'>{this.$t('依赖历史数据长度')}:</span>
                            <span>{item.ts_depend}</span>
                          </div>
                          <div class='content-item'>
                            <span class='content-item-title'>{this.$t('数据频率')}:</span>
                            <span>{item.ts_freq || this.$t('无限制')}</span>
                          </div>
                          <div class='content-item'>
                            <span class='content-item-title'>{this.$t('描述')}:</span>
                            <span class='content-item-description'>{item.description}</span>
                          </div>
                        </div>
                      </bk-popover>
                    </bk-option>
                  ))}
                </bk-select>
              </ErrorMsg>
            ) : (
              (() => {
                const name = this.schemeList.find(s => s.id === this.baseConfig.default_plan_id)?.name || '';
                return <span>{name}</span>;
              })()
            )}
          </div>
        </div>
        {/* 默认敏感度 */}
        {!this.isSingle && (
          <div class='single-indicator-item'>
            <div class='item-label item-required'>{this.$t('敏感度')}</div>
            <div class='item-container'>
              {this.isEdit ? (
                [
                  <bk-slider
                    key={1}
                    v-model={this.baseConfig.default_sensitivity}
                    disable={!this.isEdit}
                    max-value={10}
                    on-change={this.handleBaseConfigChange}
                  />,
                  <div
                    key={2}
                    class='sensitivity-tips'
                  >
                    <span>{this.$t('较少告警')}</span>
                    <span>{this.$t('较多告警')}</span>
                  </div>,
                ]
              ) : (
                <span>{this.baseConfig.default_sensitivity}</span>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }
}
