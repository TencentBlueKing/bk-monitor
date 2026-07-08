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
import { type PropType, computed, defineComponent, shallowRef, useTemplateRef } from 'vue';

import { Input, Message, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './expired-select.scss';

export interface IOptionsItem {
  id: number;
  name: string;
}

const DEFAULT_OPTIONS: IOptionsItem[] = [
  {
    id: 1,
    name: window.i18n.t(' {n} 天', { n: 1 }),
  },
  {
    id: 3,
    name: window.i18n.t(' {n} 天', { n: 3 }),
  },
  {
    id: 7,
    name: window.i18n.t(' {n} 天', { n: 7 }),
  },
  {
    id: 14,
    name: window.i18n.t(' {n} 天', { n: 14 }),
  },
];

export default defineComponent({
  name: 'ExpiredSelect',
  props: {
    modelValue: {
      type: [Number, String] as PropType<number | string>,
      default: undefined,
    },
    /** 可选项 */
    options: {
      type: Array as PropType<IOptionsItem[]>,
      default: () => DEFAULT_OPTIONS,
    },
    /** 单位 */
    unit: {
      type: String,
      default: window.i18n.t('天'),
    },
    /** 自定义输入占位符 */
    placeholder: {
      type: String,
      default: window.i18n.t('输入自定义的天数，按Enter确认'),
    },
    /** 组件宽度 */
    width: {
      type: Number,
      default: undefined,
    },
    /** 最大值 */
    max: {
      type: Number,
      default: Number.POSITIVE_INFINITY,
    },
  },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const selectRef = useTemplateRef<InstanceType<typeof Select>>('selectRef');

    /** 自定义选项 */
    const customOptions = shallowRef<IOptionsItem[]>([]);
    const customInput = shallowRef('');

    const localOptions = computed(() => {
      return [...props.options, ...customOptions.value]
        .filter(item => item.id <= props.max)
        .reduce<IOptionsItem[]>((total, item) => {
          if (!total.find(set => set.id === item.id)) total.push(item);
          return total;
        }, [])
        .sort((a, b) => a.id - b.id);
    });

    const valueChange = (val: number) => {
      emit('update:modelValue', val);
      emit('change', val);
    };

    /** 添加自定义选项 */
    const addCustomOptions = (val: number | string) => {
      customOptions.value = [...customOptions.value, { id: val as number, name: `${val}${props.unit}` }];
    };

    /** 隐藏下拉 */
    const hide = () => {
      selectRef.value?.hidePopover();
      customInput.value = '';
    };

    /** 回车确认自定义输入 */
    const handleEnter = (val: number | string) => {
      const numVal = Number(val);
      if (numVal > props.max) {
        Message({ message: t('最大自定义天数为{n}天', { n: props.max }), theme: 'error' });
      } else if (numVal < 0) {
        Message({ message: t('不支持填写负数'), theme: 'error' });
      } else if (numVal !== props.modelValue && !!numVal) {
        valueChange(numVal);
        addCustomOptions(numVal);
        hide();
      } else {
        hide();
      }
    };

    /** 下拉的展开和收起 */
    const handleToggle = (val: boolean) => {
      if (!val) customInput.value = '';
    };

    /** 初始化数据，自动添加自定义选项 */
    const init = () => {
      const option = localOptions.value.find(item => item.id === props.modelValue);
      if (!option && props.modelValue !== undefined) addCustomOptions(props.modelValue);
    };

    init();

    return {
      localOptions,
      customInput,
      valueChange,
      handleEnter,
      handleToggle,
    };
  },
  render() {
    return (
      <Select
        key={JSON.stringify(this.localOptions)}
        ref='selectRef'
        style={this.width ? { width: `${this.width}px` } : undefined}
        v-slots={{
          extension: () => (
            <div class='expired-select-custom-input-wrap'>
              <Input
                v-model={this.customInput}
                placeholder={this.placeholder}
                showControl={false}
                size='small'
                type='number'
                onEnter={(val: string) => this.handleEnter(val)}
              />
            </div>
          ),
        }}
        clearable={false}
        modelValue={this.modelValue}
        onChange={this.valueChange}
        onToggle={this.handleToggle}
      >
        {this.localOptions.map(opt => (
          <Select.Option
            id={opt.id}
            key={String(opt.id)}
            name={opt.name}
          />
        ))}
      </Select>
    );
  },
});
