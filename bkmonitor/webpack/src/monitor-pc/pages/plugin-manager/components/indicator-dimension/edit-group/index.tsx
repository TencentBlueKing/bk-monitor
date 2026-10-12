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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import VerifyInput from '../../../../../components/verify-input/verify-input.vue';

import { GROUP_DEFAULT_NAME, GROUP_NAME_REGX, type IGroupSubmitPayload } from '../types';

import './index.scss';

interface IEmits {
  onCancel: () => void;
  onGroupSubmit: (payload: IGroupSubmitPayload) => void;
}

interface IProps {
  confirmLoading?: boolean;
  groupInfo: IGroupSubmitPayload;
  isEdit: boolean;
  isShow: boolean;
  nameList: string[];
}

@Component
export default class PluginEditGroup extends tsc<IProps, IEmits> {
  @Prop({ default: false }) isShow: boolean;
  @Prop({ default: false }) isEdit: boolean;
  @Prop({ default: false }) confirmLoading: boolean;
  @Prop({ default: () => ({}) }) groupInfo: IGroupSubmitPayload;
  @Prop({ default: () => [] }) nameList: string[];

  localInfo: IGroupSubmitPayload = {
    isEdit: false,
    table_name: '',
    table_desc: '',
    rule_list: [],
    fields: [],
  };
  isNameEmpty = false;

  @Watch('isShow')
  handleShowChange(val: boolean) {
    if (val) {
      this.localInfo = {
        isEdit: this.isEdit,
        oldName: this.groupInfo.oldName,
        table_name: this.groupInfo.table_name || '',
        table_desc: this.groupInfo.table_desc || '',
        rule_list: [...(this.groupInfo.rule_list || [])],
        fields: [...(this.groupInfo.fields || [])],
      };
      this.isNameEmpty = false;
    }
  }

  handleValidateName() {
    this.isNameEmpty =
      !GROUP_NAME_REGX.test(this.localInfo.table_name) || this.localInfo.table_name === GROUP_DEFAULT_NAME;
  }

  handleValueChange(v: boolean) {
    if (!v) {
      this.handleCancel();
    }
  }

  handleConfirm() {
    if (this.confirmLoading) {
      return;
    }
    this.handleValidateName();
    if (this.isNameEmpty) {
      return;
    }
    const isConflict = this.nameList.some(name => {
      if (this.isEdit) {
        return name === this.localInfo.table_name && name !== this.groupInfo.oldName;
      }
      return name === this.localInfo.table_name;
    });
    if (isConflict) {
      this.$bkMessage({ theme: 'error', message: `${this.$t('注意: 名字冲突')}` });
      return;
    }
    this.$emit('groupSubmit', {
      ...this.localInfo,
      isEdit: this.isEdit,
      table_desc: this.localInfo.table_desc || this.localInfo.table_name,
      fields: this.localInfo.fields || [],
    });
  }

  handleCancel() {
    if (this.confirmLoading) {
      return;
    }
    this.$emit('cancel');
  }

  render() {
    return (
      <bk-dialog
        width={480}
        class='plugin-metric-edit-group-dialog'
        header-position='left'
        mask-close={false}
        show-footer={false}
        title={this.isEdit ? this.$t('编辑指标分类') : this.$t('增加指标分类')}
        value={this.isShow}
        on-after-leave={this.handleCancel}
        on-value-change={this.handleValueChange}
      >
        <div class='metric-name'>
          <div class='hint'>
            <i class='icon-monitor icon-hint' />
            {this.$t('指标分类的定义影响指标检索的时候,如试图查看，仪表盘添加视图和添加监控策略时选择指标的分类。')}
          </div>
          <p class='item required'>{this.$t('名称')}</p>
          <VerifyInput
            class='verify-input'
            show-validate={this.isNameEmpty}
            validator={{ content: this.$tc('输入指标名,以字母开头,允许包含下划线和数字且不能为group_default') }}
          >
            <bk-input
              v-model={this.localInfo.table_name}
              placeholder={this.$t('英文名')}
              on-blur={this.handleValidateName}
            />
          </VerifyInput>
          <p class='item'>{this.$t('别名')}</p>
          <VerifyInput class='verify-input'>
            <bk-input
              v-model={this.localInfo.table_desc}
              placeholder={this.$t('别名')}
            />
          </VerifyInput>
          <p class='item'>{this.$t('匹配规则')}</p>
          <VerifyInput>
            <bk-tag-input
              v-model={this.localInfo.rule_list}
              style={{ width: '100%' }}
              allow-auto-match={true}
              allow-create={true}
              free-paste={true}
              placeholder={this.$t('匹配规则')}
              show-clear-only-hover={true}
            />
          </VerifyInput>
          <p class='rule-desc'>{this.$tc('支持JS正则匹配方式， 如子串前缀匹配go_，模糊匹配(.*?)_total')}</p>
        </div>
        <div class='footer'>
          <bk-button
            class='confirm-btn'
            disabled={this.confirmLoading}
            loading={this.confirmLoading}
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button
            disabled={this.confirmLoading}
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
