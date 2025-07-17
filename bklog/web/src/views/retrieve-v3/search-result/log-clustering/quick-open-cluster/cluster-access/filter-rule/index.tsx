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

import { computed, defineComponent, ref, watch, nextTick } from 'vue';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import $http from '@/api';
import useLocale from '@/hooks/use-locale';
import useFieldNameHook from '@/hooks/use-field-name';
import { formatDate } from '@/common/util';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';

import './index.scss';

export default defineComponent({
  name: 'FilterRule',
  props: {
    value: {
      type: Array<{
        fields_name: string;
        logic_operator: string;
        op: string;
        value: string[];
      }>,
      default: () => [],
    },
    totalFields: {
      type: Array<any>,
      required: true,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
    datePickerValue: {
      type: Array<any>,
      required: true,
    },
  },
  setup(props, { emit, expose }) {
    const store = useStore();
    const route = useRoute();
    const { t } = useLocale();

    const refs = ref({} as any);
    const quickClusterFromRef = ref();
    const isLikeCorrect = ref(true);
    const formData = ref({
      filter_rules: [],
    });
    const localFilterRule = ref(props.value || []);

    // 优先展示选中字段名
    const filterSelectList = computed(() => {
      const { getConcatenatedFieldName } = useFieldNameHook({ store });
      return props.totalFields
        .filter(item => !/^__dist/.test(item.field_name) && item.field_type !== '__virtual__')
        .map(el => {
          return getConcatenatedFieldName(el);
        });
    });

    const isShowAddFilterIcon = computed(() => {
      const rules = formData.value.filter_rules;
      if (
        !rules.length ||
        (rules.slice(-1)[0].fields_name !== '' && rules.length === 1) ||
        rules.slice(-1)[0].value.length > 0
      )
        return true;
      return false;
    });

    const checkFilterRules = () => {
      if (formData.value.filter_rules.length === 1 && !formData.value.filter_rules[0].fields_name) return true;
      return formData.value.filter_rules.every(item => !!item.value.length && item.fields_name);
    };
    const checkLIKERules = () => {
      isLikeCorrect.value = formData.value.filter_rules.every(item => {
        if (['NOT LIKE', 'LIKE'].includes(item.op) && !!item.value.length) return /%/.test(item.value[0]);
        return true;
      });
      return isLikeCorrect.value;
    };

    const formRules = {
      clustering_fields: [
        {
          required: true,
          trigger: 'blur',
        },
      ],
      filter_rules: [
        {
          validator: checkFilterRules,
          trigger: 'blur',
        },
        {
          validator: checkLIKERules,
          trigger: 'change',
        },
      ],
    };
    const conditionList = [
      // 过滤条件对比
      { id: '=', name: '=' },
      { id: '!=', name: '!=' },
      { id: 'LIKE', name: 'LIKE' },
      { id: 'NOT LIKE', name: 'NOT LIKE' },
    ];
    const comparedList = [
      { id: 'and', name: 'AND' },
      { id: 'or', name: 'OR' },
    ];

    watch(
      () => formData.value.filter_rules,
      rules => {
        localFilterRule.value = rules;
        emit('update:value', rules);
      },
      {
        deep: true,
      },
    );

    watch(
      localFilterRule,
      rules => {
        if (rules.length) {
          formData.value.filter_rules = rules;
        }
      },
      {
        deep: true,
        immediate: true,
      },
    );

    const fieldsKeyStrList = () => {
      const fieldsStrList = formData.value.filter_rules
        .filter(item => item.field_type !== 'text' && item.es_doc_values)
        .map(item => item.fields_name);
      return Array.from(new Set(fieldsStrList));
    };

    const queryValueList = async (fields = []) => {
      if (!fields.length) return;
      const tempList = handleTransformToTimestamp(props.datePickerValue as any, store.getters.retrieveParams.format);
      try {
        const res = await $http.request('retrieve/getAggsTerms', {
          params: {
            index_set_id: window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId,
          },
          data: {
            keyword: props.retrieveParams?.keyword ?? '*',
            fields,
            start_time: formatDate(tempList[0]),
            end_time: formatDate(tempList[1]),
          },
        });
        formData.value.filter_rules.forEach(item => {
          item.valueList =
            res.data.aggs_items[item.fields_name]?.map(item => ({
              id: item.toString(),
              name: item.toString(),
            })) ?? [];
        });
      } catch (err) {
        formData.value.filter_rules.forEach(item => (item.valueList = []));
      }
    };

    const handleFieldChange = (fieldName: string, index: number) => {
      const field = props.totalFields.find(item => item.field_name === fieldName) ?? {};
      Object.assign(formData.value.filter_rules[index], {
        ...field,
        value: [],
      });
      const requestFields = fieldsKeyStrList();
      queryValueList(requestFields);
    };

    const handleDeleteSelect = (index: number) => {
      formData.value.filter_rules.splice(index, 1);
      console.log('refs.value = ', refs.value);
      (refs.value[`fieldSelectRef-${index}`] as any).close();
    };

    const handleAddFilterRule = () => {
      formData.value.filter_rules.push({
        fields_name: '', // 过滤规则字段名
        op: '=', // 过滤规则操作符号
        value: [], // 过滤规则字段值
        logic_operator: 'and',
        valueList: [],
      });
      nextTick(() => {
        const index = formData.value.filter_rules.length - 1;
        console.log('refs.value = ', refs.value);
        (refs.value[`fieldSelectRef-${index}`] as any).show();
      });
    };

    const handleValueBlur = (operateItem, val: string) => {
      if (!operateItem.value.length && !!val) operateItem.value.push(val);
    };

    const handleCheckRuleValidate = async () => {
      try {
        await quickClusterFromRef.value.validate();
        return true;
      } catch (error) {
        return false;
      }
    };

    // 设置动态ref的方法
    const setSelectDynamicRef = (key: string) => {
      return (el: any) => {
        if (el === null) {
          // 卸载时移除
          delete refs.value[key];
        } else {
          refs.value[key] = el;
        }
      };
    };

    expose({
      handleCheckRuleValidate,
    });

    return () => (
      <bk-form
        ref={quickClusterFromRef}
        ext-cls='filter-container'
        form-type='vertical'
        {...{
          props: {
            model: formData.value,
            rules: formRules,
          },
        }}
      >
        <bk-form-item
          label=''
          property='filter_rules'
        >
          {!isLikeCorrect.value && (
            <div class='like-error-message'>
              <i class='bk-icon icon-exclamation-circle-shape error-icon'></i>
              <span>{t('使用LIKE、NOT LINK操作符时请在过滤值前后增加%')}</span>
            </div>
          )}
          <div class='filter-rule'>
            {formData.value.filter_rules.map((item, index) => (
              <div class='filter-rule filter-rule-item'>
                {!!formData.value.filter_rules.length && !!index && !!item.fields_name && (
                  <bk-select
                    class='icon-box and-or mr-neg1'
                    value={item.logic_operator}
                    clearable={false}
                    on-change={value => (item.logic_operator = value)}
                  >
                    {comparedList.map(option => (
                      <bk-option
                        id={option.id}
                        name={option.name}
                      ></bk-option>
                    ))}
                  </bk-select>
                )}
                <bk-select
                  ref={setSelectDynamicRef(`fieldSelectRef-${index}`)}
                  class={['min-100 mr-neg1 above', { 'is-not-error': !!item.fields_name }]}
                  value={item.fields_name}
                  clearable={false}
                  popover-min-width={150}
                  searchable
                  on-change={value => (item.fields_name = value)}
                  on-selected={fieldsName => handleFieldChange(fieldsName, index)}
                >
                  {filterSelectList.value.map(option => (
                    <bk-option
                      id={option.id}
                      name={option.name}
                    ></bk-option>
                  ))}
                  <div
                    style='cursor: pointer'
                    slot='extension'
                    onClick={() => handleDeleteSelect(index)}
                  >
                    <i class='bk-icon icon-close-circle'></i>
                    <span style='margin-left: 4px;'>{t('删除')}</span>
                  </div>
                </bk-select>
                {!!item.fields_name && (
                  <bk-select
                    class='icon-box mr-neg1 condition'
                    value={item.op}
                    clearable={false}
                    popover-min-width={100}
                    on-change={value => (item.op = value)}
                  >
                    {conditionList.map(option => (
                      <bk-option
                        id={option.id}
                        name={option.name}
                      ></bk-option>
                    ))}
                  </bk-select>
                )}
                {!!item.fields_name && (
                  <div onClick={() => (operateIndex = index)}>
                    <bk-tag-input
                      class={['mr-neg1 min-100 above', { 'is-not-error': !!item.value.length }]}
                      value={item.value}
                      content-width={232}
                      list={item.valueList}
                      placeholder={t('请输入')}
                      trigger='focus'
                      allow-auto-match
                      allow-create
                      on-change={value => (item.value = value)}
                      on-blur={v => handleValueBlur(item, v)}
                    ></bk-tag-input>
                  </div>
                )}
              </div>
            ))}
            {isShowAddFilterIcon.value && (
              <button
                class='icon-box'
                onClick={handleAddFilterRule}
              >
                <i class='bk-icon icon-plus-line'></i>
              </button>
            )}
          </div>
        </bk-form-item>
      </bk-form>
    );
  },
});
