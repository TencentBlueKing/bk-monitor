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

import { getVariableValue } from 'monitor-api/modules/grafana';

import { CONDITION, NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from '../../../../constant/constant';
import { getPopoverWidth } from '../../../../utils';
import SelectMenu from '../components/select-menu';

import type { ICommonItem } from '../typings';

import './condition-input.scss';

const nullOptions = {
  // 下拉选项第一为空值
  id: '',
  name: `- ${window.i18n.tc('空')} -`,
};
export type GetVarApiType = (field: string) => Promise<IVarOption[]>;
export interface IConditionItem {
  condition?: string;
  key: string;
  method: string;
  value: string | string[];
}
export interface IVarOption {
  id: string;
  name: string;
}
interface IConditionInputProps {
  conditionList: IConditionItem[];
  dimensionsList?: ICommonItem[];
  getDataApi?: GetVarApiType;
  metricMeta?: IMetricMeta;
  title?: string;
  /* 选择维度自动填充默认值 */
  defaultValue?: {
    [propName: string]: string[];
  };
}
interface IMetricMeta {
  dataSourceLabel: string;
  dataTypeLabel: string;
  indexSetId?: number | string;
  metricField: string;
  resultTableId: number | string;
}
@Component({
  name: 'ConditionInput',
})
export default class ConditionInput extends tsc<
  IConditionInputProps,
  {
    onChange: (value: IConditionItem[]) => void;
  }
> {
  @Prop({ required: true, type: Array }) readonly dimensionsList: any[];
  @Prop({ required: false, type: Object }) readonly metricMeta: IMetricMeta;
  @Prop({ type: String, default: window.i18n.tc('条件') }) readonly title: string;
  /** 自定义的请求接口，传入时候不传指标数据metricMeta */
  @Prop({ type: Function }) readonly getDataApi: GetVarApiType;
  @Prop({ default: () => ({}), type: Object }) defaultValue: IConditionInputProps['defaultValue'];

  @Model('change', { default: () => [], type: Array }) conditionList!: any[];

  conditions = [];

  menuList = [];
  showSelectMenu = false;
  curSelectTarget = null;
  curConditionIndex = -1;
  curConditionProp = '';
  dimensionsValueMap: Record<string, { id: string; name: string }[]> = {};
  dimensionsValueMapLoading: Record<string, boolean> = {};
  get showAdd() {
    if (!this.conditions.length) return false;
    const { key, value } = this.conditions[this.conditions.length - 1];
    return key && value?.length > 0;
  }

  /**
   * @description: 条件值变更
   */
  @Emit('change')
  handleConditionChange() {
    return this.conditions;
  }

  /**
   * @description: 清除条件
   */
  @Emit('clear-value')
  emitClearValue(item) {
    return item;
  }

  async created() {
    const conditionList = this.conditionList.filter(item => item.key);
    conditionList.length &&
      (this.metricMeta?.metricField || !!this.getDataApi) &&
      Promise.all(conditionList.map(item => this.getVariableValueList(item.key)));
    // 初始化conditions
    this.conditions = conditionList.length > 0 ? conditionList : [this.handleGetDefaultCondition()];
  }

  /**
   * @description: 添加条件
   */
  async handleAddCondition() {
    const len = this.conditions.push(this.handleGetDefaultCondition());
    await this.$nextTick();
    (this.$refs[`key-${len - 1}`] as any).show();
  }

  handleMenuDelete() {}

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

  handleDeleteKey(index: number) {
    const deleteList = this.conditions.splice(index, 1);
    if (!this.conditions.length) {
      this.conditions.push(this.handleGetDefaultCondition(false));
    } else {
      if (this.conditions[index] && index === 0) {
        // biome-ignore lint/performance/noDelete: <explanation>
        delete this.conditions[index].condition;
      }
    }
    !!deleteList?.[0]?.key && this.handleConditionChange();
  }

  handleToggleKey(show: boolean, index: number) {
    if (!show && !this.conditions[index].key) {
      this.handleDeleteKey(index);
    }
  }

  handleToggleMethod(e, { index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    const { key } = this.conditions[index];
    const { type } = this.dimensionsList.find(item => item.id === key) || { type: 'string' };
    this.menuList = this.handleGetMethodList(type);
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  handleToggleCondition(e, { index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    this.menuList = CONDITION;
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  /**
   * @description: 维度数据类型不同所需的method
   * @param {*} type 维度的数据类型
   */
  handleGetMethodList(type: 'number' | 'string') {
    if (type === 'number') {
      return NUMBER_CONDITION_METHOD_LIST;
    }
    return STRING_CONDITION_METHOD_LIST;
  }

  handleGetMethodNameById(id: string) {
    return NUMBER_CONDITION_METHOD_LIST.find(item => item.id === id)?.name || '';
  }

  handleGetDefaultCondition(needCondition = true) {
    return Object.assign(
      {},
      {
        key: '',
        value: [],
        method: 'eq',
      },
      needCondition ? { condition: 'and' } : {}
    );
  }
  // key变化时触发
  async handleKeyChange(item: IConditionItem, v: string) {
    this.$emit('key-loading', true);
    if (item.key !== v) {
      item.value = [];
    }
    item.key = v;
    if (this.defaultValue[item.key] !== undefined && Array.isArray(item.value) && !item.value.length) {
      const value = this.defaultValue[item.key];
      item.value = item.value.concat(value).filter((value, index, arr) => arr.indexOf(value) === index);
    }
    if (v && !this.dimensionsValueMap[v]) {
      await this.getVariableValueList(v);
    }
    this.conditions = this.conditions.slice();
    this.handleConditionChange();
    this.$emit('key-loading', false);
  }
  handleRenderDimensionList(dimension) {
    return (
      <bk-option
        id={dimension.id}
        key={dimension.id}
        name={dimension.name}
      >
        <span
          v-bk-tooltips={{
            content: dimension.id,
            placement: 'right',
            zIndex: 9999,
            boundary: document.body,
            appendTo: document.body,
            allowHTML: false,
          }}
        >
          {dimension.name}
        </span>
      </bk-option>
    );
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
  // 获取维度值列表数据
  async getVariableValueList(keyId: string) {
    /** 自定义请求维度列表数据的api */
    if (this.getDataApi) {
      this.$set(this.dimensionsValueMapLoading, keyId, true);
      return this.getDataApi(keyId)
        .then(data => {
          this.dimensionsValueMap[keyId] = data || [];
        })
        .finally(() => {
          this.$set(this.dimensionsValueMapLoading, keyId, false);
        });
    }
    const { dataSourceLabel, metricField, dataTypeLabel, resultTableId } = this.metricMeta;
    if (!dataSourceLabel || !metricField || !dataTypeLabel || !resultTableId) return;
    const params = {
      bk_biz_id: this.$store.getters.bizId,
      type: 'dimension',
      params: Object.assign(
        {
          data_source_label: this.metricMeta.dataSourceLabel,
          data_type_label: this.metricMeta.dataTypeLabel,
          field: keyId,
          metric_field: this.metricMeta.metricField,
          result_table_id: this.metricMeta.resultTableId,
          where: [],
        },
        this.metricMeta.dataSourceLabel === 'bk_log_search'
          ? {
              index_set_id: this.metricMeta.indexSetId,
            }
          : {}
      ),
    };
    const { field } = params.params;
    this.$set(this.dimensionsValueMapLoading, field, true);
    await getVariableValue(params, { needRes: true })
      .then(({ data, tips }) => {
        if (tips?.length) {
          this.$bkMessage({
            theme: 'warning',
            message: tips,
          });
        }
        const result = Array.isArray(data) ? data.map(item => ({ name: item.label.toString(), id: item.value })) : [];
        this.dimensionsValueMap[field] = result || [];
      })
      .catch(() => []);
    this.$set(this.dimensionsValueMapLoading, field, false);
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
          show: true,
        });
      }
    });
    this.handleConditionChange();
    return ret;
  }
  /**
   * 获取当前条件的可选值
   * @param item
   * @returns
   */
  getValueOptions(item) {
    return this.dimensionsValueMap[item.key] ? [nullOptions].concat(this.dimensionsValueMap[item.key]) : [nullOptions];
  }
  getValueOptionsLoading(item) {
    return !!this.dimensionsValueMapLoading?.[item.key];
  }
  render() {
    return (
      <span class='condition'>
        {this.title && <span class='condition-item condition-item-label'>{this.title}</span>}
        {this.conditions.map((item, index) => [
          item.condition && item.key && index > 0 ? (
            <input
              key={`condition-${index}-${item.key}`}
              style={{ display: item.condition ? 'block' : 'none' }}
              class='condition-item condition-item-condition'
              value={item.condition.toLocaleUpperCase()}
              readonly
              on-click={e => this.handleToggleCondition(e, { index, prop: 'condition' })}
            />
          ) : undefined,
          <bk-select
            key={`key-${index}-${item.key}`}
            ref={`key-${index}`}
            class='condition-item condition-item-key'
            v-bk-tooltips={{
              content: item.key,
              trigger: 'mouseenter',
              zIndex: 9999,
              disabled: !item.key,
              boundary: document.body,
              allowHTML: false,
            }}
            clearable={false}
            popover-min-width={200}
            popover-width={getPopoverWidth(this.dimensionsList)}
            value={item.key}
            searchable
            on-change={v => this.handleKeyChange(item, v)}
            on-toggle={e => this.handleToggleKey(e, index)}
          >
            {this.dimensionsList.map(dimension => this.handleRenderDimensionList(dimension))}
            <div
              style={{ display: item.key ? 'flex' : 'none' }}
              class='extension'
              slot='extension'
              on-click={() => this.handleDeleteKey(index)}
            >
              <i class='icon-monitor icon-chahao' />
              <span>{this.$t('删除')}</span>
            </div>
          </bk-select>,
          item.key && [
            <span
              key={`method-${index}-${item.key}`}
              class='condition-item condition-item-method'
              on-click={e => this.handleToggleMethod(e, { index, prop: 'method' })}
            >
              {this.handleGetMethodNameById(item.method)}
            </span>,
            this.getValueOptionsLoading(item) ? (
              <span
                key={`value-${index}-${item.key}`}
                class='condition-item condition-item-value-loading'
              >
                <div class='spinner' />
              </span>
            ) : (
              <bk-tag-input
                key={`value-${index}-${item.key}-${JSON.stringify(this.dimensionsValueMap[item.key] || [])}`}
                class='condition-item condition-item-value'
                content-width={getPopoverWidth(this.getValueOptions(item), 20, 190)}
                list={this.getValueOptions(item)}
                paste-fn={v => this.handlePaste(v, item)}
                trigger='focus'
                value={item.value}
                allow-auto-match
                allow-create
                has-delete-icon
                on-change={(v: string[]) => this.handleValueChange(item, v)}
              />
            ),
          ],
        ])}
        <span
          style={{ display: this.showAdd ? 'flex' : 'none' }}
          class='condition-item condition-add'
          on-click={() => this.handleAddCondition()}
        >
          <i class='bk-icon icon-plus' />
        </span>
        <SelectMenu
          list={this.menuList}
          min-width={60}
          show={this.showSelectMenu}
          target={this.curSelectTarget}
          on-on-delete={() => this.handleMenuDelete()}
          on-on-hidden={() => this.handleMenuHidden()}
          on-on-select={item => this.handelMenuSelect(item)}
        />
        <slot />
      </span>
    );
  }
}
