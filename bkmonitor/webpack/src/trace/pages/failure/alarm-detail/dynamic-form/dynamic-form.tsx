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

import { type PropType, computed, defineComponent, onBeforeMount, ref } from 'vue';

import { Checkbox, Form, Input, Radio, Select } from 'bkui-vue';
import { deepClone } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import SetMealAdd from '../../../../store/modules/set-meal-add';
import AutoInput from '../auto-input/auto-input';

import './dynamic-form.scss';

interface FormChildProps {
  help_text?: string;
  label?: string;
  placeholder?: string;
  property?: string;
  required?: boolean;
  options?: {
    id: string;
    name: string;
    value: string;
  }[];
}
interface FormItemProps {
  help_text?: string;
  property?: string;
  required?: boolean;
  sensitive?: boolean;
}
interface FormListItem {
  formChildProps?: FormChildProps;
  formItemProps?: FormItemProps;
  type?: string;
}

export default defineComponent({
  props: {
    formRules: {
      type: Object,
      default: () => ({}),
    },
    formModel: {
      type: Object,
      default: () => ({}),
    },
    noAutoInput: {
      type: Boolean,
      default: false,
    },
    formList: {
      type: Array as PropType<FormListItem[]>,
      default: () => [],
    },
    labelWidth: {
      type: Number,
      default: 150,
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const setMealAddModule = SetMealAdd();
    const { t } = useI18n();

    const getMessageTemplateList = computed(() =>
      props.noAutoInput ? [] : setMealAddModule.getMessageTemplateList.filter(item => item.group !== 'CONTENT_VAR')
    );
    const createFormEl = ref<InstanceType<typeof Form>>(null);

    const emitModel = () => {
      emit('change', deepClone(props.formModel));
    };
    const validator = async () => {
      const res = await createFormEl.value.validate().catch(err => {
        console.log(err);
      });
      return res;
    };

    onBeforeMount(() => {
      emitModel();
    });

    return {
      emitModel,
      createFormEl,
      getMessageTemplateList,
      validator,
      t,
    };
  },
  render() {
    return (
      <div class='dynamic-form-wrap'>
        <Form
          ref='createFormEl'
          class='form-wrap'
          form-type='vertical'
          labelWidth={this.labelWidth}
          {...{
            model: this.formModel,
            rules: this.formRules,
          }}
          v-slots={{
            default: () => {
              return this.formList.map((item, index) => (
                <Form.FormItem
                  key={index}
                  class='create-form-item'
                  errorDisplayType='tooltips'
                  {...item.formItemProps}
                  required={!!item.formItemProps?.required}
                >
                  {item.type === 'select' ? (
                    <Select
                      class='width-520'
                      behavior={'simplicity'}
                      {...item.formChildProps}
                      v-model={this.formModel[item.formItemProps.property]}
                    >
                      {item.formChildProps.options.map(option => (
                        <Select.Option
                          id={option.id}
                          key={option.id}
                          name={option.name}
                        />
                      ))}
                    </Select>
                  ) : undefined}
                  {item.type === 'checkbox-group' ? (
                    <Checkbox.Group
                      {...item.formChildProps}
                      v-model={this.formModel[item.formItemProps.property]}
                    >
                      {item.formChildProps.options.map(option => (
                        <Checkbox
                          key={option.id}
                          label={option.id}
                        />
                      ))}
                    </Checkbox.Group>
                  ) : undefined}
                  {item.type === 'RadioGroup' ? (
                    <Radio.Group
                      {...item.formChildProps}
                      v-model={this.formModel[item.formItemProps.property]}
                    >
                      {item.formChildProps.options.map(option => (
                        <Radio
                          key={option.id}
                          label={option.id}
                        />
                      ))}
                    </Radio.Group>
                  ) : undefined}
                  {
                    (() => {
                      if (item.type === 'input') {
                        if (item.formItemProps.sensitive) {
                          return (
                            <Input
                              v-model={this.formModel[item.formItemProps.property]}
                              behavior={'simplicity'}
                              placeholder={item.formChildProps.placeholder || this.t('请输入')}
                              type={'password'}
                              onChange={this.emitModel}
                            />
                          );
                        }
                        return (
                          <AutoInput
                            v-model={this.formModel[item.formItemProps.property]}
                            placeholder={item.formChildProps.placeholder || this.t('请输入')}
                            tipsList={this.getMessageTemplateList}
                            on-change={this.emitModel}
                          />
                        );
                      }
                      return undefined;
                    })()
                    // ? <Input
                    //   class="width-520"
                    //   behavior={'simplicity'}
                    //   onChange={ this.emitModel }
                    //   {...item.formChildProps}
                    //   v-model={ this.formModel[item.formItemProps.property] }></Input> : undefined
                  }
                  {item.formItemProps.help_text ? (
                    <div class='form-desc'>{item.formItemProps.help_text}</div>
                  ) : undefined}
                </Form.FormItem>
              ));
            },
          }}
        />
      </div>
    );
  },
});
