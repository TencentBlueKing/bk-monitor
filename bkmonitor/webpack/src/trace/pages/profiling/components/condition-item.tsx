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
import { defineComponent, inject, PropType, reactive, Ref, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Select } from 'bkui-vue';

import { queryLabelValues } from '../../../../monitor-api/modules/apm_profile';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { IConditionItem, RetrievalFormData, ToolsFormData } from '../typings';

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
    }
  },
  emits: ['change'],
  setup(props, { emit }) {
    const toolsFormData = inject<Ref<ToolsFormData>>('toolsFormData');
    const formData = inject<RetrievalFormData>('formData');

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
    const labelValueMap = new Map();
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
      () => localValue.key,
      async newVal => {
        if (!newVal) {
          valueList.value = [];
          return;
        }
        getLabelValues();
      }
    );

    /** 获取过滤项值列表 */
    async function getLabelValues() {
      /** 缓存 */
      if (labelValueMap.has(localValue.key)) {
        valueList.value = labelValueMap.get(localValue.key);
        return;
      }
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      const res = await queryLabelValues({
        app_name: formData.server.app_name,
        service_name: formData.server.service_name,
        start: start * 1000 * 1000,
        end: end * 1000 * 1000,
        label_key: localValue.key
      }).catch(() => ({ label_values: [] }));
      valueList.value = res.label_values;
      labelValueMap.set(localValue.key, valueList.value);
    }

    function handleEmitData() {
      emit('change', { ...localValue });
    }

    return {
      t,
      localValue,
      labelStatus,
      valueList,
      handleEmitData
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
                onChange={this.handleEmitData}
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
        </div>
        <div class='content'>
          <Select
            v-model={this.localValue.value}
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
