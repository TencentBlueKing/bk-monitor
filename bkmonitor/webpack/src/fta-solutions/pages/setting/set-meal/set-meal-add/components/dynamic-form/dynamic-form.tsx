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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from '../../../../../../../monitor-common/utils/utils';
import SetMealAddModule from '../../../../../../store/modules/set-meal-add';
import AutoInput from '../auto-input/auto-input';

import './dynamic-form.scss';

interface IDynamicForm {
  formRules?: any;
  formModel: any;
  formList: any;
  noAutoInput?: boolean; // 无需提示输入
  labelWidth?: number;
}

@Component
export default class DynamicForm extends tsc<IDynamicForm> {
  @Prop({ default: () => ({}), type: Object }) formRules;
  @Prop({ default: () => ({}), type: Object }) formModel;
  @Prop({ default: () => [], type: Array }) formList;
  @Prop({ default: false, type: Boolean }) noAutoInput;
  @Prop({ default: 150, type: Number }) labelWidth: number;

  get getMessageTemplateList() {
    return this.noAutoInput ? [] : SetMealAddModule.getMessageTemplateList.filter(item => item.group !== 'CONTENT_VAR');
  }

  // isPass: boolean = true

  @Ref('createForm') readonly createFormEl: any;

  @Emit('change')
  emitModel() {
    return deepClone(this.formModel);
  }

  created() {
    this.emitModel();
  }

  async validator() {
    const res = await this.createFormEl.validate().catch(err => {
      console.log(err);
    });
    return res;
  }

  protected render() {
    return (
      <div class='dynamic-form-wrap'>
        <bk-form
          class='form-wrap'
          ref='createForm'
          form-type='vertical'
          labelWidth={this.labelWidth}
          {...{
            props: {
              model: this.formModel,
              rules: this.formRules
            }
          }}
        >
          {this.formList.map((item, index) => (
            <bk-form-item
              class='create-form-item'
              key={index}
              {...{
                props: { ...item.formItemProps, required: !!item.formItemProps?.required }
              }}
            >
              {item.type === 'select' ? (
                <bk-select
                  class='width-520'
                  behavior={'simplicity'}
                  {...item.formChildProps}
                  vModel={this.formModel[item.formItemProps.property]}
                >
                  {item.formChildProps.options.map(option => (
                    <bk-option
                      key={option.id}
                      id={option.id}
                      name={option.name}
                    ></bk-option>
                  ))}
                </bk-select>
              ) : undefined}
              {item.type === 'checkbox-group' ? (
                <bk-checkbox-group
                  {...item.formChildProps}
                  vModel={this.formModel[item.formItemProps.property]}
                >
                  {item.formChildProps.options.map(option => (
                    <bk-checkbox
                      key={option.id}
                      value={option.id}
                    ></bk-checkbox>
                  ))}
                </bk-checkbox-group>
              ) : undefined}
              {item.type === 'RadioGroup' ? (
                <bk-radio-group
                  {...item.formChildProps}
                  vModel={this.formModel[item.formItemProps.property]}
                >
                  {item.formChildProps.options.map(option => (
                    <bk-radio
                      key={option.id}
                      value={option.id}
                    ></bk-radio>
                  ))}
                </bk-radio-group>
              ) : undefined}
              {
                (() => {
                  if (item.type === 'input') {
                    if (item.formItemProps.sensitive) {
                      return (
                        <bk-input
                          v-model={this.formModel[item.formItemProps.property]}
                          placeholder={item.formChildProps.placeholder}
                          type={'password'}
                          behavior={'simplicity'}
                          on-change={this.emitModel}
                        ></bk-input>
                      );
                    }
                    return (
                      <AutoInput
                        placeholder={item.formChildProps.placeholder}
                        tipsList={this.getMessageTemplateList}
                        on-change={this.emitModel}
                        v-model={this.formModel[item.formItemProps.property]}
                      ></AutoInput>
                    );
                  }
                  return undefined;
                })()
                // ? <bk-input
                //   class="width-520"
                //   behavior={'simplicity'}
                //   onChange={ this.emitModel }
                //   {...item.formChildProps}
                //   vModel={ this.formModel[item.formItemProps.property] }></bk-input> : undefined
              }
              {item.formItemProps.help_text ? <div class='form-desc'>{item.formItemProps.help_text}</div> : undefined}
            </bk-form-item>
          ))}
        </bk-form>
      </div>
    );
  }
}
