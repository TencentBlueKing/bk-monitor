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

import { defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import DurationInput from './duration-input';
import { TIME_CONSUMING_EMITS, TIME_CONSUMING_PROPS } from './typing';

import './time-consuming.scss';

const GTE = 'gte'; // 大于等于
const LTE = 'lte'; // 小于等于
const EQUAL = 'equal'; // 等于
const BETWEEN = 'between'; // 范围

export default defineComponent({
  name: 'TimeConsuming',
  props: TIME_CONSUMING_PROPS,
  emits: TIME_CONSUMING_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    const localValue = shallowRef([0, 0]);
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

    function handleChange(val) {
      localValue.value = val;
      const where = getWhere(val);
      emit('change', {
        key: props.fieldInfo.field,
        ...where,
      });
    }

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
            {this.t('耗时')}
          </span>
        )}
        <DurationInput
          styleType={this.styleType || 'default'}
          value={this.localValue}
          onChange={this.handleChange}
        />
      </div>
    );
  },
});
