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
import type { PropType } from 'vue';

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './add-group-dialog.scss';

enum EPreviewFlag {
  Preview_Changed = 3,
  Preview_Not_Started = 1,
  Preview_Started = 2,
}

interface IGroupConfig {
  auto_rules?: string[];
  manual_list?: string[];
  name: string;
}
interface IGroupInfo {
  manualList: string[];
  name: string;
  rules: string;
}

@Component
export default class AddGroupDialog extends tsc<any> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  @Prop({ default: () => ({ name: '', rules: '' }), type: Object as PropType<IGroupInfo> }) groupInfo;
  @Prop({ default: () => [] }) nameList;
  @Prop({ default: () => [] }) metricList;
  @Ref() groupRef;
  localGroupInfo: IGroupInfo = { name: '', rules: '', manualList: [] };

  matchedMetrics = [];

  /** 分组表单规则 */
  rules = {
    name: [
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'blur',
      },
      {
        validator: this.checkGroupName,
        message: window.i18n.t('注意: 名字冲突'),
        trigger: 'blur',
      },
      {
        validator: this.checkGroupRepeat,
        message: window.i18n.t('输入中文、英文、数字、下划线类型的字符'),
        trigger: 'blur',
      },
    ],
  };

  /** 预览按钮状态：未预览、需重新预览、已预览 */
  previewBtnFlag = EPreviewFlag.Preview_Not_Started;

  /**
   * 获取指标名称列表
   */
  get metricNameList(): Array<{ description: string; name: string }> {
    return this.metricList.map(item => ({ name: item.name, description: item.description }));
  }

  get disabled() {
    return (
      !this.localGroupInfo.name ||
      (this.localGroupInfo.rules && this.previewBtnFlag === EPreviewFlag.Preview_Not_Started) ||
      !this.checkGroupName() ||
      !this.checkGroupRepeat() ||
      this.previewBtnFlag === EPreviewFlag.Preview_Changed ||
      false
    );
  }

  get disabledTips() {
    if (!this.localGroupInfo.name) {
      return this.$t('请输入名称');
    }
    if (!this.checkGroupName()) {
      return this.$t('名称重复');
    }
    if (!this.checkGroupRepeat()) {
      return this.$t('输入中文、英文、数字、下划线类型的字符');
    }
    if (this.localGroupInfo.rules && this.previewBtnFlag === EPreviewFlag.Preview_Not_Started) {
      return this.$t('已有规则，请先预览');
    }
    if (this.previewBtnFlag === EPreviewFlag.Preview_Changed) {
      return this.$t('匹配规则已变更，请重新预览。');
    }
    return '';
  }

  @Watch('groupInfo', { immediate: true, deep: true })
  handleGroupInfoChange(newVal: IGroupInfo) {
    this.localGroupInfo = { ...newVal };
  }

  /** 校验分组名称是否重名 */
  checkGroupName() {
    const groupNames = this.nameList.filter(name => name !== this.groupInfo.name);
    return !groupNames.includes(this.localGroupInfo.name);
  }
  /** 校验分组名称是否符合正则规范 */
  checkGroupRepeat() {
    return /^[\u4E00-\u9FA5A-Za-z0-9_-]+$/g.test(this.localGroupInfo.name);
  }
  /** 点击预览 */
  async handlePreview() {
    if (!this.localGroupInfo.rules) {
      this.previewBtnFlag = EPreviewFlag.Preview_Not_Started;
      this.matchedMetrics = [];
      return;
    }
    const { auto_metrics: autoMetrics } = await this.$store.dispatch('custom-escalation/getGroupRulePreviews', {
      time_series_group_id: this.$route.params.id,
      auto_rules: [this.localGroupInfo.rules],
    });
    this.previewBtnFlag = EPreviewFlag.Preview_Started;

    const autoMetricsMapped = (autoMetrics[0]?.metrics || []).map(metricName => {
      const metric = this.metricList.find(m => m.name === metricName) || { name: metricName, description: '' };
      return { name: metric.name, description: metric.description };
    });

    // 合并自动指标和手动选择的列表，并去重（手动列表项优先）
    const combinedMetrics = [...autoMetricsMapped, ...this.localGroupInfo.manualList.map(name => ({ name }))];
    const metricMap = new Map();
    combinedMetrics.forEach(metric => {
      metricMap.set(metric.name, metric);
    });
    this.matchedMetrics = Array.from(metricMap.values());
  }
  /** 规则改变 */
  handleRulesChange() {
    if (this.previewBtnFlag === EPreviewFlag.Preview_Not_Started) return;
    if (!this.localGroupInfo.rules) {
      this.matchedMetrics = [];
      this.previewBtnFlag = EPreviewFlag.Preview_Not_Started;
    }
    this.previewBtnFlag = EPreviewFlag.Preview_Changed;
  }
  /** 提交分组 */
  handleSubmit() {
    const config: IGroupConfig = {
      name: this.localGroupInfo.name,
      manual_list: this.localGroupInfo.manualList,
    };
    if (this.localGroupInfo.rules) {
      config.auto_rules = [this.localGroupInfo.rules];
    }
    this.$emit('groupSubmit', config);
    this.clear();
  }
  /** 取消添加分组 */
  @Emit('cancel')
  handleCancel() {
    this.clear();
    return false;
  }
  /** 初始化相关数据 */
  clear() {
    this.groupRef?.clearError?.();
    this.localGroupInfo = {
      name: '',
      rules: '',
      manualList: [],
    };
    this.previewBtnFlag = EPreviewFlag.Preview_Not_Started;
  }
  /** 获取预览后的状态 */
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
            {this.matchedMetrics.map(({ name, description }) => (
              <span
                key={name}
                class='metric-item'
                v-bk-tooltips={{
                  content: name,
                }}
              >
                {description || name}
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
        onCancel={this.handleCancel}
      >
        <div class='group-content'>
          <bk-alert
            class='hint-alert'
            title={this.$t('分组 用于指标归类，建议拥有相同维度的指标归到一个组里。')}
          />
          <bk-form
            ref='groupRef'
            formType='vertical'
            {...{
              props: {
                model: this.localGroupInfo,
                rules: this.rules,
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
                  v-model={this.localGroupInfo.name}
                  placeholder={this.$t('请输入')}
                />
              </bk-form-item>
            }
            {
              <bk-form-item
                error-display-type='normal'
                label={this.$t('匹配规则')}
                property='rule'
              >
                <bk-input
                  v-model={this.localGroupInfo.rules}
                  placeholder={this.$t('请输入')}
                  rows={2}
                  type='textarea'
                  onChange={this.handleRulesChange}
                />
                <div class='tip-msg'>{this.$t('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total')}</div>
              </bk-form-item>
            }
            {
              <bk-form-item
                ext-cls='name'
                label={this.$t('手动添加')}
                property='manualList'
              >
                <bk-select
                  v-model={this.localGroupInfo.manualList}
                  displayTag
                  multiple
                  searchable
                >
                  {this.metricNameList.map(item => (
                    <bk-option
                      id={item.name}
                      key={item.name}
                      name={item.name}
                    />
                  ))}
                </bk-select>
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
          <div
            style={{ 'margin-right': '8px', display: 'inline-block' }}
            v-bk-tooltips={{ content: this.disabledTips, disabled: !this.disabled }}
          >
            <bk-button
              disabled={this.disabled}
              theme='primary'
              onClick={this.handleSubmit}
            >
              {this.isEdit ? this.$t('保存') : this.$t('提交')}
            </bk-button>
          </div>

          <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  }
}
