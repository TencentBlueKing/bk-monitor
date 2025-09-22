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

import { defineComponent, ref, computed, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import InfoTips from '../../common-comp/info-tips';
import IndexSetSelect from './index-set-select';

import './base-info.scss';

export type IBaseInfo = { index_set_name: string; custom_type?: string };

export default defineComponent({
  name: 'BaseInfo',
  props: {
    typeKey: {
      type: String,
      default: 'default',
    },
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['change'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const formData = ref<IBaseInfo>({ index_set_name: '' });
    /** 展示数据名的key */
    const showNameKey = ['default', 'custom'];
    /** 展示备注说明的key */
    const showDescKey = ['default', 'custom'];
    /** 展示数据分类的key */
    const showCategoryKey = ['custom'];
    const formRef = ref();
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);

    const ruleData = ref({
      index_set_name: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
    });

    watch(
      () => props.typeKey,
      val => {
        if (val === 'custom') {
          formData.value = {
            ...formData.value,
            custom_type: 'log',
          };
        }
      },
      { immediate: true },
    );

    const handleChange = () => {
      emit('change', formData.value);
    };

    const validate = () => {
      return formRef.value.validate();
    };

    const handleChangeType = id => {
      formData.value.custom_type = id;
    };

    expose({ validate });

    const renderBaseInfo = () => (
      <bk-form
        ref={formRef}
        class='base-info-form'
        label-width={100}
        {...{
          props: {
            model: formData.value,
            rules: ruleData.value,
          },
        }}
      >
        <bk-form-item
          label={t('采集名')}
          property='index_set_name'
          required={true}
        >
          <bk-input
            maxlength={50}
            value={props.data.index_set_name}
            onInput={val => {
              formData.value.index_set_name = val;
              handleChange();
            }}
          />
        </bk-form-item>
        {showCategoryKey.includes(props.typeKey) && (
          <bk-form-item
            class='category-form-item'
            label={t('数据分类')}
            property='name'
            required={true}
          >
            <div class='bk-button-group'>
              {globalsData.value.databus_custom.map(item => (
                <bk-button
                  // :disabled="isEdit"
                  key={item.id}
                  // data-test-id="`addNewCustomBox_button_typeTo${item.id}`"
                  class={`${formData.value.custom_type === item.id ? 'is-selected' : ''}`}
                  on-click={() => handleChangeType(item.id)}
                >
                  {item.name}
                </bk-button>
              ))}
            </div>
            <InfoTips
              class='block'
              tips={t(
                '自定义上报数据，可以通过采集器，或者指定协议例如otlp等方式进行上报，自定义上报有一定的使用要求，具体可以查看使用说明',
              )}
            />
          </bk-form-item>
        )}
        {showNameKey.includes(props.typeKey) && (
          <bk-form-item
            label={t('数据名')}
            required={true}
          >
            <bk-input
              maxlength={50}
              minlength={5}
              placeholder={t('用于索引和数据源，仅支持数字、字母、下划线，5～50 字符')}
              value={formData.value.index_set_name}
              clearable
              onInput={val => {
                formData.value.index_set_name = val;
              }}
            />
          </bk-form-item>
        )}
        <bk-form-item label={t('所属索引集')}>
          <IndexSetSelect
            on-select={val => {
              console.log(val);
            }}
          />
        </bk-form-item>
        {showDescKey.includes(props.typeKey) && (
          <bk-form-item label={t('备注说明')}>
            <bk-input
              maxlength={100}
              type='textarea'
              value={formData.value.index_set_name}
              clearable
              onInput={val => {
                formData.value.index_set_name = val;
              }}
            />
          </bk-form-item>
        )}
      </bk-form>
    );
    return () => <div class='base-info-box'>{renderBaseInfo()}</div>;
  },
});
