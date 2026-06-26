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

import { type PropType, defineComponent, shallowRef } from 'vue';

import { Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { ITapdListItem } from '../typing';

import './tapd-relation.scss';

export default defineComponent({
  name: 'TapdRelation',
  props: {
    modelValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    tapdList: {
      type: Array as PropType<ITapdListItem[]>,
      default: () => [
        {
          tapd_id: '111',
          tapd_type: 'story',
          tapd_title: '需求1',
        },
        {
          tapd_id: '222',
          tapd_type: 'story',
          tapd_title: '需求2',
        },
      ],
    },
  },
  emits: {
    'update:modelValue': (_val: string[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const errMsg = shallowRef('');

    const validate = async () => {
      if (!props.modelValue.length) {
        errMsg.value = t('请选择单据');
      } else {
        errMsg.value = '';
      }
      return !errMsg.value;
    };

    const handleChange = (val: string[]) => {
      emit('update:modelValue', val);
    };

    const handleToggle = val => {
      if (val) {
        errMsg.value = '';
      } else {
        validate();
      }
    };

    return {
      errMsg,
      t,
      handleChange,
      validate,
      handleToggle,
    };
  },
  render() {
    return (
      <div class='tapd-sideslider-relation-compoent'>
        <span class='form-header mb-24'>
          <span class='form-header-title'>{this.t('选择单据')}</span>
        </span>
        <div class='form-grid'>
          <div class={'form-item'}>
            <div class={['form-item-title', 'required']}>
              <span>{this.t('选择已有单据')}</span>
            </div>
            <div class={['form-item-content', { 'is-error': this.errMsg }]}>
              <Select
                popoverOptions={{
                  extCls: 'tapd-sideslider-relation-compoent-popover',
                }}
                modelValue={this.modelValue}
                multiple={true}
                filterable
                onToggle={this.handleToggle}
                onUpdate:modelValue={this.handleChange}
              >
                {this.tapdList.map(item => (
                  <Select.Option
                    id={item.tapd_id}
                    key={item.tapd_id}
                    name={item.tapd_title}
                  >
                    <span class='tapd-select-item'>
                      <span class='tapd-id'>{item.tapd_id}</span>
                      <span class='tapd-title'>{item.tapd_title}</span>
                      <span class='tapd-status'>backlog</span>
                    </span>
                  </Select.Option>
                ))}
              </Select>
              {this.errMsg ? <span class='err-msg'>{this.errMsg}</span> : undefined}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
