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
import { type PropType, computed, defineComponent, nextTick, shallowRef, useTemplateRef } from 'vue';

import { Input, Select } from 'bkui-vue';
import { EditLine } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import ExpiredSelect from '../../../../components/expired-select/expired-select';

import './editable-field.scss';
/**
 * 可编辑字段组件
 * 支持两种状态：
 * 1. 展示状态：显示值和编辑图标
 * 2. 编辑状态：显示输入控件和确认/取消按钮
 */
export default defineComponent({
  name: 'EditableField',
  props: {
    /** 字段值 */
    value: {
      type: [Number, String] as PropType<number | string>,
      default: '',
    },
    /** 是否可编辑 */
    editable: {
      type: Boolean,
      default: true,
    },
    /** 字段标签 */
    label: {
      type: String,
      default: '',
    },
    /** 展示后缀，如 "天"、"G" */
    suffix: {
      type: String,
      default: '',
    },
    /** 编辑类型：input / select / expired */
    type: {
      type: String as PropType<'expired' | 'input' | 'select'>,
      default: 'input',
    },
    /** 下拉选项（type为select时使用） */
    options: {
      type: Array as PropType<Array<{ label: string; value: number | string }>>,
      default: () => [],
    },
    /** 编辑处理函数 */
    confirm: {
      type: Function as PropType<
        (value: number | string) => Promise<{ isPass: boolean; msg: string }> | { isPass: boolean; msg: string }
      >,
      default: null,
    },
    /** 最大过期天数（type 为 expired 时使用） */
    maxExpired: {
      type: Number,
      default: 0,
    },
    /** 是否必填 */
    required: {
      type: Boolean,
      default: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const isEditing = shallowRef<boolean>(false);
    const loading = shallowRef(false);
    const editValue = shallowRef<number | string>('');

    const errorMsg = shallowRef('');
    const inputRef = useTemplateRef<InstanceType<typeof Input>>('input');

    // 计算展示文本
    const displayText = computed(() => {
      if (props.type === 'select' && props.options.length) {
        const option = props.options.find(opt => opt.value === props.value);
        return option?.label || props.value;
      }
      return props.value;
    });

    // 开始编辑
    const handleStartEdit = () => {
      if (!props.editable) return;
      editValue.value = props.value;
      isEditing.value = true;
      errorMsg.value = '';
      nextTick(() => {
        inputRef.value?.focus();
      });
    };

    // 确认修改
    const handleConfirm = async () => {
      if (!editValue.value && editValue.value !== 0 && props.required) {
        errorMsg.value = t('必填项');
        return;
      }
      if (props.confirm) {
        loading.value = true;
        const { isPass, msg } = await props.confirm(editValue.value);
        loading.value = false;
        errorMsg.value = msg;
        if (!isPass) return;
      }
      isEditing.value = false;
    };

    // 取消编辑
    const handleCancel = () => {
      isEditing.value = false;
    };

    /** 根据编辑类型渲染对应的编辑控件（Input / Select / ExpiredSelect） */
    const renderEditValue = () => {
      switch (props.type) {
        case 'select':
          return (
            <Select
              class='edit-item select-item'
              v-model={editValue.value}
              clearable={false}
              disabled={loading.value}
            >
              {props.options.map(opt => (
                <Select.Option
                  id={opt.value}
                  key={String(opt.value)}
                  name={opt.label}
                />
              ))}
            </Select>
          );
        case 'expired':
          return (
            <ExpiredSelect
              class='edit-item expired-select'
              v-model={editValue.value}
              max={props.maxExpired}
              placeholder={t('最大为{n}天', { n: props.maxExpired })}
            />
          );
        default:
          return (
            <Input
              ref='input'
              class='edit-item input-item'
              v-model={editValue.value}
              disabled={loading.value}
            />
          );
      }
    };

    return {
      t,
      isEditing,
      editValue,
      displayText,
      loading,
      errorMsg,
      renderEditValue,
      handleStartEdit,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <div class={['editable-field', { 'is-editable': this.editable }]}>
        <div class='editable-field-wrap'>
          {this.label && (
            <span class='editable-field-label'>
              <span
                class='text'
                v-bk-tooltips={{ content: this.label }}
              >
                {this.label}
              </span>
            </span>
          )}
          <div class='editable-field-content'>
            {this.isEditing ? (
              <div class='editable-field-edit-mode'>
                {this.renderEditValue()}
                {this.loading ? (
                  <div class='action-loading' />
                ) : (
                  <div class='action-btns'>
                    <i
                      class='icon-monitor icon-mc-check-small confirm'
                      onClick={this.handleConfirm}
                    />
                    <i
                      class='icon-monitor icon-mc-close close'
                      onClick={this.handleCancel}
                    />
                  </div>
                )}
              </div>
            ) : (
              <div
                class='editable-field-view-mode'
                onClick={this.handleStartEdit}
              >
                <span class='editable-field-value'>
                  {this.displayText}
                  <span class='suffix'>{this.suffix}</span>
                </span>
                {this.editable && (
                  <span
                    class='editable-field-icon'
                    v-tippy={{ content: this.t('编辑') }}
                  >
                    <EditLine />
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {this.isEditing && this.errorMsg && <span class='error-msg'>{this.errorMsg}</span>}
      </div>
    );
  },
});
