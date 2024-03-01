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
import { defineComponent, PropType, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Select } from 'bkui-vue';
import { debounce } from 'lodash';
import { queryLabelValues } from 'monitor-api/modules/apm_profile';

import { IConditionItem } from '../typings';

import './condition-item.scss';

export default defineComponent({
  name: 'ConditionItem',
  props: {
    data: {
      type: Object as PropType<IConditionItem>,
      default: () => null
    },
    labelList: {
      type: Array as PropType<string[]>,
      default: () => []
    },
    valueListParams: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['change', 'delete'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const localValue = reactive<IConditionItem>({
      key: '',
      method: 'eq',
      value: ''
    });
    const labelStatus = reactive({
      toggle: false,
      hover: false
    });

    const scrollLoading = ref(false);
    const valueList = ref<string[]>([]);

    watch(
      () => props.data,
      newVal => {
        newVal && Object.assign(localValue, newVal);
      },
      {
        immediate: true
      }
    );

    watch(
      () => props.labelList,
      () => {
        valueList.value = [];
      }
    );

    const getLabelValuesDebounce = debounce(getLabelValues, 100);

    /** 获取过滤项值列表 */
    async function getLabelValues() {
      // 每页数量
      const rows = 30;
      // 如果列表数据量不是每页数量的倍数，说明所有数据都请求完成了
      if (valueList.value.length % rows !== 0) return;
      const offset = Math.floor(valueList.value.length / rows);
      scrollLoading.value = true;
      const res = await queryLabelValues({
        ...props.valueListParams,
        label_key: localValue.key,
        rows,
        offset
      }).catch(() => ({ label_values: [] }));
      valueList.value = [...valueList.value, ...res.label_values];
      scrollLoading.value = false;
    }

    function handleKeyChange() {
      localValue.value = '';
      valueList.value = [];
      getLabelValuesDebounce();
      handleEmitData();
    }

    function handleEmitData() {
      emit('change', { ...localValue });
    }

    function handleDelete() {
      emit('delete');
    }

    return {
      t,
      localValue,
      labelStatus,
      valueList,
      scrollLoading,
      getLabelValuesDebounce,
      handleKeyChange,
      handleEmitData,
      handleDelete
    };
  },

  render() {
    return (
      <div class='condition-item-component'>
        <div class='header-label'>
          <div class='label-wrap'>
            <span
              class={{
                label: true,
                active: this.labelStatus.toggle,
                hover: this.labelStatus.hover,
                placeholder: !this.localValue.key
              }}
            >
              {this.localValue.key || this.t('选择')}
            </span>
            <div
              onMouseover={() => (this.labelStatus.hover = true)}
              onMouseout={() => (this.labelStatus.hover = false)}
            >
              <Select
                v-model={this.localValue.key}
                class='label-select'
                onToggle={toggle => (this.labelStatus.toggle = toggle)}
                popover-min-width={120}
                clearable={false}
                onChange={this.handleKeyChange}
              >
                {this.labelList.map(option => (
                  <Select.Option
                    key={option}
                    id={option}
                    name={option}
                  ></Select.Option>
                ))}
              </Select>
            </div>
          </div>
          <span class={['method', this.localValue.method]}>=</span>
          <i
            class='icon-monitor icon-mc-delete-line'
            onClick={this.handleDelete}
          ></i>
        </div>
        <div class='content'>
          <Select
            v-model={this.localValue.value}
            filterable
            scroll-loading={this.scrollLoading}
            onScroll-end={this.getLabelValuesDebounce}
            onChange={this.handleEmitData}
          >
            {this.valueList.map(option => (
              <Select.Option
                key={option}
                id={option}
                name={option}
              ></Select.Option>
            ))}
          </Select>
        </div>
      </div>
    );
  }
});
