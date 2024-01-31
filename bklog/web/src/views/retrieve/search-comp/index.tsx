/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import {
  Component,
  Prop,
  Provide,
  Emit,
  Ref,
  Watch,
} from 'vue-property-decorator';
import $http from '../../../api';
import './index.scss';
import HandleBtn from './handle-btn';
import { Button, Select, Option } from 'bk-magic-vue';
import RetrieveDetailInput from '../condition-comp/retrieve-detail-input.vue';
import QueryStatement from './query-statement';
import Condition from './condition';
import UiQuery from './ui-query';
import { formatDate } from '@/common/util';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { deepClone } from '../../../components/monitor-echarts/utils';
import { Debounce } from '../../../common/util';

interface IProps {
  tableLoading: boolean;
  isAutoQuery: boolean;
  isSearchAllowed: boolean | unknown;
  activeFavoriteID: number;
  isCanStorageFavorite: boolean;
  retrieveParams: object;
  activeFavorite: object;
  isSqlSearchType: boolean;
  visibleFields: Array<[]>;
  indexSetList: Array<[]>;
  historyRecords: Array<[]>;
  retrievedKeyword: string;
  isFavoriteSearch: boolean;
  isShowUiType: boolean;
  favSearchList: Array<string>;
  datePickerValue: Array<any>;
  fieldAliasMap: object;
  totalFields: Array<any>;
}

interface ITagFocusInputObj {
  index?: number;
  str?: string;
}

@Component
export default class SearchComp extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) tableLoading: boolean; // 检索中
  @Prop({ type: Boolean, default: false }) isAutoQuery: boolean; // 是否自动查询
  @Prop({ required: true }) isSearchAllowed: any; // 是否有检索权限
  @Prop({ type: Number, required: true }) activeFavoriteID: number; // 当前点击收藏的ID
  @Prop({ type: Boolean, required: true }) isCanStorageFavorite: boolean; // 是否能保存收藏
  @Prop({ type: Object, required: true }) retrieveParams: any; // 检索条件参数
  @Prop({ type: String, required: true }) indexId: string; // 索引ID
  @Prop({ type: Object, required: true }) activeFavorite: object; // 当前活跃的收藏数据
  @Prop({ type: Array, required: true }) visibleFields: Array<[]>; // 表格展示的字段列表
  @Prop({ type: Array, required: true }) indexSetList: Array<[]>; // 索引列表
  @Prop({ type: Boolean, required: true }) isSqlSearchType: boolean; // 是否是Sql搜索模式
  @Prop({ type: Array, required: true }) historyRecords: Array<[]>; // 检索历史列表
  @Prop({ type: String, required: true }) retrievedKeyword: string; // 检索语句
  @Prop({ type: Object, required: true }) retrieveDropdownData: any; // 检索框下拉数据
  @Prop({ type: Boolean, required: true }) isFavoriteSearch: boolean; // 当前是否是收藏检索
  @Prop({ type: Boolean, required: true }) isShowUiType: boolean; // 是否展示Sql / UI切换
  @Prop({ type: Array, required: true }) favSearchList: Array<string>; // 收藏名称列表
  @Prop({ type: Array, required: true }) datePickerValue:  Array<any>; //
  @Prop({ type: Object, required: true }) fieldAliasMap: object;
  @Prop({ type: Array, required: true }) totalFields: Array<any>; // 所有字段
  @Prop({ type: Object, required: true }) catchIpChooser: object; // ip选择器缓存数据

  @Ref('uiQuery') private readonly uiQueryRef; // 操作列表实例

  inputSearchList = []; // ui模式检索语句生成的键名
  filedSelectedValue = null; // 添加条件下拉框的key
  conditionList = []; // 条件列表
  isShowFilterOption = false; // 添加条件下拉框是否是展开状态
  aggsItems = []; // 接口返回输入框可选值
  /** 检索时，清空输入框内缓存的字符串 */
  isClearCatchInputStr = false;
  tagFocusInputObj: ITagFocusInputObj = {
    index: 0,
    str: '',
  };

  get isCanUseUiType() { // 判断当前的检索语句生成的键名和操作符是否相同 不相等的话不能切换表单模式
    return this.inputSearchList.some(v => this.favSearchList.includes(v));
  }

  get IPSelectIndex() { // 是否已选ip选择器 并找出下标
    return this.conditionList.findIndex(item => item.conditionType === 'ip-select');
  }

  get fieldsKeyStrList() { // 去重后的当前条件字段数组
    const fieldsStrList = this.conditionList.filter((item) => {
      return item.conditionType !== 'ip-select' && item.fieldType !== 'text' && item.esDocValues;
    }).map(item => item.id);
    return Array.from(new Set(fieldsStrList));
  }

  get fieldLength() {
    return this.conditionList.filter(item => item.conditionType !== 'ip-select').length;
  }

  get filterFields() { // 所有的过滤条件列表
    // 判断当前列表是否需要展示ip选择器
    const isShowIpSelect = this.totalFields.some(item => item.field_name === '__ext.container_id');
    const result = !isShowIpSelect ? [{
      id: 'ip-select',
      name: window.mainComponent.$t('IP目标'),
      fullName: window.mainComponent.$t('IP目标'),
      fieldType: 'ip-select',
      disabled: this.IPSelectIndex > -1,
      disabledContent: window.mainComponent.$t('已经被选择'),
      isInclude: true, // 是否查询包含
      operator: '', // 操作符
      operatorList: [], // 操作符列表
      operatorItem: {}, // 当前的操作符元素
      conditionType: 'ip-select',
      value: [], // 值
      valueList: [], // taginput的输入框列表
      esDocValues: false,
    }] : [];

    this.totalFields.forEach((item) => {
      // 操作符列表为undefined或者没数据时不加入过滤条件
      if (!Array.isArray(item.field_operator) || !item.field_operator.length) return;
      const fieldName = item.field_name;
      const alias = this.fieldAliasMap[fieldName];
      result.push({
        id: fieldName,
        name: fieldName,
        fullName: (alias && alias !== fieldName) ? `${fieldName} (${alias})` : fieldName,
        fieldType: item.field_type,
        disabled: false,
        disabledContent: '',
        isInclude: true,
        operator: item.field_operator[0].operator,
        conditionType: 'filed',
        operatorList: item.field_operator,
        operatorItem: item.field_operator[0],
        value: [],
        valueList: [],
        esDocValues: item.es_doc_values,
      });
    });

    // 禁用排序
    const disabledList = [];
    const unDisabledList = result.reduce((pre, cur) => {
      cur.disabled ? disabledList.push(cur) : pre.push(cur);
      return pre;
    }, []);
    return [...unDisabledList, ...disabledList];
  }

  get ipChooserIsOpen() { // ip选择器开关
    return this.conditionList.find(item => item.conditionType === 'ip-select')?.isInclude ?? false;
  }

  get keywordAndFields() {
    return `${this.retrievedKeyword}_${this.fieldsKeyStrList.join(',')}`;
  }

  @Watch('keywordAndFields', { immediate: true })
  getValueList() {
    this.queryValueList(this.fieldsKeyStrList);
  }

  @Watch('datePickerValue')
  handleDatePickerValueChange() {
    this.queryValueList(this.fieldsKeyStrList);
  }

  @Watch('fieldLength', { immediate: true })
  setValueList() {
    this.initValueList();
  }

  @Provide('handleUserOperate')
  handleUserOperate(type: string, value: any, isFunction = false) {
    this.handleValueChange({ type, value, isFunction });
  }

  @Emit('emitChangeValue')
  handleValueChange(operate) {
    return operate;
  }

  @Emit('retrieveLog')
  handleRetrieveLog(retrieveValue?) {
    return retrieveValue;
  }

  @Emit('clearCondition')
  handleClearCondition(str: string) {
    (this.uiQueryRef as any)?.clearCondition();
    return str;
  }

  @Emit('updateSearchParam')
  handleUpdateSearchParam(keyword, addition, host) {
    return { keyword, addition, host };
  }

  @Emit('updateKeyWords')
  handleUpdateKeyWords(str: string) {
    return str;
  }

  @Emit('searchAddChange') // 添加条件检索
  handleSearchAddChange(addition, isQuery: boolean, isForceQuery: boolean) {
    return { addition, isQuery, isForceQuery };
  }

  @Emit('openIpQuick')
  handleOpenIpQuick() {}

  @Emit('ipSelectorValueClear')
  handleIPSelectorValueChange(v = {}, isChangeCatch = false) {
    return { v, isChangeCatch };
  }

  handleClickSearchType() {  // UI模式和Lucene模式切换
    this.handleRetrieveLog();
    this.handleBlurSearchInput(this.retrieveParams.keyword);
    // 切换表单模式或者sql模式
    this.handleUserOperate('isSqlSearchType', !this.isSqlSearchType);
    // 如果是sql模式切到表单模式 则缓存keywords  表单切回sql模式时回填缓存的keywords
  }

  // 添加条件按钮 添加条件
  handleToggleChange(isOpen: boolean) {
    this.isShowFilterOption = isOpen;
  }

  handleSelectFiled(v) {
    const condition = this.filterFields.find(fItem => fItem.id === v);
    this.conditionList.push(deepClone(condition));
    this.filedSelectedValue = null;
    this.isShowFilterOption = false;
  }

  /**
   * @desc: 初始化条件列表
   * @param {Array} initAddition 路由的字段条件参数
   * @param {Object} initIPChooser 路由的ip选择器参数
   * @param {Boolean} chooserSwitch 路由的ip选择器是否打开
   */
  initConditionList(initAddition, initIPChooser, chooserSwitch = true) {
    const addition = initAddition ?? this.retrieveParams.addition;
    const ipChooser = initIPChooser ?? this.retrieveParams.ip_chooser;
    this.conditionList = [];
    const isHaveIP = Boolean(Object.keys(ipChooser).length);
    if (isHaveIP) {
      this.pushCondition('ip-select', '', ipChooser, chooserSwitch);
    }
    this.initAdditionDefault(addition);
    this.setRouteParams(isHaveIP ? ipChooser : {});
  }

  setIPChooserFilter(value) { // 更新ip选择器的参数
    const isHaveIP = Boolean(Object.keys(value).length);
    this.setRouteParams(value, !isHaveIP);
  }

  // 改变条件时 更新路由参数
  setRouteParams(ipChooser = {}, deleteIpValue = false, linkAddition = null) {
    const { params, query } = this.$route;
    const { ip_chooser, isIPChooserOpen, addition, ...reset } = query;
    const filterQuery = reset; // 给query排序 让addition和ip_chooser排前面
    const newQueryObj = { addition: this.getFiledAdditionStr(linkAddition) }; // 新的query对象
    const newIPChooser = Object.keys(ipChooser).length ? ipChooser : query.ip_chooser;

    if (newIPChooser && Object.keys(newIPChooser).length) { // ip值更新
      Object.assign(newQueryObj, {
        ip_chooser: this.getIPChooserStr(newIPChooser),
        isIPChooserOpen: this.ipChooserIsOpen,
      });
    };

    if (deleteIpValue) { // 清空ip值
      delete (newQueryObj as any).ip_chooser;
      delete (newQueryObj as any).isIPChooserOpen;
    }

    Object.assign(filterQuery, newQueryObj);
    const routeData = {
      name: 'retrieve',
      params,
      query: filterQuery,
    };
    if (linkAddition) return this.$router.resolve(routeData).href;
    this.$router.replace(routeData);
  }

  // 获取有效的字段条件字符串
  getFiledAdditionStr(linkAddition = null) {
    const filterAddition = this.conditionList
      .filter((item) => {
        if (item.conditionType === 'filed') {
        // 如果是有exists操作符则不判断是否有值 直接回填路由
          if (this.isExistsOperator(item.operator)) return true;
          return !!item.value.filter(Boolean).length;
        }
        return false;
      });
    if (!filterAddition.length && !linkAddition) return undefined;
    const stringifyList = filterAddition.map(item => ({
      field: item.id,
      operator: item.operator,
      value: item.value.join(','),
      isInclude: item.isInclude,
    }));
    if (linkAddition && JSON.stringify(linkAddition) !== '{}') {
      stringifyList.push(linkAddition);
    }
    return JSON.stringify(stringifyList);
  }

  getIPChooserStr(ipChooser) {
    if (typeof ipChooser === 'object') return JSON.stringify(ipChooser);
    return ipChooser;
  }

  // 初始化或从外部下钻添加过来的交互下钻过来的条件
  pushCondition(field: string, operator: string, value: any, isInclude: boolean) {
    const findField = this.filterFields.find(item => item.id === field);
    const operatorItem = findField?.operatorList.find(item => (
      item.operator === operator || item?.wildcard_operator === operator
    )) ?? {}; // 找不到则是ip选择器
    // 空字符串切割会时会生成一个带有空字符串的数组 空字符串应该使用空数组
    const inputValueList = value !== '' ? value.toString().split(',') : [];
    // 检查条件列表中是否存在具有相同操作符和字段ID的条件
    const isExistCondition = this.conditionList.some(item => item.operator === operator && item.id === field);
    // 获取条件列表中的最后一个条件
    const lastCondition = this.conditionList[this.conditionList.length - 1];
    // 检查操作符是否是包含或不包含匹配短语
    const isContains = ['contains match phrase', 'not contains match phrase'].includes(operator);
    // 遍历条件列表
    for (const cIndex in this.conditionList) {
      // 获取当前遍历到的条件
      const currentCondition = this.conditionList[cIndex];
      // 如果当前条件的操作符和字段与给定的匹配
      if (currentCondition.operator === operator && currentCondition.id === field) {
        // 如果当前条件的值为空数组
        if (!currentCondition.value.length) {
          // 则将输入值数组直接设置为当前条件的值
          currentCondition.value = inputValueList;
          return;
        }
        // 如果存在具有相同操作符和字段的条件，并且操作符是包含类型
        if (isExistCondition && isContains) {
          // 如果最后一个条件的字段与给定的匹配
          if (lastCondition.id === field) {
            // 则将输入值数组添加到最后一个条件的值中
            lastCondition.value = [...lastCondition.value, ...inputValueList];
            return;
          }
          if (!lastCondition.value.length) {
            // 如果最后一个条件的值为空数组，则将输入值数组添加到当前条件的值中
            currentCondition.value = [...currentCondition.value, ...inputValueList];
            return;
          };
        };
      }
    }
    this.conditionList.push({
      ...findField,
      id: field,
      operator,
      isInclude: isInclude ?? true,
      value: inputValueList,
      operatorItem,
    });
  }

  // 只清除条件的值 不删除条件
  clearValue() {
    this.conditionList.forEach((item) => {
      item.value = [];
    });
    this.setRouteParams({}, true);
  }

  clearAllCondition() {
    this.conditionList = [];
    this.setRouteParams({}, true);
  }

  initAdditionDefault(addition = []) {
    // 如果初始化时没有路由传过来的条件则默认展示path和log条件
    if (!addition.length && !this.conditionList.length) {
      // log / path 操作默认展示
      addition = this.filterFields
        .filter(item => ['path', 'log'].includes(item.name))
        .map(item => ({
          field: item.name,
          operator: item.operator,
          value: '',
          isInclude: true,
        }));
    }
    addition.forEach((el) => {
      const { field, operator, value, isInclude } = el;
      this.pushCondition(field, operator, value, isInclude);
    });
  }

  /**
   * @desc: 删除条件
   * @param {Number} index 删除的下标
   * @param {String} conditionType 删除的条件交互类型
   */
  handleConditionDelete(index: number, conditionType: string) {
    const condition = deepClone(this.conditionList[index]);
    this.conditionList.splice(index, 1);
    if (conditionType === 'ip-select') {
      this.handleIPSelectorValueChange({}, true);
    } else if (condition.isInclude) {
      const isQuery = this.isExistsOperator(condition.operate) || condition.value.length;
      this.searchAdditionQuery(isQuery); // 删除的条件有值并且开启检索或者是操作符包含exists 则搜索一次
    };
    this.setRouteParams({}, conditionType === 'ip-select');
  }

  // 条件的字段更变
  handleFiledChange(index: number, id: string) {
    if (this.conditionList[index].conditionType === 'ip-select') {
      this.handleIPSelectorValueChange({}, true); // 当前旧的条件是ip选择器则清空IP
    }
    const spliceItem = this.filterFields.find(item => item.id === id);
    Object.entries(spliceItem).forEach(([key, val]) => { // 替换新的字段
      this.conditionList[index][key] = val;
    });
    this.searchAdditionQuery(false); // 更新检索条件但不检索
    this.setRouteParams();
  }

  // 更改是否参与检索
  handleIsIncludeChange(index:number, v:boolean) {
    const condition = this.conditionList[index];
    condition.isInclude = v;
    if (condition.conditionType === 'ip-select') {
      this.handleIPSelectorValueChange(!v ? {} : this.catchIpChooser);
    } else if (this.isExistsOperator(condition.operator) || condition.value.length) { // 如果是有包含和非包含直接请求
      this.searchAdditionQuery();
    };
    this.setRouteParams();
  }

  handleAdditionValueChange(index, additionVal) {
    const { newReplaceObj, isQuery } = additionVal;
    Object.assign(this.conditionList[index], newReplaceObj); // 更新操作符和数据
    if (this.conditionList[index].isInclude && !this.tagFocusInputObj?.str) {
      this.searchAdditionQuery(isQuery); // 操作需要请求且条件为打开时请求
    }
    this.setRouteParams();
  }

  async handleBlurSearchInput(keyword) {
    keyword === '' && (keyword = '*');
    try {
      const res = await $http.request('favorite/getSearchFields', {
        data: { keyword },
      });
      this.inputSearchList = res.data.map(item => item.name);
    } catch (err) {
      this.inputSearchList = [];
    }
  }

  @Debounce(300)
  searchAdditionQuery(isQuery = true, isForceQuery = false) { // 获得当前开启的字段并且有有效值进行检索
    const addition = this.conditionList
      .filter((item) => {
        if (item.conditionType !== 'filed' || !item.isInclude) return false;
        if (this.isExistsOperator(item.operator)) return true;
        if (item.value.length) return true;
      })
      .map(item => ({
        field: item.id,
        operator: item.operator,
        value: item.value.join(','),
      }));
    this.handleSearchAddChange(addition, isQuery, isForceQuery);
  }

  isExistsOperator(operator: string) { // 是否是包含和不包含
    return ['exists', 'does not exists'].includes(operator);
  }

  async queryValueList(fields = []) {
    if (!fields.length) return;
    const tempList = handleTransformToTimestamp(this.datePickerValue);
    try {
      const res = await $http.request('retrieve/getAggsTerms', {
        params: {
          index_set_id: this.indexId,
        },
        data: {
          keyword: !!this.retrievedKeyword ? this.retrievedKeyword : '*',
          fields,
          start_time: formatDate(tempList[0] * 1000),
          end_time: formatDate(tempList[1] * 1000),
        },
      });
      this.aggsItems = res.data.aggs_items;
      this.initValueList();
    } catch (err) {
      this.conditionList.forEach(item => item.valueList = []);
    }
  }

  initValueList() {
    this.conditionList.forEach((item) => {
      if (item.conditionType === 'ip-select') return;
      item.valueList = this.aggsItems[item.id] ?? [];
    });
  }

  tagInputStrChange(index: number, str: string) {
    this.tagFocusInputObj = str ? { index, str } : {};
  }

  handleClickRequestBtn() {
    const { index, str } = this.tagFocusInputObj;
    if (str) {
      const oldConditionList = this.conditionList[index].value;
      const setArr = new Set([...oldConditionList, str]);
      Object.assign(this.conditionList[index].value, [...setArr].filter(Boolean));
    };
    this.isClearCatchInputStr = !this.isClearCatchInputStr;
    this.searchAdditionQuery(true, true);
  }

  blurUpdateKeyword(val) {
    const { params, query: routerQuery } = this.$route;
    const routeData = {
      name: 'retrieve',
      params,
      query: { ...routerQuery, keyword: val },
    };
    this.$router.replace(routeData);
  }

  render() {
    return (
      <div>
        <QueryStatement
          history-records={this.historyRecords}
          is-show-ui-type={this.isShowUiType}
          is-sql-search-type={this.isSqlSearchType}
          is-can-use-ui-type={this.isCanUseUiType}
          onUpdateSearchParam={this.handleUpdateSearchParam}
          onRetrieve={this.handleRetrieveLog}
          onClickSearchType={this.handleClickSearchType} />
        {
          this.isSqlSearchType
            ? <RetrieveDetailInput
                v-model={this.retrieveParams.keyword}
                is-auto-query={this.isAutoQuery}
                retrieved-keyword={this.retrievedKeyword}
                dropdown-data={this.retrieveDropdownData}
                is-show-ui-type={this.isShowUiType}
                onKeywordBlurUpdate={this.blurUpdateKeyword}
                onInputBlur={this.handleBlurSearchInput}
                onIsCanSearch={val => this.handleUserOperate('isCanStorageFavorite', val)}
                onRetrieve={this.handleRetrieveLog}
              />
            : <UiQuery
                ref="uiQuery"
                is-favorite-search={this.isFavoriteSearch}
                keyword={this.retrieveParams.keyword}
                active-favorite={this.activeFavorite}
                onUpdateKeyWords={this.handleUpdateKeyWords}
                onIsCanSearch={val => this.handleUserOperate('isCanStorageFavorite', val)}
              />
        }
        {/* 这里插入 condition 组件 */}
        {
          this.conditionList.map((item, index) => <Condition
            name={item.name}
            filed={item.id}
            isInclude={item.isInclude}
            operatorValue={item.operator}
            inputValue={item.value}
            operatorList={item.operatorList}
            operatorItem={item.operatorItem}
            conditionType={item.conditionType}
            fieldType={item.fieldType}
            valueList={item.valueList}
            filterFields={this.filterFields}
            is-auto-query={this.isAutoQuery}
            retrieveParams={this.retrieveParams}
            catchIpChooser={this.catchIpChooser}
            isClearCatchInputStr={this.isClearCatchInputStr}
            // statisticalFieldsData={this.statisticalFieldsData}
            onIsIncludeChange={v => this.handleIsIncludeChange(index, v)}
            onDelete={v => this.handleConditionDelete(index, v)}
            onAdditionValueChange={additionVal => this.handleAdditionValueChange(index, additionVal)}
            onFiledChange={v => this.handleFiledChange(index, v)}
            onIpChange={() => this.handleOpenIpQuick()}
            onInputChange={v => this.tagInputStrChange(index, v)}
            style='margin-bottom: 16px;'
          />)
        }
        <div class={{ 'inquire-cascader-container': true, active: this.isShowFilterOption }}>
          <Button class='add-condition' theme="primary">
            <i class='bk-icon icon-plus' style='margin-right: 6px;'></i>
            <span>{this.$t('添加条件')}</span>
          </Button>

          <Select
            class='inquire-cascader'
            // multiple
            searchable
            v-model={this.filedSelectedValue}
            onToggle={this.handleToggleChange}
            onSelected={this.handleSelectFiled}
          >
            {
              this.filterFields.map(option => (
                <Option
                  v-bk-tooltips={{
                    content: option.disabledContent,
                    placement: 'right',
                    disabled: !option.disabled,
                  }}
                  key={option.id}
                  id={option.id}
                  name={option.fullName}
                  disabled={option.disabled}>
                </Option>
              ))
            }
          </Select>
        </div>
        <HandleBtn
          indexId={this.indexId}
          conditionList={this.conditionList}
          tableLoading={this.tableLoading}
          isAutoQuery={this.isAutoQuery}
          isSearchAllowed={this.isSearchAllowed}
          activeFavoriteID={this.activeFavoriteID}
          isCanStorageFavorite={this.isCanStorageFavorite}
          catchIpChooser={this.catchIpChooser}
          retrieveParams={this.retrieveParams}
          activeFavorite={this.activeFavorite}
          visibleFields={this.visibleFields}
          indexSetList={this.indexSetList}
          isSqlSearchType={this.isSqlSearchType}
          onRetrieveLog={this.handleClickRequestBtn}
          onClearCondition={this.handleClearCondition}/>
      </div>
    );
  }
}
