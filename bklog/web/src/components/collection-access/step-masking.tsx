/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Button } from 'bk-magic-vue';
import MaskingField from '../../components/log-masking/masking-field';
import './step-masking.scss';
import $http from '../../api';

interface IProps {
  value: Boolean;
}

@Component
export default class StepMasking extends tsc<IProps> {
  @Prop({ type: String, required: true }) operateType: string;
  @Ref('maskingField') private readonly maskingFieldRef: HTMLElement; // 移动到分组实例
  submitLoading = false;
  /** 应用模式下 是否请求了接口 */
  isApplicationSubmit = false;

  get curCollect() {
    return this.$store.getters['collect/curCollect'];
  }

  get isShowJump() {
    return this.$route.query?.type !== 'masking';
  }

  @Emit('stepChange')
  emitStepChange() {
    if (this.isApplicationSubmit && !this.isShowJump) this.messageSuccess(this.$t('保存成功'));
    return this.isShowJump ? '' : 'back';
  }

  @Emit('changeSubmit')
  emitSubmitChange(val: boolean) {
    return val;
  }

  /** 提交脱敏 */
  async submitSelectRule(stepChange = false) {
    const data = (this.maskingFieldRef as any).getQueryConfigParams();
    const isUpdate = (this.maskingFieldRef as any).isUpdate;
    if (!data.field_configs.length && !isUpdate) {
      this.isApplicationSubmit = true;
      this.emitSubmitChange(true);
      this.emitStepChange();
      return;
    } // 非更新状态且没有任何字段选择规则 直接下一步
    let requestStr = isUpdate ? 'updateDesensitizeConfig' : 'createDesensitizeConfig';
    if (!data.field_configs.length && isUpdate) requestStr = 'deleteDesensitizeConfig'; // 无任何字段且是更新时 则删除当前索引集配置
    try {
      this.submitLoading = true;
      const res = await $http.request(`masking/${requestStr}`, {
        params: { index_set_id: this.curCollect?.index_set_id },
        data
      });
      this.$emit('changeIndexSetId', this.curCollect?.index_set_id || '');
      this.emitSubmitChange(true);
      if (res.result && stepChange) {
        this.isApplicationSubmit = true;
        this.emitStepChange();
      }
    } catch (err) {
      this.emitSubmitChange(false);
    } finally {
      this.submitLoading = false;
    }
  }

  /** 跳过 */
  handleNextPage() {
    this.emitSubmitChange(true);
    this.emitStepChange();
  }

  /** 取消 回到列表里 */
  cancelSelectRule() {
    this.$router.push({
      name: 'collection-item',
      query: {
        spaceUid: this.$store.state.spaceUid
      }
    });
  }

  render() {
    return (
      <div class='filed-masking-container'>
        <div class='masking-field-box'>
          <MaskingField
            ref='maskingField'
            collect-data={this.curCollect}
            operate-type={this.operateType}
            onChangeData={() => this.submitSelectRule()}
          />
        </div>
        <div class='submit-content'>
          <Button
            theme='primary'
            loading={this.submitLoading}
            onClick={() => this.submitSelectRule(true)}
          >
            {this.isShowJump ? this.$t('下一步') : this.$t('应用')}
          </Button>
          {this.isShowJump && (
            <Button
              theme='default'
              loading={this.submitLoading}
              onClick={() => this.handleNextPage()}
            >
              {this.$t('跳过')}
            </Button>
          )}
          <Button
            theme='default'
            onClick={() => this.cancelSelectRule()}
          >
            {this.$t('取消')}
          </Button>
        </div>
      </div>
    );
  }
}
