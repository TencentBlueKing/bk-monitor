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

import { defineComponent, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  name: 'RuleTrigger',
  components: {},
  props: {
    data: {
      type: Object as PropType<{
        field_alias: string;
        field_name: string;
        op: string;
        values: string[];
      }>,
      default: () => {},
    },
    isCreate: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const displayValueList = computed(() => props.data.values.slice(0, 3));

    const opMap = {
      '=': '=',
      '!=': '!=',
      contains: t('包含'),
      'not contains': t('不包含'),
    };

    const handleClickTrigger = () => {
      emit('click');
    };

    const handleClickDelete = (e: Event) => {
      e.stopPropagation();
      emit('delete');
    };

    return () => (
      <div
        class='config-rule-trigger'
        on-click={handleClickTrigger}
      >
        {props.isCreate ? (
          <div class='add-main'>
            <log-icon type='plus' />
          </div>
        ) : (
          <div class='display-main'>
            <div class='field-display'>
              <span class='name-title'>
                {props.data.field_alias}({props.data.field_name})
              </span>
              <span class={{ 'opt-sign': true, 'is-negtive': ['!=', 'not contains'].includes(props.data.op) }}>
                {opMap[props.data.op]}
              </span>
              <div
                class='close-main'
                on-click={handleClickDelete}
              >
                <log-icon
                  class='close-icon'
                  type='close-circle-shape'
                  common
                />
              </div>
            </div>
            <div class='value-display'>
              {displayValueList.value.map((item, index) => (
                <div
                  key={item}
                  class='combine-main'
                >
                  <div
                    class='value-item'
                    v-bk-overflow-tips
                  >
                    {item}
                  </div>
                  {index < 2 && index < displayValueList.value.length - 1 && <span class='split-sign'>,</span>}
                </div>
              ))}
              {props.data.values.length > 3 && (
                <span
                  class='more-count'
                  v-bk-tooltips={{
                    content: props.data.values.slice(3).join(','),
                  }}
                >
                  +{props.data.values.length - 3}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    );
  },
});
