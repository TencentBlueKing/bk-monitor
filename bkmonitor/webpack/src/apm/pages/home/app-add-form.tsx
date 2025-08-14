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
import { Component, Emit, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { checkDuplicateName } from 'monitor-api/modules/apm_meta';

import type { IAppSelectOptItem } from './app-select';

import './app-add-form.scss';

interface IProps {
  pluginId?: string;
  value?: boolean;
}
@Component
export default class AppAddForm extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ type: String, default: '' }) pluginId: IProps['pluginId'];
  @Ref() addForm: any;

  formData: ICreateAppFormData = {
    name: '',
    enName: '',
    desc: '',
    pluginId: '',
  };
  rules = {
    name: [
      {
        required: true,
        message: window.i18n.tc('输入应用名,1-50个字符'),
        trigger: 'blur',
      },
    ],
    enName: [
      {
        validator: val => /^[_|a-zA-Z][a-zA-Z0-9_]*$/.test(val) && val.length >= 5,
        message: window.i18n.t('输入5-50字符的字母开头、数字、下划线'),
        trigger: 'blur',
      },
    ],
  };
  /** 英文名是否重名 */
  existedName = false;

  /** 插件列表 */
  pluginsList: IAppSelectOptItem[] = [];

  /** 点击提交触发 */
  clickSubmit = false;

  created() {
    this.initData();
  }

  @Emit('change')
  handleShowChange(val?: boolean) {
    return val ?? !this.value;
  }

  /** 初始化页面数据 */
  initData() {
    this.rules.enName.push({
      message: window.i18n.tc('注意: 名字冲突'),
      trigger: 'none',
      validator: val => !this.existedName && !!val,
    });
  }

  /** 取消新增 */
  handleCancel() {
    this.addForm?.clearError?.();
    this.formData = {
      name: '',
      enName: '',
      desc: '',
      pluginId: '',
    };
    this.handleShowChange(false);
  }
  /** 跳转添加页面 */
  async handleConfirm() {
    /** 校验重名 */
    this.clickSubmit = true;
    const noExistedName = await this.handleCheckEnName(true);
    if (noExistedName) {
      const isPass = await this.addForm.validate();
      if (isPass) {
        this.handleShowChange(false);
        this.$router.push({
          name: 'application-add',
          params: {
            appInfo: JSON.stringify({ ...this.formData, ...{ pluginId: this.pluginId } }),
          },
        });
      }
    }
  }

  /** 检查英文名是否重名 */
  handleCheckEnName(isSubmit = false) {
    return new Promise((resolve, reject) => {
      if (!this.formData.enName) return resolve(true);
      if (!/^[_|a-zA-Z][a-zA-Z0-9_]*$/.test(this.formData.enName) || this.formData.enName.length < 5)
        return reject(false);

      setTimeout(async () => {
        if (this.clickSubmit && !isSubmit) {
          resolve(true);
        } else {
          this.clickSubmit = false;
          const { exists } = await checkDuplicateName({ app_name: this.formData.enName });
          this.existedName = exists;
          if (exists) {
            this.addForm.validateField('enName');
            reject(false);
          } else {
            resolve(true);
          }
        }
      }, 100);
    });
  }

  render() {
    return (
      <div class='app-add-form-wrap'>
        <bk-dialog
          width={640}
          ext-cls='app-add-dialog'
          confirm-fn={this.handleConfirm}
          header-position='left'
          title={this.$t('新建应用')}
          value={this.value}
          onCancel={this.handleCancel}
          onValueChange={this.handleShowChange}
        >
          <div class='app-add-dialog-main'>
            <div class='app-add-desc'>
              <div class='app-add-question'>{this.$t('什么是应用？')}</div>
              <div class='app-add-answer'>
                {this.$t(
                  '应用一般是拥有独立的站点，由多个Service共同组成，提供完整的产品功能，拥有独立的软件架构。 从技术方面来说应用是Trace数据的存储隔离，在同一个应用内的数据将进行统计和观测。更多请查看产品文档。'
                )}
              </div>
            </div>
            <bk-form
              class='app-add-form'
              {...{
                props: {
                  model: this.formData,
                  rules: this.rules,
                },
              }}
              ref='addForm'
              label-width={84}
            >
              <bk-form-item
                error-display-type='normal'
                label={this.$t('应用名称')}
                property='name'
                required
              >
                <bk-input
                  v-model={this.formData.name}
                  maxlength={50}
                  placeholder={this.$t('输入应用名,1-50个字符')}
                />
              </bk-form-item>
              <bk-form-item
                error-display-type='normal'
                label={this.$t('英文名')}
                property='enName'
                required
              >
                <bk-input
                  v-model={this.formData.enName}
                  maxlength={50}
                  placeholder={this.$t('输入5-50字符的字母开头、数字、下划线')}
                  onBlur={() => this.handleCheckEnName()}
                />
              </bk-form-item>
              <bk-form-item label={this.$t('描述')}>
                <bk-input
                  v-model={this.formData.desc}
                  type='textarea'
                />
              </bk-form-item>
            </bk-form>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
