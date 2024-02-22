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
import { Component, Emit, Model, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getVariableValue } from '../../../../monitor-api/modules/grafana';
import { CONDITION, NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from '../../../constant/constant';
import SelectMenu from '../../strategy-config/strategy-config-set-new/components/select-menu';

import SimpleSelectInput from './simple-select-input';

import './simple-condition-input.scss';

const nullOptions = {
  // 下拉选项第一为空值
  id: '',
  name: `- ${window.i18n.tc('空')} -`
};

interface IConditionItem {
  key: string;
  value: string | string[];
  method: string;
  condition?: string;
  dimensionName?: string;
}
export interface IDimensionItem {
  id: string | number;
  name: string;
  type?: string;
  is_dimension?: boolean;
}

interface IMetricMeta {
  dataSourceLabel: string;
  dataTypeLabel: string;
  metricField: string;
  resultTableId: string | number;
  indexSetId?: string | number;
}

interface IProps {
  dimensionsList: IDimensionItem[];
  conditionList: IConditionItem[];
  metricMeta: IMetricMeta;
  hasLeftLabel?: boolean;
  isHasNullOption?: boolean;
}
interface IEvents {
  onChange?: void;
  onKeyLoading?: (v: boolean) => void;
}

@Component
export default class SimpleConditionInput extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) readonly dimensionsList: IDimensionItem[];
  @Model('change', { default: () => [], type: Array }) conditionList!: IConditionItem[];
  @Prop({ default: () => null, type: Object }) readonly metricMeta: IMetricMeta;
  @Prop({ default: false, type: Boolean }) isHasNullOption: boolean;
  @Prop({ default: false, type: Boolean }) hasLeftLabel: boolean;

  conditions: {
    key: string; // 维度id
    dimensionName: string; // 维度输入框的值
    value: string | string[]; // 维度值
    method?: string; // 运算符
    condition?: string; // 条件
  }[] = [];

  dimensionsValueMap: Record<string, { id: string; name: string }[]> = {};

  curSelectTarget = null;
  showSelectMenu = false;
  menuList = [];
  curConditionIndex = -1;
  curConditionProp = '';

  get showAdd() {
    if (!this.conditions.length) return false;
    const { key, value } = this.conditions[this.conditions.length - 1];
    return key && value?.length > 0;
  }

  created() {
    const conditionList = this.conditionList
      .filter(item => item.key)
      .map(item => ({
        ...item,
        dimensionName:
          item.dimensionName ||
          (item as any).dimension_name ||
          this.dimensionsList.find(dim => dim.id === item.key)?.name ||
          ''
      }));
    this.conditions = conditionList.length > 0 ? conditionList : ([this.handleGetDefaultCondition()] as any);
    this.conditions.forEach(({ key }) => {
      if (
        key &&
        !this.dimensionsValueMap[key] &&
        this.dimensionsList?.some(dim => dim.id === key && dim.is_dimension !== false)
      ) {
        this.getVariableValueList(key);
      }
    });
  }
  handleGetDefaultCondition(needCondition = true) {
    return Object.assign(
      {},
      {
        key: '',
        dimensionName: '',
        value: [],
        method: 'eq'
      },
      needCondition ? { condition: 'and' } : {}
    );
  }

  /* 弹出条件选择 */
  handleToggleCondition(e, { index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    this.menuList = CONDITION;
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  /* 弹出判断方式 */
  handleToggleMethod(e, { index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    const { key } = this.conditions[index];
    const { type } = this.dimensionsList.find(item => item.id === key) || { type: 'string' };
    this.menuList = this.handleGetMethodList(type as any);
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  /**
   * @description: 维度数据类型不同所需的method
   * @param {*} type 维度的数据类型
   */
  handleGetMethodList(type: 'string' | 'number') {
    if (type === 'number') {
      return NUMBER_CONDITION_METHOD_LIST;
    }
    return STRING_CONDITION_METHOD_LIST;
  }
  handleGetMethodNameById(id: string) {
    return NUMBER_CONDITION_METHOD_LIST.find(item => item.id === id)?.name || '';
  }

  // 粘贴条件时触发(tag-input)
  handlePaste(v, item) {
    const SYMBOL = ';';
    /** 支持 空格 | 换行 | 逗号 | 分号 分割的字符串 */
    const valList = `${v}`.replace(/(\s+)|([,;])/g, SYMBOL)?.split(SYMBOL);
    const ret = [];
    valList.forEach(val => {
      !item.value.some(v => v === val) && val !== '' && item.value.push(val);
      if (!this.dimensionsValueMap[item.key]?.some(item => item.id === val)) {
        ret.push({
          id: val,
          name: val,
          show: true
        });
      }
    });
    this.handleConditionChange();
    return ret;
  }

  // value变化时触发
  async handleValueChange(item: IConditionItem, v: string[]) {
    await this.$nextTick();
    if (item.value.includes(nullOptions.id)) {
      if (v.length > 1) {
        item.value = v.filter(str => str !== nullOptions.id);
      } else {
        item.value = v;
      }
    } else {
      if (v.includes(nullOptions.id)) {
        item.value = [nullOptions.id];
      } else {
        item.value = v;
      }
    }
    this.conditions = this.conditions.slice();
    this.handleConditionChange();
  }

  handelMenuSelect(item) {
    const condition = this.conditions[this.curConditionIndex];
    if (!condition) return;
    condition[this.curConditionProp] = item?.id;
    this.handleConditionChange();
  }

  handleMenuHidden() {
    this.curSelectTarget = null;
    this.menuList = [];
    this.showSelectMenu = false;
  }

  /* 选中维度 */
  async handleKeyChange(item: IConditionItem, v: string) {
    this.$emit('key-loading', true);
    if (!v && this.conditions.length > 1) this.handleDeleteKey(this.conditionList.length - 1);
    item.dimensionName = v;
    let id = v;
    this.dimensionsList.forEach(item => {
      if (item.id === v || item.name === v) {
        id = item.id as string;
      }
    });
    if (item.key !== id) {
      item.value = [];
    }
    item.key = id;
    if (
      id &&
      !this.dimensionsValueMap[id] &&
      this.dimensionsList?.some(dim => dim.id === id && dim.is_dimension !== false)
    ) {
      await this.getVariableValueList(id);
    }
    this.conditions = this.conditions.slice();
    this.handleConditionChange();
    this.$emit('key-loading', false);
  }

  // 获取维度值列表数据
  async getVariableValueList(keyId: string) {
    /** 自定义请求维度列表数据的api */
    if (!this.metricMeta) return;
    const { dataSourceLabel, metricField, dataTypeLabel, resultTableId } = this.metricMeta;
    if (!dataSourceLabel || !metricField || !dataTypeLabel) return;
    const params = {
      bk_biz_id: this.$store.getters.bizId,
      type: 'dimension',
      params: Object.assign(
        {
          data_source_label: dataSourceLabel,
          data_type_label: dataTypeLabel,
          field: keyId,
          metric_field: metricField,
          result_table_id: resultTableId || '',
          where: []
        },
        this.metricMeta.dataSourceLabel === 'bk_log_search'
          ? {
              index_set_id: this.metricMeta.indexSetId
            }
          : {}
      )
    };
    await getVariableValue(params, { needRes: true })
      .then(({ data, tips }) => {
        if (tips?.length) {
          this.$bkMessage({
            theme: 'warning',
            message: tips
          });
        }
        const result = Array.isArray(data) ? data.map(item => ({ name: item.label, id: item.value })) : [];
        const { field } = params.params;
        this.$set(this.dimensionsValueMap, field, result || []);
      })
      .catch(() => []);
  }

  /**
   * @description: 添加条件
   */
  async handleAddCondition() {
    this.conditions.push(this.handleGetDefaultCondition());
    setTimeout(() => {
      (this.$refs[`selectInput${this.conditions.length - 1}`] as SimpleSelectInput).inputWrapRef.click();
      (this.$refs[`selectInput${this.conditions.length - 1}`] as SimpleSelectInput).inputRef.focus();
    }, 100);
  }

  /* 删除条件 */
  handleDeleteKey(index: number) {
    const deleteList = this.conditions.splice(index, 1);
    if (!this.conditions.length) {
      this.conditions.push(this.handleGetDefaultCondition(false));
    } else {
      if (this.conditions[index] && (this.conditions[index - 1]?.condition || index === 0)) {
        delete this.conditions[index].condition;
      }
    }
    !!deleteList?.[0]?.key && this.handleConditionChange();
  }

  @Emit('change')
  handleConditionChange() {
    return this.conditions;
  }

  /* 获取当前条件的可选值 */
  getValueOptions(item) {
    return this.dimensionsValueMap[item.key] ? [nullOptions].concat(this.dimensionsValueMap[item.key]) : [nullOptions];
  }

  render() {
    return (
      <div class='simple-condition-input-component'>
        {this.hasLeftLabel && <span class='condition-item condition-item-label'>{this.$t('条件')}</span>}
        {this.conditions.map((item, index) => [
          item.condition && item.key && index > 0 ? (
            <input
              style={{ display: item.condition ? 'block' : 'none' }}
              key={`condition-${index}-${item.key}`}
              class='condition-item condition-item-condition'
              readonly
              value={item.condition.toLocaleUpperCase()}
              on-click={e => this.handleToggleCondition(e, { index, prop: 'condition' })}
            />
          ) : undefined,
          <SimpleSelectInput
            ref={`selectInput${index}`}
            value={item.dimensionName}
            list={this.dimensionsList as any}
            placeholder={window.i18n.t('输入维度名称') as string}
            v-bk-tooltips={{
              content: item.key,
              trigger: 'mouseenter',
              zIndex: 9999,
              disabled: !item.key,
              boundary: document.body,
              allowHTML: false
            }}
            nodataMsg={window.i18n.t('该策略无可选维度') as string}
            onChange={v => this.handleKeyChange(item, v)}
          >
            <div
              style={{ display: item.key ? 'flex' : 'none' }}
              slot='extension'
              class='extension'
              on-click={() => this.handleDeleteKey(index)}
            >
              <i class='icon-monitor icon-chahao'></i>
              <span>{this.$t('删除')}</span>
            </div>
          </SimpleSelectInput>,
          item.dimensionName
            ? [
                <span
                  class='condition-item condition-item-method'
                  key={`method-${index}-${item.key}`}
                  on-click={e => this.handleToggleMethod(e, { index, prop: 'method' })}
                >
                  {this.handleGetMethodNameById(item.method)}
                </span>,
                <bk-tag-input
                  key={`value-${index}-${item.key}-${JSON.stringify(this.dimensionsValueMap[item.key] || [])}`}
                  class='condition-item condition-item-value'
                  list={
                    this.dimensionsValueMap[item.key]
                      ? (this.isHasNullOption ? [nullOptions] : []).concat(this.dimensionsValueMap[item.key])
                      : this.isHasNullOption
                        ? [nullOptions]
                        : []
                  }
                  trigger='focus'
                  has-delete-icon
                  allow-create
                  allow-auto-match
                  value={item.value}
                  paste-fn={v => this.handlePaste(v, item)}
                  on-change={(v: string[]) => this.handleValueChange(item, v)}
                ></bk-tag-input>
              ]
            : undefined
        ])}
        <span
          class='condition-item condition-add'
          style={{ display: this.showAdd ? 'flex' : 'none' }}
          on-click={() => this.handleAddCondition()}
        >
          <i class='bk-icon icon-plus'></i>
        </span>
        <SelectMenu
          show={this.showSelectMenu}
          target={this.curSelectTarget}
          list={this.menuList}
          min-width={60}
          on-on-select={item => this.handelMenuSelect(item)}
          on-on-hidden={() => this.handleMenuHidden()}
        ></SelectMenu>
      </div>
    );
  }
}
