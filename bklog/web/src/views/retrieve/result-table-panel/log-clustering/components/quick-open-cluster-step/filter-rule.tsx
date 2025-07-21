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

import { From } from 'bk-magic-vue';
import {
  Component,
  Prop,
  Emit,
  Ref,
  ModelSync,
  Watch,
} from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import $http from '../../../../../../api';
import { formatDate } from '../../../../../../common/util';
import { handleTransformToTimestamp } from '../../../../../../components/time-range/utils';

import './filter-rule.scss';

interface IProps {
  totalFields: Array<any>;
}

const { $i18n } = window.mainComponent;

@Component
export default class QuickOpenCluster extends tsc<IProps> {
  @ModelSync('value', 'change', { type: Array }) localFilterRule!: Array<any>;
  @Prop({ required: true, type: Array }) totalFields: Array<any>;
  @Prop({ required: true, type: Array }) datePickerValue: Array<any>;
  @Prop({ required: true, type: Object }) retrieveParams: object;
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
        trigger: 'blur',
        validator: this.checkFilterRules,
      },
      {
        trigger: 'change',
        validator: this.checkLIKERules,
      },
    ],
  };

  get isShowAddFilterIcon() {
    const rules = this.formData.filter_rules;
    if (
      !rules.length ||
      (rules.slice(-1)[0].fields_name !== '' && rules.length === 1) ||
      rules.slice(-1)[0].value.length > 0
    )
      return true;
    return false;
  }

  get filterSelectList() {
    return this.totalFields
      .filter(
        (item) =>
          !/^__dist/.test(item.field_name) && item.field_type !== '__virtual__'
      )
      .map((el) => {
        const { field_alias: alias, field_name: id } = el;
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
    const field =
      this.totalFields.find((item) => item.field_name === fieldName) ?? {};
    Object.assign(this.formData.filter_rules[index], {
      ...field,
      value: [],
    });
    const requestFields = this.fieldsKeyStrList();
    this.queryValueList(requestFields);
  }
  async queryValueList(fields = []) {
    if (!fields.length) return;
    const tempList = handleTransformToTimestamp(
      this.datePickerValue,
      this.$store.getters.retrieveParams.format
    );
    try {
      const res = await $http.request('retrieve/getAggsTerms', {
        data: {
          end_time: formatDate(tempList[1]),
          fields,
          keyword: this.retrieveParams?.keyword ?? '*',
          start_time: formatDate(tempList[0]),
        },
        params: {
          index_set_id: this.$route.params.indexId,
        },
      });
      this.formData.filter_rules.forEach((item) => {
        item.valueList =
          res.data.aggs_items[item.fields_name]?.map((item) => ({
            id: item.toString(),
            name: item.toString(),
          })) ?? [];
      });
    } catch (err) {
      this.formData.filter_rules.forEach((item) => (item.valueList = []));
    }
  }
  fieldsKeyStrList() {
    const fieldsStrList = this.formData.filter_rules
      .filter((item) => item.field_type !== 'text' && item.es_doc_values)
      .map((item) => item.fields_name);
    return Array.from(new Set(fieldsStrList));
  }
  handleValueBlur(operateItem, val: string) {
    if (!operateItem.value.length && !!val) operateItem.value.push(val);
  }
  checkFilterRules() {
    if (
      this.formData.filter_rules.length === 1 &&
      !this.formData.filter_rules[0].fields_name
    )
      return true;
    return this.formData.filter_rules.every(
      (item) => !!item.value.length && item.fields_name
    );
  }
  checkLIKERules() {
    this.isLikeCorrect = this.formData.filter_rules.every((item) => {
      if (['NOT LIKE', 'LIKE'].includes(item.op) && !!item.value.length)
        return /%/.test(item.value[0]);
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
      logic_operator: 'and',
      op: '=', // 过滤规则操作符号
      value: [], // 过滤规则字段值
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
    } catch (error) {
      return false;
    }
  }
  render() {
    return (
      <bk-form
        ext-cls="filter-container"
        form-type="vertical"
        ref="quickClusterFrom"
        {...{
          props: {
            model: this.formData,
            rules: this.formRules,
          },
        }}
      >
        <bk-form-item label="" property="filter_rules">
          {!this.isLikeCorrect && (
            <div class="like-error-message">
              <i class="bk-icon icon-exclamation-circle-shape error-icon"></i>
              <span>
                {$i18n.t('使用LIKE、NOT LINK操作符时请在过滤值前后增加%')}
              </span>
            </div>
          )}
          <div class="filter-rule">
            {this.formData.filter_rules.map((item, index) => (
              <div class="filter-rule filter-rule-item">
                {!!this.formData.filter_rules.length &&
                  !!index &&
                  !!item.fields_name && (
                    <bk-select
                      class="icon-box and-or mr-neg1"
                      clearable={false}
                      v-model={item.logic_operator}
                    >
                      {this.comparedList.map((option) => (
                        <bk-option
                          id={option.id}
                          name={option.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  )}
                <bk-select
                  class={[
                    'min-100 mr-neg1 above',
                    { 'is-not-error': !!item.fields_name },
                  ]}
                  clearable={false}
                  on-selected={(fieldsName) =>
                    this.handleFieldChange(fieldsName, index)
                  }
                  popover-min-width={150}
                  ref={`fieldSelectRef-${index}`}
                  searchable
                  v-model={item.fields_name}
                >
                  {this.filterSelectList.map((option) => (
                    <bk-option id={option.id} name={option.name}></bk-option>
                  ))}
                  <div
                    onClick={() => this.handleDeleteSelect(index)}
                    slot="extension"
                    style="cursor: pointer"
                  >
                    <i class="bk-icon icon-close-circle"></i>
                    <span style="margin-left: 4px;">{$i18n.t('删除')}</span>
                  </div>
                </bk-select>
                {!!item.fields_name && (
                  <bk-select
                    class="icon-box mr-neg1 condition"
                    clearable={false}
                    popover-min-width={100}
                    v-model={item.op}
                  >
                    {this.conditionList.map((option) => (
                      <bk-option id={option.id} name={option.name}></bk-option>
                    ))}
                  </bk-select>
                )}
                {!!item.fields_name && (
                  <div onClick={() => (this.operateIndex = index)}>
                    <bk-tag-input
                      allow-auto-match
                      allow-create
                      class={[
                        'mr-neg1 min-100 above',
                        { 'is-not-error': !!item.value.length },
                      ]}
                      content-width={232}
                      list={item.valueList}
                      max-data={1}
                      on-blur={(v) => this.handleValueBlur(item, v)}
                      placeholder={$i18n.t('请输入')}
                      trigger="focus"
                      v-model={item.value}
                    ></bk-tag-input>
                  </div>
                )}
              </div>
            ))}
            {this.isShowAddFilterIcon && (
              <button class="icon-box" onClick={this.handleAddFilterRule}>
                <i class="bk-icon icon-plus-line"></i>
              </button>
            )}
          </div>
        </bk-form-item>
      </bk-form>
    );
  }
}
