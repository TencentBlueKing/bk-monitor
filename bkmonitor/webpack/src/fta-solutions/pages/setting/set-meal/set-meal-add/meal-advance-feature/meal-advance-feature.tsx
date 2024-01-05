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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import VerifyItem from '../../../../../components/verify-item/verify-item';
import SetMealAddModule from '../../../../../store/modules/set-meal-add';
import NoticeMode from '../notice-mode/notice-mode';

import './meal-advance-feature.scss';

interface IFailedRetry {
  timeout: number | string;
}
interface IConvergeConfig {
  timedelta: number | string;
  count: number | string;
  condition: number;
  convergeFunc: string;
  dimension: Array<{ dimession: string; value: Array<any> }>;
}
interface IMealAdvanceFeature {
  failedRetry: IFailedRetry;
  convergeConfig: IConvergeConfig;
  mealType: string | number;
}
@Component({
  name: 'MealAdvanceFeature'
})
export default class MealAdvanceFeature extends tsc<IMealAdvanceFeature> {
  @Prop() public failedRetry: IFailedRetry;
  @Prop() public convergeConfig: IConvergeConfig;
  @Prop() public mealType: string | number;

  @Ref('noticeMode') readonly noticeModeEl: NoticeMode;

  errorMsg = {
    timeout: '',
    timedelta: '',
    count: '',
    notifyConfig: ''
  };
  customName = {
    title: `${window.i18n.t('执行阶段')}`,
    fatal: `${window.i18n.t('失败时')}`,
    warning: `${window.i18n.t('成功时')}`,
    info: `${window.i18n.t('执行前')}`
  };

  get getMealType(): number {
    return +SetMealAddModule.getMealType;
  }

  // 收敛方法
  get getConvergeFunctions() {
    return SetMealAddModule.getConvergeFunctions.filter(item =>
      this.getMealType === 1 ? item.key === 'collect' : item.key !== 'collect'
    );
  }

  // 收敛维度
  get getDimensions() {
    return SetMealAddModule.getDimensions;
  }

  // 通知方式
  get noticeWayList() {
    return SetMealAddModule.noticeWayList;
  }

  // 是否显示通知方式
  get showNoticeMode() {
    return !SetMealAddModule.isNotice;
  }

  // 初始通知方式配置
  get notifyConfig() {
    return SetMealAddModule.notifyConfig;
  }

  // 告警通知
  get isNotice() {
    return SetMealAddModule.isNotice;
  }

  @Emit('notice-change')
  onNoticeChange(v) {
    if (this.noticeModeEl?.validator()) this.errorMsg.notifyConfig = '';
    return v;
  }

  validator() {
    if (!this.isNotice && !this?.noticeModeEl.validator(false)?.isPass) {
      this.errorMsg.notifyConfig = this?.noticeModeEl.validator(false)?.msg;
      return false;
    }
    if (this.failedRetry.timeout === '') {
      this.errorMsg.timeout = this.$tc('必填项');
      return false;
    }
    if (this.failedRetry.timeout <= 0) {
      this.errorMsg.timeout = this.$tc('填写正整数');
      return false;
    }
    if (this.convergeConfig.timedelta === '') {
      this.errorMsg.timedelta = this.$tc('必填项');
      return false;
    }
    if (this.convergeConfig.timedelta < 0) {
      this.errorMsg.timedelta = this.$tc('填写非负整数');
      return false;
    }
    if (this.convergeConfig.count === '') {
      this.errorMsg.count = this.$tc('必填项');
      return false;
    }
    if (this.convergeConfig.count < 0) {
      this.errorMsg.count = this.$tc('填写非负整数');
      return false;
    }

    return true;
  }
  clearError(key, v) {
    if (!v) return;
    this.errorMsg[key] = '';
  }

  // 失败处理
  handleFail() {
    return (
      <div class={['config-item', this.showNoticeMode ? 'mt24' : 'mt16']}>
        <span class='title'>{this.$t('超时设置')}：</span>
        <div class='content'>
          <i18n path='当执行{0}分钟 未结束按失败处理'>
            <div class='input-wrapper-small'>
              <VerifyItem
                class='verify-item'
                errorMsg={this.errorMsg.timeout}
              >
                <bk-input
                  class='input-inline'
                  v-model={this.failedRetry.timeout}
                  behavior={'simplicity'}
                  type={'number'}
                  onChange={v => this.clearError('timeout', v)}
                ></bk-input>
              </VerifyItem>
            </div>
          </i18n>
          {/* <i18n path="分钟"></i18n>
          <i18n path="未结束按失败处理"></i18n>。 */}
        </div>
      </div>
    );
  }
  // 收敛规则
  convergenceRule() {
    return (
      <div class='config-item'>
        <span class='title'>{this.$t('防御规则')}：</span>
        <div class='content'>
          <i18n path='当遇到相同的{0}, 在{1}分钟内触发{2}条以上,进行{3}收敛'>
            <div class='select-wrapper-small'>
              <bk-select
                class='select-inline'
                search-with-pinyin={true}
                multiple
                popover-min-width={140}
                v-model={this.convergeConfig.dimension}
                behavior={'simplicity'}
                clearable={false}
                searchable
              >
                {this.getDimensions.map(option => (
                  <bk-option
                    key={option.key}
                    id={option.key}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
            </div>
            <div class='input-wrapper-small'>
              <VerifyItem
                class='verify-item'
                errorMsg={this.errorMsg.timedelta}
              >
                <bk-input
                  class='input-inline'
                  v-model={this.convergeConfig.timedelta}
                  behavior={'simplicity'}
                  type={'number'}
                  onChange={v => this.clearError('timedelta', v)}
                ></bk-input>
              </VerifyItem>
            </div>
            <div class='input-wrapper-small'>
              <VerifyItem
                class='verify-item'
                errorMsg={this.errorMsg.count}
              >
                <bk-input
                  class='input-inline'
                  v-model={this.convergeConfig.count}
                  behavior={'simplicity'}
                  type={'number'}
                  onChange={v => this.clearError('count', v)}
                ></bk-input>
              </VerifyItem>
            </div>
            <div class='select-wrapper-small'>
              <bk-select
                class='select-inline'
                popover-min-width={140}
                v-model={this.convergeConfig.convergeFunc}
                behavior={'simplicity'}
                clearable={false}
                searchable
              >
                {this.getConvergeFunctions.map(option => (
                  <bk-option
                    key={option.key}
                    id={option.key}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
            </div>
          </i18n>
        </div>
      </div>
    );
  }
  render() {
    return (
      <div class='meal-advance-feature'>
        {this.showNoticeMode ? (
          <VerifyItem errorMsg={this.errorMsg.notifyConfig}>
            <NoticeMode
              ref='noticeMode'
              on-notice-change={this.onNoticeChange}
              noticeWay={this.noticeWayList}
              notifyConfig={this.notifyConfig}
              customName={this.customName}
            ></NoticeMode>
          </VerifyItem>
        ) : undefined}
        {this.handleFail()}
        {this.convergenceRule()}
      </div>
    );
  }
}
