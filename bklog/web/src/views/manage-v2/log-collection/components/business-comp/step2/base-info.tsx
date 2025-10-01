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

import { defineComponent, ref, computed, watch, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import InfoTips from '../../common-comp/info-tips';
import IndexSetSelect from './index-set-select';

import './base-info.scss';

export type IBaseInfo = {
  index_set_name?: string;
  custom_type?: string;
  parent_index_set_ids?: number[];
  collector_config_name_en?: string;
  collector_config_name?: string;
  description?: string;
};

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
    const formData = ref<IBaseInfo>({ index_set_name: '', parent_index_set_ids: [] });
    /** 展示数据名的key */
    const showNameKey = ['default', 'custom'];
    /** 展示备注说明的key */
    const showDescKey = ['default', 'custom'];
    /** 展示数据分类的key */
    const showCategoryKey = ['custom'];
    const formRef = ref();
    const isTextValid = ref(true);
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const enNameRegex = /^[A-Za-z0-9_]+$/;
    const checkEnNameValidator = val => {
      isTextValid.value = enNameRegex.test(val);
      console.log(val, isTextValid.value, 'eeeeee', enNameRegex.test(val));
      return isTextValid.value;
    };
    const ruleData = ref({
      index_set_name: [
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
      collector_config_name_en: [
        // 采集数据名称
        {
          required: true,
          message: t('必填项'),
          trigger: 'blur',
        },
        {
          max: 50,
          message: t('不能多于{n}个字符', { n: 50 }),
          trigger: 'blur',
        },
        {
          min: 5,
          message: t('不能少于5个字符'),
          trigger: 'blur',
        },
        {
          validator: val => checkEnNameValidator(val),
          message: t('只支持输入字母，数字，下划线'),
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
      handleChange();
    };
    /**
     * 数据名
     */
    const handleCollectorConfigNameEnChange = (val: string) => {
      const data = { ...formData.value, collector_config_name_en: val };
      formData.value = data;
    };
    /**
     * 格式转换
     */
    const handleEnConvert = () => {
      const str = formData.value.collector_config_name_en;
      const convertStr = str.split('').reduce((pre, cur) => {
        let newCur = cur;
        if (newCur === '-') {
          newCur = '_';
        }
        if (!/\w/.test(newCur)) {
          newCur = '';
        }
        return pre + newCur;
      }, '');
      handleCollectorConfigNameEnChange(convertStr);
      handleChange();
      nextTick(() => {
        formRef.value
          .validate()
          .then(() => {
            isTextValid.value = true;
          })
          .catch(() => {
            console.log('fail');
            if (convertStr.length < 5) {
              isTextValid.value = true;
            }
          });
      });
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
            property='collector_config_name_en'
            required={true}
          >
            <bk-input
              maxlength={50}
              minlength={5}
              placeholder={t('用于索引和数据源，仅支持数字、字母、下划线，5～50 字符')}
              value={formData.value.collector_config_name_en}
              onInput={val => {
                formData.value.collector_config_name_en = val;
                handleChange();
              }}
            />
            {!isTextValid.value && (
              <span v-bk-tooltips={{ content: t('自动转换成正确的数据名格式') }}>
                <span
                  class='auto-convert'
                  on-click={handleEnConvert}
                >
                  {t('自动转换')}
                </span>
              </span>
            )}
          </bk-form-item>
        )}
        <bk-form-item label={t('所属索引集')}>
          <IndexSetSelect
            on-select={val => {
              formData.value.parent_index_set_ids = val;
              handleChange();
            }}
          />
        </bk-form-item>
        {showDescKey.includes(props.typeKey) && (
          <bk-form-item label={t('备注说明')}>
            <bk-input
              maxlength={100}
              type='textarea'
              value={formData.value.description}
              clearable
              onInput={val => {
                formData.value.description = val;
                handleChange();
              }}
            />
          </bk-form-item>
        )}
      </bk-form>
    );
    return () => <div class='base-info-box'>{renderBaseInfo()}</div>;
  },
});
