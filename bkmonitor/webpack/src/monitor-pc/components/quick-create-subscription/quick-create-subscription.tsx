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
import { Component, Model } from 'vue-property-decorator';
import { Component as tsc, ofType } from 'vue-tsx-support';

import CreateSubscriptionForm from './create-subscription-form';

import './quick-create-subscription.scss';

interface IProps {
  value: boolean;
}

@Component({
  components: {
    CreateSubscriptionForm
  }
})
class QuickCreateSubscription extends tsc<IProps> {
  @Model('change', { type: Boolean }) value: IProps['value'];
  handleSave() {
    (this.$refs.refOfCreateSubscriptionForm as any)
      ?.validateAllForms?.()
      .then(response => {
        console.log(response);
      })
      .catch(console.log);
  }
  render() {
    return (
      <div>
        <bk-sideslider
          is-show={this.value}
          width='960'
          ext-cls='quick-create-subscription-slider'
          transfer
          title={this.$t('新增订阅')}
          before-close={() => {
            this.$emit('change', false);
          }}
        >
          <div slot='content'>
            <div class='quick-create-subscription-slider-container'>
              {/* @ts-ignore */}
              <CreateSubscriptionForm
                ref='refOfCreateSubscriptionForm'
                mode='quick'
              ></CreateSubscriptionForm>
            </div>
            <div class='footer-bar'>
              <bk-button
                theme='primary'
                style={{ width: '88px', marginRight: '8px' }}
                onClick={this.handleSave}
              >
                {window.i18n.t('保存')}
              </bk-button>
              <bk-dropdown-menu
                trigger='click'
                placement='top-start'
              >
                <bk-button
                  theme='primary'
                  outline
                  slot='dropdown-trigger'
                  style={{ width: '88px', marginRight: '8px' }}
                >
                  {window.i18n.t('测试发送')}
                </bk-button>

                <ul
                  class='bk-dropdown-list'
                  slot='dropdown-content'
                >
                  <li>
                    <a href='javascript:;'>{window.i18n.t('给自己')}</a>
                  </li>
                  <li>
                    <a href='javascript:;'>{window.i18n.t('给全员')}</a>
                  </li>
                </ul>
              </bk-dropdown-menu>
              <bk-button
                style={{ width: '88px' }}
                onClick={() => (this.value = false)}
              >
                {window.i18n.t('取消')}
              </bk-button>
            </div>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
export default ofType().convert(QuickCreateSubscription);
