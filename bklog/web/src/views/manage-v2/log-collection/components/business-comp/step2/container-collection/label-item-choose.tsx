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

import { defineComponent, ref, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import type { IValueItem } from '../../../../type';

import './label-item-choose.scss';

const LABEL_NAME_REGEX = /^([A-Za-z0-9][-A-Za-z0-9_./]*)?[A-Za-z0-9]$/;

export default defineComponent({
  name: 'LabelItemChoose',
  props: {
    matchItem: {
      type: Object as PropType<IValueItem>,
      default: () => ({
        key: '',
        operator: 'In',
        value: '',
      }),
    },
  },
  emits: ['delete', 'change'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const isValueError = ref(false);

    const formData = ref({ ...props.matchItem });
    const keyRef = ref();

    // 表达式操作选项
    const expressOperatorList = ref([
      // { id: '=', name: '=' },
      { id: 'In', name: 'In' },
      { id: 'NotIn', name: 'NotIn' },
      { id: 'Exists', name: 'Exists' },
      { id: 'DoesNotExist', name: 'DoesNotExist' },
    ]);

    const checkName = () => {
      if (formData.value.matchKey === '') {
        return true;
      }
      return LABEL_NAME_REGEX.test(formData.value.matchKey);
    };

    // 表单验证规则
    const rules = {
      key: [
        {
          validator: checkName,
          message: t('标签名称不符合正则{n}', { n: '([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9]' }),
          trigger: 'blur',
        },
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
    };

    // 计算属性
    // const expressInputIsDisabled = computed(() => {
    //   return ['Exists', 'DoesNotExist'].includes(formData.value.operator);
    // });

    const isHaveCompared = computed(() => {
      return ['In', 'NotIn'].includes(formData.value.operator);
    });

    const handleOperateChange = (val: string) => {
      formData.value.operator = val;
      emit('change', formData.value);
    };

    const handleValueBlur = (input: string, list: string[]) => {
      if (!input) {
        return;
      }
      const data = formData.value.value.split(',').filter(item => item.trim() !== '');
      const newList = list.length ? [...new Set([...data, input])] : [input];
      formData.value.value = newList.join(',');
      emit('change', formData.value);
    };

    const handleCancelMatch = () => {
      emit('delete', formData.value);
    };

    // 渲染函数
    return () => (
      <div class='label-item-choose-box'>
        <div class='customize-left'>
          <bk-form
            ref={keyRef}
            ext-cls='fill-key'
            label-width={0}
            {...{
              props: {
                model: formData.value,
                rules,
              },
            }}
          >
            <bk-form-item property='key'>
              <bk-input
                ext-cls='fill-key'
                value={formData.value.key}
                clearable
                on-input={(val: string) => {
                  formData.value.key = val;
                  emit('change', formData.value);
                }}
              />
            </bk-form-item>
          </bk-form>

          <bk-select
            ext-cls='fill-operate'
            clearable={false}
            popover-min-width={116}
            value={formData.value.operator}
            on-selected={handleOperateChange}
          >
            {expressOperatorList.value.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
          </bk-select>
        </div>
        <div class='customize-right justify-sb'>
          {isHaveCompared.value && (
            <bk-tag-input
              ext-cls={`fill-value ${isValueError.value ? 'tag-input-error' : ''}`}
              value={formData.value.value.split(',').filter(item => item.trim() !== '')}
              allow-create
              free-paste
              has-delete-icon
              on-blur={handleValueBlur}
              on-change={(val: string[]) => {
                formData.value.value = val.join(',');
                emit('change', formData.value);
              }}
            />
          )}

          <div
            class='add-operate flex-ac'
            on-Click={handleCancelMatch}
          >
            <span class='bk-icon icon-close-line-2' />
          </div>
        </div>
      </div>
    );
  },
});
