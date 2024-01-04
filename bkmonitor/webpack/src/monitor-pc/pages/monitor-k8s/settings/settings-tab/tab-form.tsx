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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { IBookMark, SettingsTabType } from '../../typings';

import './tab-form.scss';

interface ITabFormProps {
  canAddTab: Boolean;
  formData: SettingsTabType.ITabForm;
  bookMarkData: IBookMark[];
}

interface ITabFormEvents {
  onChange: void;
  onSave: void;
  onDelete: string;
  onReset: void;
}

@Component
export default class TabForm extends tsc<ITabFormProps, ITabFormEvents> {
  @Prop({ default: () => [], type: Array }) bookMarkData: IBookMark[];
  @Prop() formData: SettingsTabType.ITabForm;
  @Prop({ default: false, type: Boolean }) canAddTab: boolean;
  @Ref('tabForm') refForm;

  get checkNewTab() {
    return this.bookMarkData.some(item => item.id.toString() === this.localForm.id.toString());
  }

  /** 表单数据 */
  localForm: SettingsTabType.ITabForm = {
    id: '',
    name: '',
    // link: '',
    show_panel_count: true
  };

  formRules = {};

  @Watch('formData', { immediate: true, deep: true })
  handleFormDataChange(val) {
    Object.assign(this.localForm, val);
    this.formRules = {
      name: [
        {
          required: true,
          message: this.$t('输入页签名称'),
          trigger: 'blur'
        },
        {
          validator: () => {
            const { id, name } = this.localForm;
            const idList = [];
            const nameList = [];
            this.bookMarkData.forEach(item => {
              idList.push(item.id);
              nameList.push(item.name);
            });
            if (!nameList.includes(name)) return true;

            if (idList.includes(id)) return true;

            return false;
          },
          message: this.$t('注意: 名字冲突'),
          trigger: 'blur'
        }
      ]
    };
  }

  /**
   * @description: 页签设置更新
   */
  handleValueChange() {
    this.$emit('change', this.localForm);
  }

  /**
   * @description: 保存页签
   */
  handleSave() {
    this.refForm.validate().then(() => {
      this.$emit('save');
    });
  }

  // /**
  //  * @description: 重置页签
  //  */
  // handleReset() {
  //   this.$emit('reset');
  // }

  /**
   * @description: 删除页签
   */
  handleDelete() {
    this.$emit('delete', this.localForm.id);
  }

  render() {
    return (
      <div class='tab-from-wrapper'>
        <bk-form
          ref='tabForm'
          class='tab-form'
          form-type='vertical'
          {...{
            props: {
              model: this.localForm,
              rules: this.formRules
            }
          }}
        >
          <bk-form-item
            label={this.$t('页签名称')}
            property='name'
          >
            <bk-input
              class='input-title'
              v-model={this.localForm.name}
              onBlur={this.handleValueChange}
            ></bk-input>
          </bk-form-item>
          {/* <bk-form-item label={this.$t('链接内容')} property="link">
            <bk-input
              class="input-title"
              v-model={this.localForm.link}
              onBlur={this.handleValueChange}
            ></bk-input>
          </bk-form-item> */}
          <bk-form-item
            label={this.$t('是否展示数字')}
            property='link'
          >
            <bk-switcher
              size='large'
              theme='primary'
              v-model={this.localForm.show_panel_count}
              onChange={this.handleValueChange}
            ></bk-switcher>
          </bk-form-item>
          <bk-form-item>
            <div class='handle-footer'>
              <bk-button
                class='handle-btn'
                theme='primary'
                onClick={this.handleSave}
              >
                {this.$t('保存')}
              </bk-button>
              {/* <bk-button class="handle-btn" onClick={this.handleReset}>{ this.$t('重置') }</bk-button> */}
              {this.canAddTab && this.checkNewTab && (
                <bk-button
                  class='handle-btn'
                  onClick={this.handleDelete}
                >
                  {this.$t('删除')}
                </bk-button>
              )}
            </div>
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
