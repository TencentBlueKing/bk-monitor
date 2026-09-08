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

import { useI18n } from 'vue-i18n';

import BytesScopeInput from './bytes-scope-input';
import DurationInput from './duration-input';
import { type INormalWhere, SCOPE_INPUT_EMITS, SCOPE_INPUT_PROPS, SCOPE_INPUT_TYPE } from './typing';

import type { TDurationBaseUnit } from './duration-input-utils';

import './scope-input.scss';

const GTE = 'gte'; // 大于等于
const LTE = 'lte'; // 小于等于
const EQUAL = 'equal'; // 等于
const BETWEEN = 'between'; // 范围

export default defineComponent({
  name: 'ScopeInput',
  props: SCOPE_INPUT_PROPS,
  emits: SCOPE_INPUT_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 传给子组件的 [起始值, 结束值]，单位与 fieldInfo.unit 一致 */
    const localValue = shallowRef([0, 0]);
    /** 用户已手动改过值后置为 true，避免子组件回传的 change 再把值覆盖回去 */
    let stopWatch = false;

    watch(
      () => props.value,
      val => {
        if (val && val?.value?.length >= 1 && !stopWatch) {
          const value = val.value;
          if (value.length === 1) {
            if (val?.method === GTE) {
              localValue.value = [Number(value[0]), 0];
            } else if (val?.method === LTE) {
              localValue.value = [0, Number(value[0])];
            } else if (val?.method === EQUAL) {
              localValue.value = [Number(value[0]), Number(value[0])];
            }
          } else {
            const [start, end] = value;
            localValue.value = [Number(start), Number(end)];
          }
          stopWatch = true;
        } else {
          if (!val?.value?.length) {
            localValue.value = [0, 0];
          }
        }
      },
      { immediate: true }
    );

    /** 子组件（耗时 / 字节量输入）范围变更：换算成 method + value 后向上抛 change */
    function handleChange(val) {
      localValue.value = val;
      const where = getWhere(val);
      emit('change', {
        key: props.fieldInfo.field,
        ...where,
      } as unknown as INormalWhere);
    }

    /** 由 [起始值, 结束值] 推导检索操作符与值：仅起始为 gte、仅结束为 lte、相等为 equal、区间为 between */
    function getWhere(val: number[]) {
      const [startVal, endVal] = val;
      if (startVal || endVal) {
        if (startVal && !endVal) {
          return {
            method: GTE,
            value: [startVal],
          };
        }
        if (!startVal && endVal) {
          return {
            method: LTE,
            value: [endVal],
          };
        }
        if (startVal === endVal) {
          return {
            method: EQUAL,
            value: [startVal],
          };
        }
        return {
          method: BETWEEN,
          value: val,
        };
      }
      return {
        method: '',
        value: [],
      };
    }

    return {
      localValue,

      t,
      handleChange,
    };
  },
  render() {
    return (
      <div class={['time-consuming-component', this.styleType ? this.styleType : 'default']}>
        {this.styleType !== 'form' && (
          <span
            class='time-consuming-title'
            v-bk-tooltips={{
              content: this.fieldInfo?.field || this.fieldInfo?.alias,
              placement: 'top',
            }}
          >
            {this.fieldInfo?.alias || this.fieldInfo?.field}
          </span>
        )}

        {/* 按字段类型分发：字节量走 BytesScopeInput，其余（耗时）走 DurationInput */}
        {(() => {
          if (this.type === SCOPE_INPUT_TYPE.bytes) {
            return (
              <BytesScopeInput
                styleType={this.styleType || 'default'}
                value={this.localValue}
                onChange={this.handleChange}
              />
            );
          }
          return (
            <DurationInput
              baseUnit={(this.fieldInfo?.unit || 'μs') as unknown as TDurationBaseUnit}
              styleType={this.styleType || 'default'}
              value={this.localValue}
              onChange={this.handleChange}
            />
          );
        })()}
      </div>
    );
  },
});
