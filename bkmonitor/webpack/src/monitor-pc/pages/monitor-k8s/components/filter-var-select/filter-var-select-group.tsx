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

import { deepClone } from 'monitor-common/utils/utils';

import CustomSelect from '../../../../components/custom-select/custom-select';
import { handleGetReferenceKeyList } from '../../utils';
import WhereFilters from '../where-filters/where-filters';
import FilterVarSelect, { type CustomParamsType, type FilterDictType } from './filter-var-select';

import type { IConditionItem } from '../../../../pages/strategy-config/strategy-config-set-new/monitor-data/condition-input';
import type { IVariableModel, IViewOptions, VariableModel } from 'monitor-ui/chart-plugins/typings';
const DIMENSION_LIST_KEY = 'dimension_list';
import './filter-var-select-group.scss';

export interface IApiPromiseStatus {
  component: FilterVarSelect; // 变量的组件实例
  // isReady: boolean; // 是否已经请求完毕数据
  fieldKey: string;
  reference: string[]; // 该变量的引用关系
  value?: Record<string, any>; // 变量的默认选中值
  apiStatus: {
    isReady: boolean; // 是否已经请求完毕数据
  };
}
export interface IEvents {
  onChange: FilterDictType[];
  onDataReady: FilterDictType[];
  onAddFilter: () => void;
}

export interface IProps {
  customParams?: CustomParamsType;
  editable?: boolean;
  needAddBtn: boolean;
  pageId?: string;
  panelList: IVariableModel[];
  scencId?: string;
  sceneType?: string;
  variables: Record<string, any>;
  // viewOptions?: IViewOptions;
}

@Component
export default class FilterVarSelectGroup extends tsc<IProps, IEvents> {
  /** 接口数据 */
  @Prop({ default: () => [], type: Array }) panelList: IVariableModel[];
  /** 是否为可编辑状态, 否则会默认选中第一个值 */
  @Prop({ default: false, type: Boolean }) editable: boolean;
  /** 场景id */
  @Prop({ default: 'host', type: String }) scencId: string;
  /** 场景类型 */
  @Prop({ default: 'detail', type: String }) sceneType: string;
  /** 页签id */
  @Prop({ default: '', type: String }) pageId: string;
  /** 回显数据 */
  @Prop({ default: () => ({}), type: Object }) variables: Record<string, any>;
  /** 是否需要新增按钮 */
  @Prop({ default: false, type: Boolean }) needAddBtn: boolean;
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 是否只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  /** 本地 */
  localPanelList: IVariableModel[] = [];

  /** 选中的变量值 */
  localValue: FilterDictType[] = [];

  /** 选中的变量 */
  selectedVar: string[] = [];

  /** 变量引用请求数据的状态记录 */
  varPromiseStatusMap: Record<string, IApiPromiseStatus> = {};

  /** 子组件实例 */
  get children(): FilterVarSelect[] {
    return this.$children as FilterVarSelect[];
  }

  /** 带有$开头的变量可选值映射表 */
  get varOptionalMap(): Map<string, string | string[]> {
    const varMap = new Map();
    for (const item of this.localPanelList || []) {
      for (const [key, value] of Object.entries(item.value)) {
        varMap.set(key, value);
      }
    }
    return varMap;
  }

  /** 当前选中的值 */
  get curentLocalValue() {
    const filterDict = deepClone(this.localValue).reduce((total, cur) => {
      const varItems = Object.entries(cur).reduce((vars, curVar) => {
        const [key, value] = curVar;
        if (Array.isArray(value) ? !!value.length : value !== undefined) vars[key] = value;
        return vars;
      }, {});
      // biome-ignore lint/performance/noAccumulatingSpread: <explanation>
      return { ...total, ...varItems };
    }, {});
    return filterDict;
  }

  /** 变量接口得自定义参数 */
  get filterCustomsParams() {
    const otherParams = {
      scene_id: this.scencId,
      type: this.sceneType,
      id: this.pageId,
      // view_options: viewOptions
    };
    return otherParams;
  }

  /** 变量的key数组 */
  get varKeyList() {
    return this.localPanelList.map(item => item.title);
  }
  get dimensionsPanel() {
    return this.localPanelList?.find?.(item => item.type === DIMENSION_LIST_KEY) || null;
  }

  mounted() {
    // !this.editable && this.getPromiseList();
    !this.editable && this.handleCreatePromiseMap();
  }

  @Watch('panelList', { immediate: true })
  panelListChange() {
    this.localPanelList = deepClone(this.panelList) as IVariableModel[];
  }

  /**
   * 统一管理所有变量接口请求
   * 生成一个变量请求状态的数据映射表，用于记录变量依赖的数据请求状态
   * @Pramas refresh 是否为刷新数据
   */
  async handleCreatePromiseMap(refresh = false, fieldsSort: Array<[string, string]> = []) {
    this.varPromiseStatusMap = {};
    /** 每个变量数据状态记录 */
    for (const item of this.localPanelList) {
      let needRefresh = true;
      if (refresh && fieldsSort) {
        /** 更新接口只会请求存在依赖的的变量 */
        const isExitRef = fieldsSort.some(fieldsItem => {
          const [key, value] = fieldsItem;
          const varKey = typeof value === 'object' ? key : value;
          const reg = new RegExp(`(\\$){?${varKey}}?`);
          return reg.test(JSON.stringify(item.targets));
        });
        if (!isExitRef) {
          needRefresh = false;
        }
      }
      if (item.checked && needRefresh) {
        const { fieldsKey, fieldsSort } = item;
        /** 变量接口的请求状态，引用类型来关联同一个变量的key */
        const apiStatus = {
          isReady: false,
        };
        for (const fielsItem of fieldsSort) {
          /** 提取变量引用关系 */
          const reference = handleGetReferenceKeyList(JSON.stringify(item.targets));
          // @typescript-eslint/naming-convention
          const [key, value] = fielsItem;
          const varKey = typeof value === 'object' ? key : value;
          this.varPromiseStatusMap[varKey] = {
            fieldKey: item.fieldsKey,
            reference, // 变量存在的引用
            apiStatus, // 是否再等待接口返回
            component: this.$refs[fieldsKey] as FilterVarSelect, // 对应的变量组件
          };
        }
      }
    }
    await this.$nextTick();
    const isReady = await this.handleCheckPromiseStatus();
    if (isReady && !refresh) {
      const defaultVarValueList = Object.entries(this.varPromiseStatusMap).map(item => item[1].value);
      this.handleDataReady(defaultVarValueList);
    }
  }

  /** 处理按照依赖顺序请求变量的接口 */
  handleCheckPromiseStatus() {
    const list = Object.entries(this.varPromiseStatusMap);
    return new Promise((resolve, reject) => {
      let isAllReady = false;
      const fn = async () => {
        try {
          let ready = true;
          // eslint-disable-next-line @typescript-eslint/prefer-for-of
          for (let i = 0; i < list.length; i++) {
            const data = list[i];

            const [_, item] = data;
            /** 应用变量的数据请求状态 true则全部请求完毕 */
            const refVarIsReady = this.handleCheckStatus(item.reference);
            if (!item.apiStatus.isReady && refVarIsReady) {
              item.value = item.component ? await item.component?.handleGetOptionsList().catch(() => ({})) : {};
              item.apiStatus.isReady = !!item.value;
              const currentPanel = this.localPanelList.find(set => set.fieldsKey === item.fieldKey);
              if (currentPanel) {
                currentPanel.value = { ...item.value };
              }
            }
            if (!item.apiStatus.isReady) ready = false;
          }
          /** 全部变量数据请求完毕 */
          if (ready) {
            isAllReady = true;
            resolve(true);
          }
          /** 若还存在为请求的接口则继续遍历变量的数据进行请求 */
          if (!isAllReady) fn();
        } catch (error) {
          reject(error);
        }
      };
      if (!isAllReady) fn();
    });
  }
  /** 检查变量依赖是否已经请求数据完毕 */
  handleCheckStatus(keys): boolean {
    return keys.every(key => {
      /** 判断是否为当前变量的引用 */
      if (!this.varKeyList.includes(key)) return true;
      const item = this.varPromiseStatusMap[key];
      return item ? item.apiStatus.isReady : true;
    });
  }

  /** 子组件数据都请求完成触发 */
  @Emit('dataReady')
  handleDataReady(res: FilterDictType[]): FilterDictType[] {
    return res.filter(item => !!item);
  }

  /** 子组件选择变量时候触发 */
  @Emit('change')
  handleVarChange(value: FilterDictType[]): FilterDictType[] {
    return value;
  }

  /** 单个变量选择更改值 */
  async handleVarSelectChange(item: IVariableModel, val, refresh = true) {
    item.value = val;
    this.getAllFilterDict();
    /** 变量的值变更需要重新请求数据 */
    await this.handleCreatePromiseMap(refresh, item.fieldsSort);
    const filterDict = this.getAllFilterDict();
    this.handleVarChange(filterDict);
  }

  /** 获取当前filter_dict */
  getAllFilterDict() {
    let filterDict = [];
    if (this.editable) {
      filterDict = this.localPanelList.filter(item => item.checked).map(item => item.value) as FilterDictType[];
    } else {
      filterDict = this.getAllChildrenFilterDict();
    }
    this.localValue = filterDict;
    return filterDict;
  }

  /** 获取所有子组件的值 */
  getAllChildrenFilterDict(): FilterDictType[] {
    const filterDictList: FilterDictType[] = [];
    for (const child of this.children) {
      child.localCheckedFilterDict && filterDictList.push(child.localCheckedFilterDict);
    }
    return filterDictList;
  }

  /** 选中变量 */
  handleAddVar(ids) {
    this.selectedVar = ids;
    for (const item of this.localPanelList) {
      item.checked = false;
    }
    for (const title of this.selectedVar) {
      const varOption = this.localPanelList.find(opt => opt.title === title);
      varOption.checked = true;
    }
    const filterDictList = this.localPanelList.filter(item => item.checked).map(item => item.value);
    this.handleVarChange(filterDictList);
  }

  /** 新增变量的默认值 */
  handleSetDefaultValue(item: IVariableModel, val: FilterDictType) {
    item.value = val;
    if (this.editable) {
      const filterDictList = this.localPanelList.filter(item => item.checked).map(item => item.value);
      this.handleVarChange(filterDictList);
    }
  }

  /**
   * 新增变量
   */
  @Emit('addFilter')
  handleAddFilter() {}

  @Emit('change')
  handelWhereFiltersChange(conditions: IConditionItem[]) {
    return [
      {
        [this.dimensionsPanel.fieldsKey]: conditions,
      },
    ];
  }
  render() {
    return (
      <span class='filter-var-select-group'>
        <span class='filter-var-select-group-label'>Filters :</span>
        {this.dimensionsPanel ? (
          <div class='where-filters-wrapper'>
            <WhereFilters
              ref={this.dimensionsPanel.fieldsKey}
              panel={this.dimensionsPanel as VariableModel}
              variableName={this.dimensionsPanel.fieldsKey}
              onChange={this.handelWhereFiltersChange}
            />
          </div>
        ) : (
          <div class='filter-var-select-main'>
            {this.localPanelList.map(item =>
              item.checked ? (
                <FilterVarSelect
                  key={item.title}
                  ref={item.fieldsKey}
                  autoGetOption={this.editable}
                  clearable={item.options?.variables?.clearable ?? true}
                  currentGroupValue={this.curentLocalValue}
                  customParams={this.filterCustomsParams}
                  editable={this.editable}
                  label={item.title}
                  multiple={item.options?.variables?.multiple ?? true}
                  panel={item}
                  required={item.options?.variables?.required}
                  variables={this.variables}
                  viewOptions={this.viewOptions}
                  whereRefMap={this.varOptionalMap}
                  onChange={val => this.handleVarSelectChange(item, val)}
                  onDefaultValue={val => this.handleSetDefaultValue(item, val)}
                  onValueChange={val => this.handleVarSelectChange(item, val)}
                />
              ) : undefined
            )}
            {!this.readonly && this.needAddBtn && (
              <span
                class='filter-add-btn'
                onClick={this.handleAddFilter}
              >
                <i class='icon-monitor icon-mc-add' />
              </span>
            )}
            {this.editable && (
              <CustomSelect
                class='filter-var-add'
                value={this.selectedVar}
                multiple
                onSelected={this.handleAddVar}
              >
                {this.panelList.map(opt => (
                  <bk-option
                    id={opt.title}
                    key={opt.title}
                    name={opt.title}
                  />
                ))}
              </CustomSelect>
            )}
          </div>
        )}
      </span>
    );
  }
}
