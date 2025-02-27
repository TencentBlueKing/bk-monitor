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

import './add-group-dialog.scss';

@Component
export default class AddGroupDialog extends tsc<any, any> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ default: false, type: Boolean }) isEdit: boolean;

  metrics = ['connections', 'connections1', 'connections2'];

  handleSubmit() {
    // TODO
  }
  handleCancel() {
    // TODO
  }
  render() {
    return (
      <bk-dialog
        width={430}
        extCls={'custom-metric-group-dialog'}
        header-position='left'
        mask-close={true}
        title={this.isEdit ? this.$t('编辑分组') : this.$t('新建分组')}
        value={this.show}
        on-cancel={() => this.$emit('show', false)}
      >
        <div class='group-content'>
          <bk-alert
            class='hint-alert'
            title={this.$t('分组 用于指标归类，建议拥有相同维度的指标归到一个组里。')}
          />
          <bk-form
            formType='vertical'
            {...{
              props: {
                // model: this.strategyConfig,
                // rules: this.rules,
              },
            }}
          >
            {
              <bk-form-item
                ext-cls='name'
                error-display-type='normal'
                label={this.$t('名称')}
                property='name'
                required
              >
                <bk-input
                  // v-model={this.strategyConfig.name}
                  placeholder={this.$t('请输入')}
                />
              </bk-form-item>
            }
            {
              <bk-form-item
                error-display-type='normal'
                label={this.$t('匹配规则')}
                property='name'
              >
                <bk-input
                  // v-model={this.strategyConfig.name}
                  placeholder={this.$t('请输入')}
                  rows={2}
                  type='textarea'
                />
                <div class='tip-msg'>{this.$t('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total')}</div>
              </bk-form-item>
            }
          </bk-form>
          <bk-button
            ext-cls='btn'
            outline={true}
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.$t('预览')}
          </bk-button>
          <div class='search-content'>
            {this.metrics.map(metric => (
              <span
                key={metric}
                class='metric-item'
              >
                {metric}
              </span>
            ))}
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            style={{ 'margin-right': '8px' }}
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.isEdit ? this.$t('保存') : this.$t('提交')}
          </bk-button>
          <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  }
}
