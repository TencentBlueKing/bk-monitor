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

import { defineComponent, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Dropdown } from 'bkui-vue';
import { Input } from 'tdesign-vue-next';

import { METHOD_MAP, NOT_TYPE_METHODS, SETTING_KV_INPUT_EMITS, SETTING_KV_INPUT_PROPS } from './typing';

import './setting-kv-input.scss';

export default defineComponent({
  name: 'SettingKvInput',
  props: SETTING_KV_INPUT_PROPS,
  emits: SETTING_KV_INPUT_EMITS,
  setup(props, { emit }) {
    const localMethod = shallowRef('');
    const methodMap = shallowRef({});
    const localValue = shallowRef('');

    init();
    watch(
      () => props.value,
      val => {
        if (val) {
          const valueStr = val.value?.[0] || '';
          localMethod.value = val.method;
          if (valueStr !== localValue.value) {
            localValue.value = (val.value?.[0] || '') as string;
          }
          if (val.method !== localMethod.value) {
            localMethod.value = val.method;
          }
        }
      },
      {
        immediate: true,
      }
    );
    function init() {
      methodMap.value = JSON.parse(JSON.stringify(METHOD_MAP));
      for (const item of props.fieldInfo?.methods || []) {
        methodMap.value[item.id] = item.name;
      }
    }

    function handleMethodChange(item: { id: string; name: string }) {
      methodMap.value[item.id] = item.name;
      localMethod.value = item.id;
      handleChange();
    }

    const handleChange = useDebounceFn(() => {
      const valueStr = props.value?.value?.[0] || '';
      const methodStr = props.value?.method || '';
      if (valueStr !== localValue.value || methodStr !== localMethod.value) {
        emit('change', {
          ...props.value,
          key: props.fieldInfo.field,
          method: localMethod.value,
          value: localValue.value?.trim().length ? [localValue.value.trim()] : [],
        });
      }
    }, 100);

    return {
      localMethod,
      methodMap,
      localValue,
      handleMethodChange,
      handleChange,
    };
  },
  render() {
    return (
      <div class='vue3_resident-setting__setting-kv-input-component'>
        <Input
          v-model={this.localValue}
          autoWidth={true}
          clearable={true}
          onBlur={this.handleChange}
          onClear={this.handleChange}
          onEnter={this.handleChange}
        >
          {{
            label: () => (
              <div class='key-method-wrap'>
                <span
                  class='key-wrap'
                  v-bk-tooltips={{
                    content: this.fieldInfo?.field || this.fieldInfo?.alias,
                    placement: 'top',
                  }}
                >
                  {this.fieldInfo?.alias || this.value?.key}
                </span>
                <span class='method-wrap'>
                  <Dropdown
                    popoverOptions={{
                      clickContentAutoHide: true,
                    }}
                    trigger='click'
                  >
                    {{
                      default: () => (
                        <span
                          class={['method-span', { 'red-text': NOT_TYPE_METHODS.includes(this.localMethod as any) }]}
                        >
                          {this.methodMap[this.localMethod] || this.localMethod}
                        </span>
                      ),
                      content: () => (
                        <ul class='vue3_resident-setting__setting-kv-selector-component_method-list-wrap'>
                          {this.fieldInfo.methods.map(item => (
                            <li
                              key={item.id}
                              class={['method-list-wrap-item', { active: item.id === this.localMethod }]}
                              onClick={() => this.handleMethodChange(item)}
                            >
                              {item.name}
                            </li>
                          ))}
                        </ul>
                      ),
                    }}
                  </Dropdown>
                </span>
              </div>
            ),
          }}
        </Input>
      </div>
    );
  },
});
