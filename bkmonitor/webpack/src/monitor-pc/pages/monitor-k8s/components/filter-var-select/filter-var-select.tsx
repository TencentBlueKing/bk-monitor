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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone, random, typeTools } from 'monitor-common/utils/utils';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
// import { getPopoverWidth } from '../../../../utils';
import FilterVarTagInput from './filter-var-tag-input';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IOption } from '../../typings';
import type { IVariableModel, IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { TranslateResult } from 'vue-i18n';

import './filter-var-select.scss';

const SPLIT_CHART = '-'; // 变量id的分隔符

export type CurrentGroupValueType = Record<string, any>;

export type CustomParamsType = { [key in string]: any };

export type FilterDictType = Record<string, string[]>;

export interface IEvents {
  onChange: FilterDictType;
  onDefaultValue: FilterDictType;
  onValueChange: FilterDictType;
}
export interface IProps {
  autoGetOption?: boolean;
  clearable?: boolean;
  currentGroupValue?: CurrentGroupValueType;
  customParams?: CustomParamsType;
  editable?: boolean;
  label?: string | TranslateResult;
  multiple?: boolean;
  panel?: IVariableModel;
  required?: boolean;
  value?: FilterDictType;
  variables: Record<string, any>;
  viewOptions: IViewOptions;
  whereRefMap: Map<string, string | string[]>;
}

type LocalValue<T extends boolean> = T extends true ? Array<number | string> : number | string;

@Component({
  name: 'FilterVarSelect',
})
export default class FilterVarSelect extends tsc<IProps, IEvents> {
  /** 图表接口数据 */
  @Prop({ type: Object }) panel: IVariableModel;
  /** 变量选择器的label */
  @Prop({ type: String }) label: string;
  /** 组件渲染是否请求可选列表接口 */
  @Prop({ default: true, type: Boolean }) autoGetOption: boolean;
  /** 多选 */
  @Prop({ default: true, type: Boolean }) multiple: boolean;
  /** 接口的其他请求参数 */
  @Prop({ default: () => ({}), type: Object }) customParams: CustomParamsType;
  /** 全部变量选中的最新值 */
  @Prop({ default: () => ({}), type: Object }) currentGroupValue: CurrentGroupValueType;
  /** 是否编辑状态, 否则会默认选中第一个值 */
  @Prop({ default: false, type: Boolean }) editable: boolean;
  /** 回显的value */
  @Prop({ type: Object }) value: FilterDictType;
  /** 是否必选 */
  @Prop({ default: false, type: Boolean }) required: boolean;
  /** 是否可清空 */
  @Prop({ default: true, type: Boolean }) clearable: boolean;
  /** 变量的引用值得映射表 用于替换变量where条件的$开头的变量*/
  @Prop({ default: () => new Map(), type: Map }) whereRefMap: Map<string, string | string[]>;
  /** 接口的过滤条件 */
  @Prop({ default: () => ({}), type: Object }) viewOptions: IViewOptions;
  /** 回显数据 */
  @Prop({ default: () => ({}), type: Object }) variables: Record<string, any>;

  /** 下拉可选项 */
  localOptions: IOption[] = [];

  /** 变量选中的值 */
  localValue: LocalValue<false> | LocalValue<true> = [];

  /* 用于初始化taginput组件 */
  tagInputKey = random(8);

  // 时间间隔
  @InjectReactive('timeRange') timeRange: TimeRangeType;

  /** 选中变量的可选项数据 */
  get localValueCheckedOptions() {
    if (this.multiple) {
      const arr = [];
      (this.localValue as LocalValue<true>).forEach(value => {
        const item = this.localOptions.find(item => item[this.localKey] === value);
        if (item) {
          arr.push(item);
        } else {
          arr.push({ [this.localKey]: value, name: value });
        }
      });
      return arr;
    }
    return this.localOptions.filter(item => this.localValue === item[this.localKey]);
  }

  /** fields list 返回[[key, value]]格式的二位数组*/
  get fieldsList(): Array<[string, string]> {
    const fields = this.panel?.targets[0]?.fields || {};
    return Object.entries(fields);
  }

  /** 与localKey相对应，当前value的key */
  get localField() {
    return this.fieldsList.find(item => item[0] === this.localKey)?.[1];
  }

  get localKey() {
    // return this.fieldsList[0]?.[0] || 'id';
    return 'id';
  }

  /** 选中的变量生成对应的filter_dict */
  get localCheckedFilterDict() {
    const filterDict: FilterDictType = {};
    this.panel.fieldsSort.reduce((total, item) => {
      const [itemKey, filterKey] = item;
      const value = this.multiple
        ? this.localValueCheckedOptions.map(opt => opt[itemKey])
        : (this.localValueCheckedOptions[0]?.[itemKey] ?? this.localValue);
      total[filterKey] = value;
      return total;
    }, filterDict);
    return filterDict;
  }

  /** 扁平化所有变量组件选中的值 */
  get currentGroupValueFlat(): CurrentGroupValueType {
    const result: CurrentGroupValueType = {};
    const fn = (data: CurrentGroupValueType) => {
      Object.entries(data).forEach(item => {
        const [key, value] = item;
        const isObject = typeTools.isObject(value);
        isObject ? fn(value) : (result[key] = value);
      });
    };
    fn(this.currentGroupValue);
    return result;
  }

  /** 多个数据接口的请求状态 */
  public apiPromise: Promise<any> = null;

  created() {
    this.autoGetOption && this.handleGetOptionsList();
    this.localValue = this.multiple ? [] : '';
    // this.editable && this.defaultValueChange();
  }

  @Watch('value', { immediate: true })
  valueChange(val: FilterDictType) {
    if (val) {
      this.localValue = this.multiple ? (val[this.localField] ?? []) : (val[this.localField] ?? '');
    }
  }

  @Watch('options', { immediate: true })
  customOptons(options: IOption[]) {
    if (options) {
      this.localOptions = deepClone(options);
    }
  }

  /** required = true 默认选中第一个 */
  handleCheckedFirstOption() {
    if (this.value) return; // 有回显值不默认选中
    const firstValue = this.localOptions[0]?.[this.localKey];
    if (this.multiple) {
      this.localValue = firstValue ? [firstValue] : [];
    } else {
      this.localValue = firstValue || '';
    }
  }

  /** 初始化回填数据 */
  displayBackValue() {
    const defaultId = this.panel.handleCreateItemId(this.variables, true);
    /** 多选的回填值 */
    const defaultIds = defaultId?.split?.(',') || [];
    let isExistOptions = true;
    const defaultIdsExist = defaultIds.filter(item => {
      const isExist = !!this.localOptions.find(set => set.id === item);
      !isExist && (isExistOptions = false);
      return isExist;
    });
    let isDisplayBackValue = false;
    /** 新选项组存在回显值时进行回填 */
    if (defaultId !== null && isExistOptions) {
      this.localValue = this.multiple ? defaultIdsExist : defaultId;
      isDisplayBackValue = true;
    }
    this.tagInputKey = random(8);
    return isDisplayBackValue;
  }

  /** 根据IVariableModel提供数据请求下拉的可选项 */
  async handleGetOptionsList() {
    await this.$nextTick();
    if (!this.required) {
      const temp = this.panel.targets?.[0].handleCreateFilterDictValue(this.variables, true);
      const data = temp || this.localCheckedFilterDict;
      this.apiPromise = Promise.resolve(data);
    }
    const promiseList = this.panel?.targets.map(async item => {
      const params = typeof item.data === 'string' ? item.data : deepClone(item.data);
      /** 当前选中的变量 */
      const selectedVar = Object.fromEntries(this.whereRefMap.entries());
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.viewOptions.variables,
        ...selectedVar,
      });
      let temp = variablesService.transformVariables(params);
      if (temp.where) {
        temp.where = temp.where.filter(item => !!item.value.length && item.value.every(val => val !== ''));
      }
      /** 合并视图相关的自定义参数 */
      temp = Object.assign(deepClone(temp), this.customParams);
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      /** 更新为当前变量选中的值 */
      Object.entries(this.currentGroupValueFlat).forEach(item => {
        const [key, value] = item;
        if (temp[key] !== undefined) temp[key] = value;
      });
      return this.$api[item.apiModule]
        [item.apiFunc]({
          ...temp,
          start_time: startTime,
          end_time: endTime,
        })
        .then(res => res?.data || res || []);
    });
    const promise = new Promise((resolve, reject) => {
      Promise.all(promiseList)
        .then(res => {
          this.localOptions = res
            .reduce((total, list) => total.concat(list), [])
            .map(item => {
              const id = this.panel.handleCreateItemId(item);
              return {
                ...item,
                id,
                name: item.name || item.ip || item.id,
              };
            });
          if (!this.editable) {
            !this.displayBackValue() && this.required && this.handleCheckedFirstOption();
          } else {
            this.defaultValueChange();
          }
          resolve(this.localCheckedFilterDict);
        })
        .catch(err => {
          console.log(err);
          reject();
        });
    });
    if (!this.required) return this.apiPromise;
    (this.required || !this.editable) && (this.apiPromise = promise);
    return this.apiPromise;
  }

  /** 根据fieldsSort来生成一个选项的id */
  createdItemId(item): string {
    const ids = this.panel.fieldsSort.reduce((total, cur) => {
      const [itemKey] = cur;
      const value = item[itemKey];
      total.push(value);
      return total;
    }, []);
    return ids.join(SPLIT_CHART);
  }

  @Emit('valueChange')
  handleValueChange() {
    return this.localCheckedFilterDict;
  }

  /** 值变更 */
  @Emit('change')
  handleSelectChange(): FilterDictType {
    return this.localCheckedFilterDict;
  }

  @Emit('defaultValue')
  defaultValueChange() {
    return this.localCheckedFilterDict;
  }

  handleTagInputChange(val) {
    this.localValue = val;
    this.handleSelectChange();
  }

  render() {
    return (
      <span class='filter-var-select-wrap'>
        {this.label && (
          <span
            class='filter-var-label'
            v-bk-tooltips={{
              content: this.panel.fieldsKey,
              zIndex: 9999,
              boundary: document.body,
              allowHTML: false,
            }}
          >
            {this.label}
          </span>
        )}
        <FilterVarTagInput
          key={this.tagInputKey}
          clearable={this.clearable}
          list={this.localOptions}
          multiple={this.multiple}
          value={this.localValue}
          onChange={this.handleTagInputChange}
        />
        {/* <bk-select
          class="bk-select-simplicity filter-var-select"
          behavior="simplicity"
          ext-popover-cls={this.localOptions.length ? '' : 'filter-var-select-options-no-data'}
          clearable={!this.required}
          multiple={this.multiple}
          v-model={this.localValue}
          searchable
          popover-width={getPopoverWidth(this.localOptions)}
          enable-virtual-scroll
          list={this.localOptions}
          onClear={this.handleSelectChange}
          onSelected={this.handleSelectChange}>
        </bk-select> */}
      </span>
    );
  }
}
