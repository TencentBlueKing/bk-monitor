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

import { defineComponent, ref, computed, watch, nextTick, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';
import InfoTips from '../../common-comp/info-tips';
import IndexSetSelect from './index-set-select';
import $http from '@/api';

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
      type: Object as PropType<IBaseInfo>,
      default: () => ({}),
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为clone模式
     */
    isClone: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();

    // ==================== 响应式数据 ====================
    /** 表单数据 */
    // const formData = ref<IBaseInfo>({ index_set_name: '', parent_index_set_ids: [] });
    const formData = ref<IBaseInfo>({ ...props.data });
    /** 表单引用 */
    const formRef = ref();
    /** 数据名格式校验状态 */
    const isTextValid = ref(true);

    // ==================== 配置项 ====================
    /** 需要展示数据名的类型列表 */
    const showNameKey = ['default', 'custom'];
    /** 需要展示备注说明的类型列表 */
    const showDescKey = ['default', 'custom'];
    /** 需要展示数据分类的类型列表 */
    const showCategoryKey = ['custom'];

    const enNameErrorMessage = ref('');

    // ==================== 全局数据 ====================
    /** 全局数据（包含自定义上报类型列表） */
    const globalsData = computed(() => store.getters['globals/globalsData']);

    const disabled = computed(() => route.name === 'collectEdit' && props.isEdit);

    // ==================== 校验相关 ====================
    /** 数据名格式正则：只支持字母、数字、下划线 */
    const enNameRegex = /^[A-Za-z0-9_]+$/;

    /**
     * 校验数据名格式（字母、数字、下划线）
     * @param val - 待校验的值
     * @returns 是否通过校验
     */
    const checkEnNameValidator = (val: string): boolean => {
      const isValid = enNameRegex.test(val);
      isTextValid.value = isValid;
      return isValid;
    };

    /**
     * 获取数据名当前值
     * @returns 数据名值
     */
    const getCollectorConfigNameEn = () => formData.value.collector_config_name_en;

    /**
     * 校验采集项的英文名是否可用
     * @param val - 校验值
     * @returns
     */
    const checkEnNameRepeat = async () => {
      if (disabled.value) return true;
      const result = await getEnNameIsRepeat();
      return result;
    };
    /**
     * 校验采集项的英文名是否可用
     * @param val
     * @returns
     */
    const getEnNameIsRepeat = async () => {
      try {
        const res = await $http.request('collect/getPreCheck', {
          params: { collector_config_name_en: getCollectorConfigNameEn(), bk_biz_id: store.state.bkBizId },
        });
        if (res.data) {
          enNameErrorMessage.value = res.data.message;
          return res.data.allowed;
        }
      } catch (error) {
        return false;
      }
    };

    /**
     * 表单校验规则
     */
    const ruleData = ref({
      index_set_name: [
        {
          message: t('必填项'),
          trigger: 'blur',
          validator: () => !!formData.value.index_set_name,
        },
      ],
      collector_config_name_en: [
        {
          message: t('必填项'),
          trigger: 'blur',
          validator: () => !!getCollectorConfigNameEn(),
        },
        {
          message: t('只支持输入字母，数字，下划线'),
          trigger: 'blur',
          validator: () => {
            const value = getCollectorConfigNameEn();
            return !value || checkEnNameValidator(value);
          },
        },
        {
          message: t('不能少于5个字符'),
          trigger: 'blur',
          validator: () => {
            const value = getCollectorConfigNameEn();
            return !value || value.length > 4;
          },
        },
        {
          max: 50,
          message: t('不能多于{n}个字符', { n: 50 }),
          trigger: 'blur',
          validator: () => {
            const value = getCollectorConfigNameEn();
            return !value || value.length <= 50;
          },
        },
        {
          // 检查数据名是否可用
          validator: checkEnNameRepeat,
          message: () => enNameErrorMessage.value,
          trigger: 'blur',
        },
      ],
    });

    // ==================== 监听器 ====================
    /**
     * 监听类型变化，初始化自定义类型
     */
    watch(
      () => props.typeKey,
      (val: string) => {
        if (val === 'custom') {
          formData.value = {
            ...formData.value,
            custom_type: 'log',
          };
        }
      },
      { immediate: true },
    );
    watch(
      () => props.data,
      (val: IBaseInfo) => {
        formData.value = { ...formData.value, ...val };
      },
      { deep: true },
    );

    // ==================== 事件处理 ====================
    /**
     * 通知父组件表单数据变化
     */
    const handleChange = () => {
      emit('change', formData.value);
    };

    /**
     * 更新表单字段值并触发变化事件
     * @param field - 字段名
     * @param value - 字段值
     */
    const updateFormField = <K extends keyof IBaseInfo>(field: K, value: IBaseInfo[K]) => {
      formData.value[field] = value;
      handleChange();
    };

    /**
     * 表单校验
     * @returns Promise - 校验结果
     */
    const validate = () => {
      return formRef.value.validate();
    };

    /**
     * 处理数据分类类型变化
     * @param id - 类型ID
     */
    const handleChangeType = (id: string) => {
      updateFormField('custom_type', id);
    };

    /**
     * 将字符串转换为符合格式要求的数据名
     * - 将横线 '-' 转换为下划线 '_'
     * - 移除非字母、数字、下划线的字符
     * @param str - 原始字符串
     * @returns 转换后的字符串
     */
    const convertToValidEnName = (str: string): string => {
      let result = '';
      for (let i = 0; i < str.length; i++) {
        const char = str[i];
        if (char === '-') {
          result += '_';
        } else if (/\w/.test(char)) {
          result += char;
        }
      }
      return result;
    };

    /**
     * 自动转换数据名格式
     */
    const handleEnConvert = () => {
      const originalStr = getCollectorConfigNameEn();
      const convertStr = convertToValidEnName(originalStr);

      updateFormField('collector_config_name_en', convertStr);

      // 转换后重新校验
      nextTick(() => {
        formRef.value
          .validate()
          .then(() => {
            isTextValid.value = true;
          })
          .catch(() => {
            // 如果转换后长度不足5，仍然标记为有效（避免显示转换提示）
            if (convertStr.length < 5) {
              isTextValid.value = true;
            }
          });
      });
    };

    // ==================== 暴露方法 ====================
    expose({ validate });

    // ==================== 渲染函数 ====================
    /**
     * 渲染数据分类选择按钮组
     * @returns JSX元素数组
     */
    const renderCategoryButtons = () => {
      const customTypes = globalsData.value.databus_custom || [];
      const buttons = [];

      for (let i = 0; i < customTypes.length; i++) {
        const item = customTypes[i];
        const isSelected = formData.value.custom_type === item.id;

        buttons.push(
          <bk-button
            key={item.id}
            disabled={disabled.value}
            class={isSelected ? 'is-selected' : ''}
            on-click={() => handleChangeType(item.id)}
          >
            {item.name}
          </bk-button>,
        );
      }

      return buttons;
    };

    /**
     * 渲染基础信息表单
     */
    const renderBaseInfo = () => {
      const shouldShowCategory = showCategoryKey.includes(props.typeKey);
      const shouldShowName = showNameKey.includes(props.typeKey);
      const shouldShowDesc = showDescKey.includes(props.typeKey);

      return (
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
          {/* 采集名 */}
          <bk-form-item
            label={t('采集名')}
            property='index_set_name'
            required={true}
          >
            <bk-input
              maxlength={50}
              value={formData.value.index_set_name}
              onInput={val => updateFormField('index_set_name', val)}
            />
          </bk-form-item>

          {/* 数据分类（仅自定义类型显示） */}
          {shouldShowCategory && (
            <bk-form-item
              class='category-form-item'
              label={t('数据分类')}
              property='name'
              required={true}
            >
              <div class='bk-button-group'>{renderCategoryButtons()}</div>
              <InfoTips
                class='block'
                tips={t(
                  '自定义上报数据，可以通过采集器，或者指定协议例如otlp等方式进行上报，自定义上报有一定的使用要求，具体可以查看使用说明',
                )}
              />
            </bk-form-item>
          )}

          {/* 数据名（默认和自定义类型显示） */}
          {shouldShowName && (
            <bk-form-item
              label={t('数据名')}
              property='collector_config_name_en'
              required={true}
            >
              <bk-input
                maxlength={50}
                minlength={5}
                disabled={disabled.value}
                placeholder={t('用于索引和数据源，仅支持数字、字母、下划线，5～50 字符')}
                value={formData.value.collector_config_name_en}
                onInput={val => updateFormField('collector_config_name_en', val)}
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

          {/* 所属索引集 */}
          <bk-form-item label={t('所属索引集')}>
            <IndexSetSelect
              value={formData.value.parent_index_set_ids}
              on-select={val => updateFormField('parent_index_set_ids', val)}
            />
          </bk-form-item>

          {/* 备注说明（默认和自定义类型显示） */}
          {shouldShowDesc && (
            <bk-form-item label={t('备注说明')}>
              <bk-input
                maxlength={100}
                type='textarea'
                value={formData.value.description}
                clearable
                onInput={val => updateFormField('description', val)}
              />
            </bk-form-item>
          )}
        </bk-form>
      );
    };

    return () => <div class='base-info-box'>{renderBaseInfo()}</div>;
  },
});
