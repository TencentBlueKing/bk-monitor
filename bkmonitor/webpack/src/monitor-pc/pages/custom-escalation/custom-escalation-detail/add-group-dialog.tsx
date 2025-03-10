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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './add-group-dialog.scss';

enum EPreviewFlag {
  Preview_Changed = 3,
  Preview_Not_Started = 1,
  Preview_Started = 2,
}

@Component
export default class AddGroupDialog extends tsc<any, any> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ default: false, type: Boolean }) isEdit: boolean;

  groupInfo = {
    name: '',
    rules: '',
  };
  matchedMetrics = [];

  previewBtnFlag = EPreviewFlag.Preview_Not_Started;

  get disabled() {
    return (
      !this.groupInfo.name ||
      (this.groupInfo.rules && this.previewBtnFlag === EPreviewFlag.Preview_Not_Started) ||
      this.previewBtnFlag === EPreviewFlag.Preview_Changed ||
      false
    );
  }

  async handlePreview() {
    if (!this.groupInfo.rules) {
      this.previewBtnFlag = EPreviewFlag.Preview_Not_Started;
      this.matchedMetrics = [];
      return;
    }
    // getGroupRulePreviews
    const { auto_metrics: autoMetrics } = await this.$store.dispatch('custom-escalation/getGroupRulePreviews', {
      time_series_group_id: this.$route.params.id,
      // manual_list: ['cpu_load'],
      auto_rules: [this.groupInfo.rules],
    });
    this.previewBtnFlag = EPreviewFlag.Preview_Started;
    this.matchedMetrics = autoMetrics[0]?.metrics || [];
  }

  handleRulesChange() {
    if (this.previewBtnFlag === EPreviewFlag.Preview_Not_Started) return;
    this.previewBtnFlag = EPreviewFlag.Preview_Changed;
  }

  handleSubmit() {
    // TODO
    this.clear();
  }
  clear() {
    console.log('触发');
    this.groupInfo = {
      name: '',
      rules: '',
    };
    this.previewBtnFlag = EPreviewFlag.Preview_Not_Started;
  }
  @Emit('show')
  handleCancel() {
    // TODO
    this.clear();
    return false;
  }

  getPreviewCmp() {
    const previewMap = {
      [EPreviewFlag.Preview_Changed]: () => (
        <div class='search-content'>
          <span class='metric-change'>
            {' '}
            <i class='icon-monitor icon-hint' />
            {this.$t('匹配规则已变更，请重新预览。')}
          </span>
        </div>
      ),
      [EPreviewFlag.Preview_Not_Started]: () => undefined,
      [EPreviewFlag.Preview_Started]: () => {
        return this.matchedMetrics.length ? (
          <div class='search-content'>
            {this.matchedMetrics.map(metric => (
              <span
                key={metric}
                class='metric-item'
              >
                {metric}
              </span>
            ))}
          </div>
        ) : (
          <div class='non-metric'>{`（${this.$t('暂无匹配到的指标')}）`}</div>
        );
      },
    };
    return previewMap[this.previewBtnFlag]();
  }
  render() {
    return (
      <bk-dialog
        width={480}
        extCls={'custom-metric-group-dialog'}
        after-leave={this.clear}
        header-position='left'
        mask-close={true}
        title={this.isEdit ? this.$t('编辑分组') : this.$t('新建分组')}
        value={this.show}
        on-cancel={this.handleCancel}
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
                  v-model={this.groupInfo.name}
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
                  v-model={this.groupInfo.rules}
                  placeholder={this.$t('请输入')}
                  rows={2}
                  type='textarea'
                  onChange={this.handleRulesChange}
                />
                <div class='tip-msg'>{this.$t('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total')}</div>
              </bk-form-item>
            }
          </bk-form>
          <bk-button
            ext-cls='btn'
            outline={true}
            theme='primary'
            onClick={this.handlePreview}
          >
            {this.$t('预览')}
          </bk-button>
          {this.getPreviewCmp()}
        </div>
        <div slot='footer'>
          <bk-button
            style={{ 'margin-right': '8px' }}
            disabled={this.disabled}
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
