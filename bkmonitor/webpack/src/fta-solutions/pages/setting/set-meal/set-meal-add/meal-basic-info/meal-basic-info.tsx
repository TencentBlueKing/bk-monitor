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

import ResizeContainer from '../../../../../components/resize-container/resize-container';
import VerifyItem from '../../../../../components/verify-item/verify-item';

import './meal-basic-info.scss';

const { i18n } = window;

interface IMealBasicInfo {
  basicInfo: IBasicInfo;
  type?: 'add' | 'edit';
}
interface IBasicInfo {
  bizId: number;
  name: string;
  asStrategy: number;
  enable: boolean;
  desc: string;
}

@Component({
  name: 'MealBasicInfo'
})
export default class MealBasicInfo extends tsc<IMealBasicInfo> {
  @Prop() public basicInfo: IBasicInfo;
  @Prop({ default: 'add', type: String }) type: string;

  $refs!: {
    basicInfoRef: any;
    mealNameRef: any;
  };

  errorMsg = {
    name: ''
  };

  private rules = {
    name: [
      {
        required: true,
        message: i18n.t('必填项'),
        trigger: 'blur'
      }
    ]
  };

  get bizList() {
    return this.$store.getters.bizList;
  }

  // 校验
  async validataForm(callback) {
    await this.$refs.basicInfoRef.validate().then(
      () => {
        callback();
      },
      () => {
        this.$refs.mealNameRef.focus();
      }
    );
  }

  validator() {
    if (this.basicInfo.name === '') {
      this.errorMsg.name = this.$tc('必填项');
      return false;
    }
    return true;
  }
  /**
   * @description: 跳转策略列表
   * @param {*} row 表格行数据
   * @return {*}
   */
  handleToStrategyList() {
    if (!this.basicInfo.asStrategy) return;
    this.$router.push({
      name: 'strategy-config',
      params: {
        actionName: this.basicInfo.name
      }
    });
  }

  protected render() {
    return (
      <div class='meal-basic-info'>
        <bk-form
          {...{
            props: {
              labelWidth: 0,
              model: this.basicInfo,
              rules: this.rules
            }
          }}
          ref='basicInfoRef'
        >
          <div class='info-item-top'>
            <div class='info-item auto'>
              <div class='item-title'>{this.$t('业务')}</div>
              <div class='item-input'>
                <bk-select
                  v-model={this.basicInfo.bizId}
                  searchable
                  clearable={false}
                  readonly
                  behavior={'simplicity'}
                >
                  {this.bizList.map((option, index) => (
                    <bk-option
                      key={index}
                      id={option.id}
                      name={option.text}
                    ></bk-option>
                  ))}
                </bk-select>
              </div>
            </div>
            <div class='info-item auto'>
              <div class='item-title required'>
                <span class='required'>{this.$t('套餐名称')}</span>
              </div>
              <div class='item-input'>
                {/* <bk-form-item property={'name'} error-display-type={'normal'} required={true}> */}
                <VerifyItem errorMsg={this.errorMsg.name}>
                  <bk-input
                    ref='mealNameRef'
                    maxlength={128}
                    minlength={1}
                    v-model={this.basicInfo.name}
                    behavior={'simplicity'}
                    onChange={v => v && (this.errorMsg.name = '')}
                  ></bk-input>
                </VerifyItem>
                {/* </bk-form-item> */}
              </div>
            </div>
            {this.type !== 'add' && (
              <div class='info-item glcl'>
                <div class='item-title'>{this.$t('关联策略')}</div>
                <div class={['item-input', { link: this.basicInfo.asStrategy > 0 }]}>
                  <span onClick={this.handleToStrategyList}>
                    {this.basicInfo.asStrategy > 0 ? this.basicInfo.asStrategy : '--'}
                  </span>
                </div>
              </div>
            )}
            <div class='info-item'>
              <div class='item-title'>{this.$t('是否启用')}</div>
              <div class='item-input'>
                <bk-switcher
                  v-model={this.basicInfo.enable}
                  theme={'primary'}
                ></bk-switcher>
              </div>
            </div>
          </div>
          <div class='info-item-bottom'>
            <div class='item-title'>{this.$t('说明')}</div>
            <div class='item-input'>
              <ResizeContainer
                minHeight={64}
                maxHeight={500}
                minWidth={200}
              >
                <bk-input
                  class='textarea'
                  type={'textarea'}
                  placeholder={this.$t('输入套餐说明')}
                  maxlength={200}
                  v-model={this.basicInfo.desc}
                ></bk-input>
              </ResizeContainer>
            </div>
          </div>
        </bk-form>
      </div>
    );
  }
}
