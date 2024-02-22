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

import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Inject, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from '../../../monitor-common/utils/utils';
import ExpiredSelect from '../../components/expired-select/expired-select';
import { IUnitItme } from '../../pages/application/app-configuration/type';
import VerifyItem from '../verify-item/verify-item';

import './editable-form-item.scss';

interface IEditableFormItemProps {
  value: any;
  label?: string | TranslateResult;
  selectEditValue?: any; // 下拉编辑选值
  selectEditOption?: Array<{}>; // 下拉编辑options
  formType?: IFormType; // 表单类型
  unit?: string; // 单位
  showEditable?: boolean; // 是否显示编辑icon
  showLabel?: boolean; // 是否显示label
  validator?: any; // 检验规则
  tooltips?: string | TranslateResult; // tooltip提示内容
  maxExpired?: Number; // 过期时间最大限制
  selectList?: Array<{}>; // select类型下拉 options
  unitList?: IUnitItme[]; // 单位列表
  authority?: boolean; // 编辑权限
  authorityName?: string; // 权限名称
  tagTheme?: string;
  updateValue?: (val) => void; // 确认提交
  onEditChange?: (val) => void; // 编辑表单值改变时
  preCheckSwitcher?: (val) => Promise<any>; // Switcher 开关预检查
}

interface IEditableFormItemEvent {
  onUpdateValue: string;
}

type IFormType = 'input' | 'select' | 'unit' | 'switch' | 'tag' | 'password' | 'expired' | 'selectEdit';

@Component
export default class EditableFormItem extends tsc<IEditableFormItemProps, IEditableFormItemEvent> {
  @Prop({ type: Boolean, default: true }) showEditable: boolean;
  @Prop({ type: String, default: '' }) label: string;
  @Prop({ type: String, default: 'input' }) formType: IFormType;
  @Prop({ type: String, default: '' }) unit: string;
  @Prop({ type: String, default: '' }) tooltips: string;
  @Prop({ type: Boolean, default: true }) showLabel: boolean;
  @Prop({ type: Boolean, default: true }) authority: boolean;
  @Prop({ type: String, default: '' }) authorityName: boolean;
  @Prop({ type: Number, required: false }) maxExpired: 0;
  @Prop({ type: Array, required: false }) selectEditOption: Array<any>;
  @Prop({ type: Array, required: false }) selectList: Array<any>;
  @Prop({ default: '', required: true }) value: any;
  @Prop({ required: false }) selectEditValue: any;
  @Prop({ default: '', type: String }) tagTheme: string;
  @Prop({ type: Array, default: () => [] }) unitList: IUnitItme[];
  @Prop() validator: (val) => void;
  @Prop() updateValue: (val) => {};
  @Prop() onEditChange: (val) => any;
  @Prop() preCheckSwitcher?: (val) => Promise<any>;

  @Ref('input') inputRef: any;

  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  lcoalValue = ''; // 编辑状态绑定值
  isEditing = false; // 编辑状态
  isSubmiting = false; // 提交loading状态
  showPasswordView = false; // 显示密码查看
  showPassword = true; // 密码显示隐藏
  secureKeyLoading = false;
  /** 校验的错误信息 */
  errorMsg = {
    value: ''
  };
  editCloneVal = '';
  editSubmitVal = '';

  get displayValue() {
    if (this.formType === 'select') {
      const selectItem = this.selectList.find(item => item.id === this.value);
      return selectItem ? selectItem.name : '';
    }
    if (this.formType === 'unit') {
      let txt = '';
      const target = this.unitList.find(group =>
        group.formats.find(option => {
          txt = option.id === this.value ? option.name : '';
          return option.id === this.value;
        })
      );
      return target ? txt : '';
    }
    return this.value === '' ? '--' : this.value;
  }

  /**
   * @description: 默认校验规则 必填
   */
  requiredValidator(val) {
    if (val.trim?.() === '') {
      return this.$t('注意: 必填字段不能为空');
    }
    return '';
  }
  /**
   * @desc 拷贝操作
   * @param { * } val
   */
  handleCopy(text) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }
  /**
   * @description: 校验规则
   */
  handleValidator() {
    // 过期时间,下拉框编辑无需此处校验
    if (['expired', 'selectEdit'].includes(this.formType)) return true;
    const apiFunc = this.validator ? 'validator' : 'requiredValidator';
    const valid = this[apiFunc](this.lcoalValue);
    if (valid) {
      this.errorMsg.value = valid;
      return false;
    }
    return true;
  }
  /**
   * @desc 获取 secureKey
   */
  async handleGetSecureKey() {
    this.secureKeyLoading = true;
    await this.updateValue(this.value);
    this.secureKeyLoading = false;
  }
  /**
   * @desc 表单值显示
   */
  handleDisplayValue() {
    switch (this.formType) {
      case 'switch': // switcher开关
        return (
          <bk-switcher
            v-authority={{ active: !this.authority }}
            theme='primary'
            value={this.value}
            pre-check={() => this.preCheckSwitcher(this.value)}
          />
        );
      case 'tag': // 标签
        return this.value.map(tag => <bk-tag theme={this.tagTheme}>{tag}</bk-tag>);
      case 'expired': // 过期时间
        return <span>{`${this.value}${this.$t('天')}`}</span>;
      case 'password': // 密码
        return this.value ? (
          <span class='password-content'>
            <span class={{ 'password-value': !this.showPassword }}>{this.showPassword ? this.value : '********'}</span>
            {this.showPassword && (
              <i
                class='icon-monitor icon-mc-copy copy-icon'
                onClick={() => this.handleCopy(this.value)}
              ></i>
            )}
            <span
              class={`bk-icon toggle-icon ${this.showPassword ? 'icon-eye-slash' : 'icon-eye'}`}
              onClick={() => (this.showPassword = !this.showPassword)}
            ></span>
          </span>
        ) : (
          <span class={['mask-content', { 'btn-loading': this.secureKeyLoading }]}>
            <span class='placeholder'>●●●●●●●●●●</span>
            {this.secureKeyLoading && <span class='loading'></span>}
            <span
              v-authority={{ active: !this.authority }}
              class='view-btn'
              // eslint-disable-next-line @typescript-eslint/no-misused-promises
              onClick={this.handleGetSecureKey}
            >
              {this.$t('点击查看')}
            </span>
          </span>
        );
      case 'selectEdit': // 多级select
        return (this.$scopedSlots as any).show ? (
          (this.$scopedSlots as any).show({ data: this.selectEditValue })
        ) : (
          <span>{this.lcoalValue}</span>
        );
      default:
        return (
          <span>
            {this.displayValue}
            {this.unit && <span class='unit'>{this.unit}</span>}
          </span>
        );
    }
  }
  /**
   * @desc 表单值编辑
   */
  handleEditValue() {
    switch (this.formType) {
      case 'tag':
        return;
      case 'expired':
        return (
          <ExpiredSelect
            class='edit-item expired-select'
            v-model={this.lcoalValue}
            max={this.maxExpired}
          />
        );
      case 'select':
        return (
          <bk-select
            class='edit-item select-item'
            v-model={this.lcoalValue}
            clearable={false}
            onChange={v => v && (this.errorMsg.value = '')}
          >
            {this.selectList.map(option => (
              <bk-option
                key={option.id}
                id={option.id}
                name={option.name}
              ></bk-option>
            ))}
          </bk-select>
        );
      case 'unit':
        return (
          <bk-select
            class='edit-item unit-select'
            v-model={this.lcoalValue}
            clearable={false}
            popover-width={180}
          >
            {this.unitList.map((group, index) => (
              <bk-option-group
                name={group.name}
                key={index}
              >
                {group.formats.map(option => (
                  <bk-option
                    key={option.id}
                    id={option.id}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-option-group>
            ))}
          </bk-select>
        );
      default:
        return (
          <bk-input
            ref='input'
            class='edit-item input-item'
            disabled={this.isSubmiting}
            v-model={this.lcoalValue}
            onChange={v => v && (this.errorMsg.value = '')}
          />
        );
    }
  }
  /**
   * @desc 点击编辑
   */
  async handleEditClick() {
    this.lcoalValue = this.value;
    if (this.formType === 'selectEdit' && this.selectEditValue) {
      this.editCloneVal = this.selectEditValue;
      this.editSubmitVal = this.selectEditValue;
      this.handleEditObjChange('edit');
    }
    this.isEditing = true;
    this.$nextTick(() => {
      if (this.formType === 'input') {
        this.inputRef.focus();
      }
    });
  }
  /**
   * @desc 编辑提交
   */
  async handleSubmit() {
    // 开关项已通过预检查操作更新
    if (this.formType === 'switch') return;

    if (this.handleValidator()) {
      this.isSubmiting = true;
      let res;
      if (this.formType === 'selectEdit') {
        res = await this.updateValue({
          selectValue: this.editSubmitVal,
          type: 'submit',
          activeItem: this.lcoalValue
        });
      } else {
        res = await this.updateValue(this.lcoalValue);
      }
      setTimeout(() => {
        this.isEditing = !Boolean(res);
        this.isSubmiting = false;
      }, 500);
    }
  }
  /**
   * @desc 取消编辑
   */
  handleCancel() {
    this.isEditing = false;
    this.handleEditObjChange('cancel');
  }
  /**
   * @desc: formType为selectEdit时展示下拉框
   */
  showEditSelect() {
    return (
      <div>
        <bk-select
          class='edit-item select-item'
          style='margin-right: 8px;'
          v-model={this.editSubmitVal}
          clearable={false}
          onChange={() => this.handleEditObjChange('select')}
        >
          {this.selectEditOption?.map(option => (
            <bk-option
              key={option.id}
              id={option.id}
              name={option.name}
            ></bk-option>
          ))}
        </bk-select>
      </div>
    );
  }
  /**
   * @desc: editObj值变化时
   */
  @Emit('editChange')
  handleEditObjChange(type: string) {
    return {
      selectValue: type === 'cancel' ? this.editCloneVal : this.editSubmitVal,
      type,
      activeItem: this.lcoalValue
    };
  }

  render() {
    return (
      <div class='editable-form-item'>
        {this.showLabel && (
          <label class='form-item-label'>
            <span
              class={{ 'tooltip-text': this.tooltips.length }}
              v-bk-tooltips={{ content: this.tooltips, disabled: !this.tooltips.length, allowHTML: false }}
            >
              {this.label}
            </span>
          </label>
        )}
        <div class='form-item-value'>
          <div class='value-content'>
            {!this.isEditing && this.handleDisplayValue()}
            {this.isEditing && (
              <div class='select-content'>
                {this.formType === 'selectEdit' && this.showEditSelect()}
                {(this.$scopedSlots as any).edit ? (
                  (this.$scopedSlots as any).edit({ data: this.editSubmitVal })
                ) : (
                  <VerifyItem
                    class='verify-item'
                    errorMsg={this.errorMsg.value}
                  >
                    {this.handleEditValue()}
                  </VerifyItem>
                )}
              </div>
            )}
          </div>
          {(this.showEditable || this.isEditing) && this.formType !== 'switch' && (
            <div class='value-tool'>
              {this.isEditing ? (
                <div>
                  {this.isSubmiting ? (
                    <div class='loading'></div>
                  ) : (
                    <span>
                      <span
                        class='bk-icon icon-check-line'
                        // eslint-disable-next-line @typescript-eslint/no-misused-promises
                        onClick={this.handleSubmit}
                      ></span>
                      <span
                        class='bk-icon icon-close-line-2'
                        onClick={this.handleCancel}
                      ></span>
                    </span>
                  )}
                </div>
              ) : (
                <span
                  class='icon-monitor icon-bianji'
                  v-authority={{ active: !this.authority }}
                  onClick={() =>
                    this.authority ? this.handleEditClick() : this.handleShowAuthorityDetail(this.authorityName)
                  }
                ></span>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}
