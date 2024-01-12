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

import ThresholdSelect from '../threshold/threshold-select';

import AiLevelSelect from './ai-level-select';
import AlarmThresholdSelect, { BoundType } from './alarm-threshold-select';
import { EFormItemValueType, FormItem, IUnitOptionItem } from './utils';

import './form.scss';
/** 数组值分隔符 */
export const ARRAY_SPLIT_CHART = ',';
interface IProps {
  formItemList: FormItem[];
  readonly?: boolean;
  rules?: {
    [key: string]: {
      required?: boolean;
      message?: string | ((val: any) => string);
      trigger?: string;
      min?: number;
      max?: number;
      validator?: (val: any) => boolean;
    };
  };
  labelWidth?: number;
}
interface IEvents {
  onChange: void;
}

type DescType<T> = { value: T; isMatch: boolean };

export interface IDescription {
  dataLength: DescType<string>;
  message: DescType<string>;
  frequency: DescType<number>;
}
@Component
export default class Form extends tsc<IProps, IEvents> {
  /** 表单数据 */
  @Prop({ type: Array, default: () => [] }) formItemList: FormItem[];
  /** 只读状态 */
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 校验规则 */
  @Prop({ type: Object, default: () => ({}) }) rules: IProps['rules'];
  /** 表单label宽度 */
  @Prop({ type: Number, default: 100 }) labelWidth: number;
  /** 表单实例 */
  @Ref() formRef: any;

  get formData() {
    return this.formItemList.reduce((pre, cur) => {
      pre[cur.field] = cur.value || cur.default;
      return pre;
    }, {});
  }

  get validate() {
    return this.formRef.validate;
  }

  get clearError() {
    return this.formRef.clearError;
  }

  /**
   * 表单值更新
   */
  @Emit('change')
  formValueChange() {}

  /** 获取模型的描述 */
  tooltipsListItem(hoverModelData) {
    const description = (hoverModelData?.description || {}) as IDescription;
    const data = [
      {
        label: this.$t('依赖历史数据长度'),
        value: description.dataLength?.value,
        error: !(description.dataLength?.isMatch ?? true)
      },
      {
        label: this.$t('数据频率'),
        value:
          description.frequency?.value === 0
            ? this.$t('无限制')
            : this.$t(' {n} 秒', { n: description.frequency?.value }),
        error: !(description.frequency?.isMatch ?? true)
      },
      {
        label: this.$t('描述'),
        value: description.message?.value,
        error: !(description.message?.isMatch ?? true)
      }
    ];
    return data;
  }

  /**
   * 根据列表获取对应的名称
   * @param id
   * @param options 可选项
   */
  getOptionName(id: number, options: IUnitOptionItem[]) {
    return options.find(item => item.id === id)?.name ?? id;
  }

  /** 处理下拉组件多选值格式 */
  handleSelectMultipleValue(item: FormItem) {
    let { value } = item;
    if (item.multiple) {
      value = !!value
        ? `${item.value}`.split(item.separator || '|').map(set => (item.valueType === 'number' ? +set : set))
        : [];
    }
    return value;
  }

  /** 处理下拉组件多选值格式 */
  handleSelectValueChange(item: FormItem, val: any) {
    let value = val;
    if (item.multiple) {
      value = val.join(item.separator || '|');
    }
    item.value = value;
  }

  render() {
    const formItemTpl = (formItem: FormItem) => {
      /** 阈值值变更 */
      const thresholdSelectChange = val => {
        formItem.value = val;
        this.formValueChange();
      };
      /** select 值变更 */
      const selectChange = () => {
        this.formValueChange();
        formItem.onChange?.(formItem);
      };
      /** switch 值变更 */
      const sitchChange = val => {
        formItem.value = +val;
        this.formValueChange();
      };
      /** range 值变更 */
      const rangeChange = val => {
        formItem.value = +val;
        this.formValueChange();
      };
      /** input-unit */
      const inputUnitChange = val => {
        formItem.value = val * formItem.unitId;
        this.formValueChange();
      };
      /** tag-input组件值变更 */
      const taginputChange = (fromItem: FormItem, val: string[]) => {
        formItem.value = fromItem.valueType === EFormItemValueType.array ? val : val.join(ARRAY_SPLIT_CHART);
        this.formValueChange();
      };

      const boundTypeSelectChange = (type: BoundType) => {
        formItem.boundType = type;
        this.formValueChange();
      };

      switch (formItem.type) {
        case 'select' /** 下拉选择 */:
          return (
            <bk-select
              class='w280 simplicity-select'
              style={{ width: `${formItem.width}px` }}
              value={this.handleSelectMultipleValue(formItem)}
              behavior={formItem.behavior}
              placeholder={formItem.placeholder}
              clearable={false}
              disabled={this.readonly}
              onSelected={selectChange}
              onChange={val => this.handleSelectValueChange(formItem, val)}
            >
              {formItem.options.map(opt => (
                <bk-option
                  id={opt.id}
                  name={opt.name}
                ></bk-option>
              ))}
            </bk-select>
          );
        case 'model-select' /** 模型下拉选择 */:
          return (
            <bk-select
              class='w280 model-select simplicity-select'
              style={{ width: `${formItem.width}px` }}
              v-model={formItem.value}
              behavior={formItem.behavior}
              placeholder={formItem.placeholder}
              clearable={false}
              disabled={this.readonly}
              ext-popover-cls='type-select-tooltips'
              onSelected={selectChange}
            >
              {formItem.options.map(opt => {
                const tooltipsListItem = this.tooltipsListItem(opt.detail);
                return (
                  <bk-option
                    id={opt.id}
                    name={opt.name}
                  >
                    {
                      <bk-popover
                        placement='right'
                        theme='light'
                        transfer
                        z-index={2500}
                        tippy-options={{
                          offset: '0,6',
                          flip: false, // 空间不足不翻转位置
                          onShow: () => {
                            /** 记录hover的选项 */
                            formItem.hoverOptionId = opt.id;
                          }
                        }}
                      >
                        <div class='type-select-item'>
                          <span class='type-select-item-name'>{opt.name}</span>
                          {opt.default && <span class='type-select-item-default'>{this.$t('默认')}</span>}
                        </div>
                        <div
                          class='type-tooltips-content-wrap'
                          slot='content'
                          v-bkloading={{ isLoading: opt.loading }}
                        >
                          <table class='ai-ops-form type-tooltips-content'>
                            {tooltipsListItem.map(item => (
                              <tr class={['ai-ops-form-item type-tooltips-item', { 'is-error': item.error }]}>
                                <td class='form-item-label type-tooltips-item-label'>
                                  <span class='td-content'>
                                    {item.error && <span class='icon-monitor icon-mind-fill'></span>}
                                    <span class='type-tooltips-label-text'>{item.label}：</span>
                                  </span>
                                </td>
                                <td class='form-item-content type-tooltips-item-content'>
                                  <span class='td-content'>{item.value}</span>
                                </td>
                              </tr>
                            ))}
                          </table>
                        </div>
                      </bk-popover>
                    }
                  </bk-option>
                );
              })}
            </bk-select>
          );
        case 'number' /** 数字串输入框 */:
          return (
            <bk-input
              class='w280 simplicity-input'
              style={{ width: `${formItem.width}px` }}
              v-model={formItem.value}
              type='number'
              min={formItem.min}
              max={formItem.max}
              placeholder={formItem.placeholder}
              behavior={formItem.behavior}
              disabled={this.readonly}
              onInput={this.formValueChange}
            ></bk-input>
          );
        case 'input-unit' /** 带单位换算的的输入框 */:
          return (
            <div class='input-unit-item'>
              <bk-input
                class='w280 simplicity-input'
                style={{ width: `${formItem.width}px` }}
                value={formItem.value / formItem.unitId}
                type='number'
                min={formItem.min}
                max={formItem.max}
                placeholder={formItem.placeholder}
                behavior={formItem.behavior}
                disabled={this.readonly}
                onInput={inputUnitChange}
              ></bk-input>
              <span class='unit-wrap'>{this.getOptionName(formItem.unitId, formItem.unitOption)}</span>
            </div>
          );
        case 'string' /** 字符串输入框 */:
          return (
            <bk-input
              class='w280 simplicity-input'
              style={{ width: `${formItem.width}px` }}
              v-model={formItem.value}
              behavior={formItem.behavior}
              placeholder={formItem.placeholder}
              disabled={this.readonly}
              onInput={this.formValueChange}
            ></bk-input>
          );
        case 'thresholds' /** 阈值选择器 */:
          return (
            <ThresholdSelect
              value={formItem.value}
              unit={formItem.unit}
              label={this.$tc('(预测值)')}
              methodList={formItem.methodList}
              autoAdd={false}
              readonly={this.readonly}
              onChange={val => thresholdSelectChange(val)}
            />
          );
        case 'alarm-thresholds' /** 告警阈值选择器 */:
          return (
            <AlarmThresholdSelect
              value={formItem.value}
              unit={formItem.unit}
              methodList={formItem.methodList}
              boundType={formItem.boundType}
              autoAdd={false}
              readonly={this.readonly}
              onChange={val => thresholdSelectChange(val)}
              onBoundTypeChange={val => boundTypeSelectChange(val)}
            />
          );
        case 'switch' /** 开关 */:
          return (
            <bk-switcher
              disabled={this.readonly}
              value={!!+formItem.value}
              onChange={sitchChange}
              size='small'
              theme='primary'
            />
          );
        case 'tag-input' /** tag-input */:
          return (
            <bk-tag-input
              class={['tag-input', formItem.behavior]}
              placeholder={formItem.placeholder || this.$t('选择')}
              disabled={this.readonly}
              behavior={formItem.behavior}
              has-delete-icon
              clearable={false}
              value={
                formItem.valueType === EFormItemValueType.array
                  ? formItem.value
                  : formItem.value?.split(ARRAY_SPLIT_CHART)
              }
              list={formItem.options}
              trigger='focus'
              onChange={v => taginputChange(formItem, v)}
            />
          );
        case 'range':
          return (
            <div class='outlier-detection-range'>
              <bk-slider
                class='w280'
                value={+formItem.value}
                step={1}
                show-tip={true}
                min-value={0}
                max-value={10}
                disable={formItem.disabled || this.readonly}
                onInput={rangeChange}
              />
              <span class='left-text'>{this.$t('较少告警')}</span>
              <span class='right-text'>{this.$t('较多告警')}</span>
            </div>
          );
        case 'ai-level': // 智能算法告警级别选择器
          return (
            <AiLevelSelect
              v-model={formItem.value}
              onChange={this.formValueChange}
              disabled={this.readonly}
            />
          );
        default:
          return undefined;
      }
    };
    return (
      <bk-form
        ref='formRef'
        class='form-wrapper'
        label-width={this.labelWidth}
        rules={this.rules}
        {...{ props: { model: this.formData } }}
      >
        {this.formItemList.map(formItem => (
          <bk-form-item
            label={`${formItem.label} : `}
            property={formItem.field}
            required={formItem.required}
            error-display-type={formItem.errorDisplayType}
          >
            <div class='form-item-content'>
              {formItemTpl(formItem)}
              {!!formItem.description && (
                <i
                  class='icon-monitor icon-hint'
                  v-bk-tooltips={{ content: formItem.description, allowHTML: false }}
                ></i>
              )}
            </div>
          </bk-form-item>
        ))}
      </bk-form>
    );
  }
}
