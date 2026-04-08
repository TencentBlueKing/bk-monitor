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

import { Component, Prop, Emit, Ref, ModelSync, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import $http from '../../../../../../api';
import { formatDate } from '../../../../../../common/util';
import { handleTransformToTimestamp } from '../../../../../../components/time-range/utils';

import type { From } from 'bk-magic-vue';

import './filter-rule.scss';

interface IProps {
  totalFields: any[];
}

const { $i18n } = window.mainComponent;

@Component
export default class QuickOpenCluster extends tsc<IProps> {
  @ModelSync('value', 'change', { type: Array }) localFilterRule!: any[];
  @Prop({ type: Array, required: true }) totalFields: any[];
  @Prop({ type: Array, required: true }) datePickerValue: any[];
  @Prop({ type: Object, required: true }) retrieveParams: object;
  @Ref('quickClusterFrom') quickClusterFromRef: From;

  conditionList = [
    // 过滤条件对比
    { id: '=', name: '=' },
    { id: '!=', name: '!=' },
    { id: 'LIKE', name: 'LIKE' },
    { id: 'NOT LIKE', name: 'NOT LIKE' },
  ];
  comparedList = [
    { id: 'and', name: 'AND' },
    { id: 'or', name: 'OR' },
  ];
  operateIndex = 0;
  isLikeCorrect = true;
  formData = {
    filter_rules: [],
  };
  formRules = {
    clustering_fields: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
    filter_rules: [
      {
        validator: this.checkFilterRules,
        trigger: 'blur',
      },
      {
        validator: this.checkLIKERules,
        trigger: 'change',
      },
    ],
  };

  get isShowAddFilterIcon() {
    const rules = this.formData.filter_rules;
    if (!rules.length || (rules.at(-1)?.fields_name !== '' && rules.length === 1) || rules.at(-1)?.value.length > 0) {
      return true;
    }
    return false;
  }

  get filterSelectList() {
    return this.totalFields
      .filter(item => !/^__dist/.test(item.field_name) && item.field_type !== '__virtual__')
      .map(el => {
        const { field_name: id, field_alias: alias } = el;
        return { id, name: alias ? `${id}(${alias})` : id };
      });
  }

  get indexId() {
    return this.$route.params.indexId;
  }

  @Watch('formData.filter_rules', { deep: true })
  handleIsShowChange(val) {
    this.localFilterRule = val;
  }

  @Watch('localFilterRule', { deep: true })
  handleFilterRuleChange(val) {
    this.formData.filter_rules = val;
  }

  @Emit('field-change')
  handleCreateCluster() {
    return this.formData.filter_rules;
  }

  handleFieldChange(fieldName: string, index: number) {
    const field = this.totalFields.find(item => item.field_name === fieldName) ?? {};
    Object.assign(this.formData.filter_rules[index], {
      ...field,
      value: [],
    });
    const requestFields = this.fieldsKeyStrList();
    this.queryValueList(requestFields);
  }
  async queryValueList(fields = []) {
    if (!fields.length) {
      return;
    }
    const tempList = handleTransformToTimestamp(this.datePickerValue, this.$store.getters.retrieveParams.format);
    try {
      const res = await $http.request('retrieve/getAggsTerms', {
        params: {
          index_set_id: this.$route.params.indexId,
        },
        data: {
          keyword: this.retrieveParams?.keyword ?? '*',
          fields,
          start_time: formatDate(tempList[0]),
          end_time: formatDate(tempList[1]),
        },
      });
      for (const item of this.formData.filter_rules) {
        item.valueList =
          res.data.aggs_items[item.fields_name]?.map(newItem => ({
            id: newItem.toString(),
            name: newItem.toString(),
          })) ?? [];
      }
    } catch {
      for (const item of this.formData.filter_rules) {
        item.valueList = [];
      }
    }
  }
  fieldsKeyStrList() {
    const fieldsStrList = this.formData.filter_rules
      .filter(item => item.field_type !== 'text' && item.es_doc_values)
      .map(item => item.fields_name);
    return Array.from(new Set(fieldsStrList));
  }
  handleValueBlur(operateItem, val: string) {
    if (!operateItem.value.length && !!val) {
      operateItem.value.push(val);
    }
  }
  checkFilterRules() {
    if (this.formData.filter_rules.length === 1 && !this.formData.filter_rules[0].fields_name) {
      return true;
    }
    return this.formData.filter_rules.every(item => !!item.value.length && item.fields_name);
  }
  checkLIKERules() {
    this.isLikeCorrect = this.formData.filter_rules.every(item => {
      if (['NOT LIKE', 'LIKE'].includes(item.op) && !!item.value.length) {
        return /%/.test(item.value[0]);
      }
      return true;
    });
    return this.isLikeCorrect;
  }
  handleDeleteSelect(index: number) {
    this.formData.filter_rules.splice(index, 1);
    (this.$refs[`fieldSelectRef-${index}`] as any).close();
  }
  handleAddFilterRule() {
    this.formData.filter_rules.push({
      fields_name: '', // 过滤规则字段名
      op: '=', // 过滤规则操作符号
      value: [], // 过滤规则字段值
      logic_operator: 'and',
      valueList: [],
    });
    this.$nextTick(() => {
      const index = this.formData.filter_rules.length - 1;
      (this.$refs[`fieldSelectRef-${index}`] as any).show();
    });
  }
  async handleCheckRuleValidate() {
    try {
      await this.quickClusterFromRef.validate();
      return true;
    } catch {
      return false;
    }
  }
  render() {
    return (
      <bk-form
        ref='quickClusterFrom'
        ext-cls='filter-container'
        form-type='vertical'
        {...{
          props: {
            model: this.formData,
            rules: this.formRules,
          },
        }}
      >
        <bk-form-item
          label=''
          property='filter_rules'
        >
          {!this.isLikeCorrect && (
            <div class='like-error-message'>
              <i class='bk-icon icon-exclamation-circle-shape error-icon' />
              <span>{$i18n.t('使用LIKE、NOT LINK操作符时请在过滤值前后增加%')}</span>
            </div>
          )}
          <div class='filter-rule'>
            {this.formData.filter_rules.map((item, index) => (
              <div
                key={`${index}-${item}`}
                class='filter-rule filter-rule-item'
              >
                {!!this.formData.filter_rules.length && !!index && !!item.fields_name && (
                  <bk-select
                    class='icon-box and-or mr-neg1'
                    v-model={item.logic_operator}
                    clearable={false}
                  >
                    {this.comparedList.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                )}
                <bk-select
                  ref={`fieldSelectRef-${index}`}
                  class={['min-100 above mr-neg1', { 'is-not-error': !!item.fields_name }]}
                  v-model={item.fields_name}
                  clearable={false}
                  popover-min-width={150}
                  searchable
                  on-selected={fieldsName => this.handleFieldChange(fieldsName, index)}
                >
                  {this.filterSelectList.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    />
                  ))}
                  <div
                    style='cursor: pointer'
                    slot='extension'
                    onClick={() => this.handleDeleteSelect(index)}
                  >
                    <i class='bk-icon icon-close-circle' />
                    <span style='margin-left: 4px;'>{$i18n.t('删除')}</span>
                  </div>
                </bk-select>
                {!!item.fields_name && (
                  <bk-select
                    class='icon-box condition mr-neg1'
                    v-model={item.op}
                    clearable={false}
                    popover-min-width={100}
                  >
                    {this.conditionList.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                )}
                {!!item.fields_name && (
                  <div onClick={() => (this.operateIndex = index)}>
                    <bk-tag-input
                      class={['min-100 above mr-neg1', { 'is-not-error': !!item.value.length }]}
                      v-model={item.value}
                      content-width={232}
                      list={item.valueList}
                      max-data={1}
                      placeholder={$i18n.t('请输入')}
                      trigger='focus'
                      allow-auto-match
                      allow-create
                      on-blur={v => this.handleValueBlur(item, v)}
                    />
                  </div>
                )}
              </div>
            ))}
            {this.isShowAddFilterIcon && (
              <button
                class='icon-box'
                type='button'
                onClick={this.handleAddFilterRule}
              >
                <i class='bk-icon icon-plus-line' />
              </button>
            )}
          </div>
        </bk-form-item>
      </bk-form>
    );
  }
}
