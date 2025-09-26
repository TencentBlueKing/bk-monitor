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
import { defineComponent, ref, watch } from 'vue';

import useLocale from '@/hooks/use-locale';

import $http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'AddRule',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    ruleList: {
      type: Array,
      default: () => [],
    },
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const formRef = ref<any>(null);
    const detectionStr = ref('');
    const isShow = ref(false);
    // 检测语法是否通过
    const isRuleCorrect = ref(false);
    // 是否点击添加
    const isClickSubmit = ref(false);
    // 是否正在检测中
    const isDetection = ref(false);
    const formData = ref({
      regular: '', // 添加聚类规则正则
      placeholder: '', // 添加聚类规则占位符
      scope: 'alone',
    });

    const rules = {
      regular: [
        {
          validator: async (val: string) => {
            try {
              const res = await $http.request('logClustering/checkRegexp', {
                data: { regexp: val },
              });
              if (res.data) {
                return res.data;
              }
            } catch {
              return false;
            }
          },
          required: true,
          trigger: 'blur',
        },
      ],
      placeholder: [
        {
          validator: (val: string) => /^(?!.*:)\S+/.test(val),
          required: true,
          trigger: 'blur',
        },
      ],
    };

    watch(
      () => props.isShow,
      () => {
        isShow.value = props.isShow;
      },
      {
        immediate: true,
      },
    );

    watch(
      () => props.data,
      () => {
        if (!Object.keys(props.data).length) {
          return;
        }
        const data = structuredClone(props.data);
        const keys = Object.keys(data).filter(key => key !== '__Index__');
        if (keys.length === 0) {
          return;
        }
        const firstKey = keys[0];
        const value = data[firstKey];
        formData.value.regular = value;
        formData.value.placeholder = firstKey;
      },
      {
        immediate: true,
      },
    );

    watch(
      formData,
      () => {
        isClickSubmit.value = false;
        isRuleCorrect.value = false;
      },
      {
        deep: true,
      },
    );

    const handleOpenToggle = (isOpen: boolean) => {
      isShow.value = isOpen;
      emit('show-change', isOpen);
      if (!isOpen) {
        formData.value.regular = '';
        formData.value.placeholder = '';
        isRuleCorrect.value = false;
        isClickSubmit.value = false;
        isDetection.value = false;
      }
    };

    // 检测规则和占位符是否重复
    const isRulesRepeat = (newRules = {}) => {
      return props.ruleList.some((listItem: Record<string, any>) => {
        const [regexKey, regexVal] = Object.entries(newRules)[0];
        const [listKey, listVal] = Object.entries(listItem)[0];
        return regexKey === listKey && regexVal === listVal;
      });
    };

    const handleRuleSubmit = () => {
      if (isRuleCorrect.value) {
        const newRuleObj = {} as any;
        const { regular, placeholder } = formData.value;
        newRuleObj[placeholder] = regular;
        // 添加渲染列表时不重复的key值
        newRuleObj.__Index__ = Date.now();
        if (props.isEdit) {
          // 编辑规则替换编辑对象
          emit('edit', newRuleObj);
        } else {
          // 检测正则和占位符是否都重复 重复则不添加
          const isRepeat = isRulesRepeat(newRuleObj);
          if (!isRepeat) {
            emit('add', newRuleObj);
          }
        }
        isShow.value = false;
      } else {
        // 第一次点击检查时显示文案变化
        isDetection.value = true;
        isClickSubmit.value = true;
        detectionStr.value = t('检验中');
        setTimeout(() => {
          formRef
            .value!.validate()
            .then(() => {
              isRuleCorrect.value = true;
              isDetection.value = false;
              detectionStr.value = t('检验成功');
            })
            .catch(() => {
              isRuleCorrect.value = false;
              isDetection.value = false;
              detectionStr.value = t('检测失败');
            });
        }, 1000);
      }
    };

    const handleClickCancel = () => {
      isShow.value = false;
    };

    return () => (
      <bk-dialog
        width={640}
        ext-cls='edit-rule-main'
        header-position='left'
        mask-close={false}
        title={props.isEdit ? t('编辑规则') : t('添加规则')}
        value={isShow.value}
        on-value-change={handleOpenToggle}
      >
        <bk-form
          ref={formRef}
          label-width={200}
          {...{
            props: {
              model: formData.value,
              rules,
            },
          }}
          form-type='vertical'
        >
          <bk-form-item
            label={t('正则表达式')}
            property='regular'
            required
          >
            <bk-input
              style='width: 560px'
              value={formData.value.regular}
              on-change={val => (formData.value.regular = val)}
            />
            <div>
              {t('样例')}
              {'：\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}'}
            </div>
          </bk-form-item>
          <bk-form-item
            label={t('占位符')}
            property='placeholder'
            required
          >
            <bk-input
              style='width: 560px'
              value={formData.value.placeholder}
              on-change={val => (formData.value.placeholder = val.trim().toUpperCase())}
            />
            <div>{t('样例')}：IP</div>
          </bk-form-item>
        </bk-form>
        <div slot='footer'>
          <div class='footer-main'>
            <div class='inspection-status'>
              {isClickSubmit.value && (
                <div>
                  {isDetection.value ? (
                    <bk-spin
                      class='spin'
                      size='mini'
                    />
                  ) : (
                    <span
                      style={`color:${isRuleCorrect.value ? '#45E35F' : '#FE5376'}`}
                      class={[
                        'bk-icon spin',
                        isRuleCorrect.value ? 'icon-check-circle-shape' : 'icon-close-circle-shape',
                      ]}
                    />
                  )}
                  <span style='margin-left: 6px'>{detectionStr.value}</span>
                </div>
              )}
            </div>
            <div class='btns-main'>
              <bk-button
                disabled={isDetection.value}
                theme='primary'
                on-click={handleRuleSubmit}
              >
                {isRuleCorrect.value ? t('保存') : t('检测语法')}
              </bk-button>
              <bk-button on-click={handleClickCancel}>{t('取消')}</bk-button>
            </div>
          </div>
        </div>
      </bk-dialog>
    );
  },
});
