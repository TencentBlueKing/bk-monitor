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
import { Component, Prop, Emit, Watch } from 'vue-property-decorator';
import './index.scss';
// import $http from '../../../../api';
import { deepClone, Debounce } from '@/common/util';
import { Form } from 'bk-magic-vue';
import ValidatorInput from './validator-input';

/** 操作符列表 */
const operatorSelectList = [
  {
    id: 'eq',
    name: window.mainComponent.$t('等于')
  },
  {
    id: 'neq',
    name: window.mainComponent.$t('不等于')
  },
  {
    id: 'include',
    name: window.mainComponent.$t('包含')
  },
  {
    id: 'exclude',
    name: window.mainComponent.$t('不包含')
  },
  {
    id: 'regex',
    name: window.mainComponent.$t('正则匹配')
  },
  {
    id: 'nregex',
    name: window.mainComponent.$t('正则不匹配')
  }
];
/** 过滤类型 */
const btnGroupList = [
  {
    id: 'match',
    name: window.mainComponent.$t('字符串')
  },
  {
    id: 'separator',
    name: window.mainComponent.$t('分隔符')
  }
];
/** 操作符映射 */
const operatorMapping = {
  '=': 'eq',
  '!=': 'neq'
};

const tableRowBaseObj = {
  fieldindex: '',
  word: '',
  op: 'eq',
  tableIndex: 0
};

const inputLogStyle = {
  backgroundColor: '#313238',
  height: '82px',
  lineHeight: '24px',
  color: '#C4C6CC',
  borderRadius: '2px'
};

type btnType = 'none' | 'match' | 'separator';

@Component
export default class LogFilter extends tsc<{}> {
  @Prop({ type: Object, required: true }) conditions: object;
  /** 日志过滤开关 */
  filterSwitcher = false;
  /** 当前过滤的日志类型 字符串或分隔符  */
  activeType: btnType = 'match';
  separator = '|';
  filterData = [
    [
      {
        fieldindex: '',
        word: '',
        op: 'eq',
        tableIndex: 0
      }
    ]
  ];
  /** 切换数据类型缓存的过滤数据 */
  catchFilterData = {
    match: deepClone(this.filterData),
    separator: deepClone(this.filterData)
  };
  originalFilterItemSelect = [];
  /** 分隔符日志 */
  logOriginal = '';
  logOriginalLoading = false;

  get globalDataDelimiter() {
    return this.$store.getters['globals/globalsData']?.data_delimiter || [];
  }
  /** 是否是字符串类型 */
  get isMatchType() {
    return this.activeType === 'match';
  }

  get shouldWatchValue() {
    return {
      filterData: this.filterData,
      switcher: this.filterSwitcher,
      separator: this.separator
    };
  }

  @Debounce(100)
  @Watch('shouldWatchValue', { deep: true })
  watchShouldWatchValue() {
    this.conditionsChange();
  }

  @Emit('update:conditions-change')
  conditionsChange() {
    return this.getSubmitConditionsData();
  }

  mounted() {
    this.initContainerData();
  }
  /** 初始化日志过滤table表格 */
  initContainerData() {
    const {
      type,
      separator,
      separator_filters: separatorFilters,
      match_content: matchContent,
      match_type: matchType
    } = this.conditions as any;
    switch (type) {
      case 'none':
        this.filterSwitcher = false;
        break;
      case 'match':
        this.filterSwitcher = true;
        this.activeType = type;
        /** 旧数据当成一个新table来处理 */
        if (!separatorFilters.length) {
          this.filterData = [
            [
              {
                fieldindex: '-1',
                word: matchContent,
                op: matchType,
                tableIndex: 0
              }
            ]
          ];
        } else {
          this.filterData = this.splitFilters(separatorFilters);
        }
        break;
      case 'separator':
        this.filterSwitcher = true;
        this.activeType = type;
        this.separator = separator || '|';
        this.filterData = this.splitFilters(separatorFilters);
        break;
      default:
        break;
    }
  }
  /** 设置过滤分组 */
  splitFilters(filters) {
    const groups = [];
    let currentGroup = [];

    filters.forEach((filter, index) => {
      const mappingFilter = {
        ...filter,
        op: operatorMapping[filter.op] ?? filter.op, // 映射操作符
        tableIndex: groups.length // 表格下标
      };
      currentGroup.push(mappingFilter);
      // 检查下一个 filter
      if (mappingFilter.logic_op === 'or' || index === filters.length - 1) {
        groups.push(currentGroup);
        currentGroup = [];
      }
    });
    // 如果最后一个 group 没有被 push
    if (currentGroup.length > 0) {
      groups.push(currentGroup);
    }

    return groups;
  }
  /** 删除分组 */
  async handleClickDeleteGroup(index) {
    if (this.filterData.length === 1) return;
    this.filterData.splice(index, 1);
  }
  /** 新增分组 */
  handleClickNewGroupBtn() {
    if (this.filterData.length >= 10) return;
    this.filterData.push([{ ...tableRowBaseObj, tableIndex: this.filterData.length }]);
  }
  /** 组内新增 */
  handleAddNewSeparator(rowIndex, tableIndex, operateType = 'add') {
    const currentGroup = this.filterData[tableIndex];
    if (operateType === 'add') {
      currentGroup.push({ ...tableRowBaseObj, tableIndex });
    } else {
      if (currentGroup.length === 1) return;
      currentGroup.splice(rowIndex, 1);
    }
  }
  /** 切换类型 */
  handleClickFilterType(type: btnType) {
    this.catchFilterData[this.activeType] = this.filterData;
    this.filterData = this.catchFilterData[type];
    this.activeType = type;
  }
  /** 输入框内数据Form验证 */
  async inputValidate() {
    return new Promise(async (resolve, reject) => {
      if (this.activeType === 'none') resolve(true);
      let isCanSubmit = true;

      for (const fIndex in this.filterData) {
        for (const iIndex in this.filterData[fIndex]) {
          let matchNotError = true;
          if (this.activeType === 'separator') {
            matchNotError = await (this.$refs[`match-${fIndex}-${iIndex}`] as Form)?.validate();
          }
          const valueNotError = await (this.$refs[`value-${fIndex}-${iIndex}`] as Form)?.validate();

          if (isCanSubmit) isCanSubmit = matchNotError && valueNotError;
        }
      }
      isCanSubmit ? resolve(true) : reject();
    });
  }

  /** 获取提交所需的conditions数据 */
  getSubmitConditionsData() {
    const filterData = this.filterData.map(fItem => fItem.filter(item => !!item.word));

    const submitData = filterData
      .filter(item => !!item.length)
      .map((fItem, fIndex) => {
        const newData = (fItem as any).map((item, index) => {
          const { tableIndex, ...reset } = item;
          return { ...reset, logic_op: fIndex === 0 || index !== 0 ? 'and' : 'or' };
        });
        return newData;
      });
    let submitFlatData = submitData.flat();
    if (this.isMatchType) {
      submitFlatData = submitFlatData.map(item => ({ ...item, fieldindex: '-1' }));
    }
    let conditions = {};
    if (!this.filterSwitcher || !submitFlatData.length) {
      conditions = { type: 'none' };
    } else {
      conditions = {
        separator: this.separator,
        separator_filters: submitFlatData,
        type: this.activeType
      };
    }
    return conditions;
  }
  /** 获取分隔符调试后的下拉框 */
  async logOriginDebug() {
    try {
      // this.logOriginalLoading = true;
      // const res = await $http.request('clean/getEtlPreview', {
      //   data: {
      //     etl_config: 'bk_log_delimiter',
      //     etl_params: { separator: this.separator },
      //     data: this.logOriginal
      //   }
      // });
      // const resDataFields = res.data.fields;
      // this.originalFilterItemSelect = resDataFields.map(item => ({
      //   name: `第${item.field_index}行 | ${item.value}`,
      //   id: String(item.field_index),
      //   value: item.value
      // }));
      // this.filterData = this.filterData.map(fItem => {
      //   return fItem.map((item, iIndex) => ({
      //     fieldindex: String(iIndex + 1),
      //     word: item.word,
      //     op: 'eq',
      //     tableIndex: 0
      //   }));
      // });
    } catch (error) {
    } finally {
      this.logOriginalLoading = false;
    }
  }

  render() {
    const fieldIndexInputSlot = {
      default: ({ $index, row }) => (
        <ValidatorInput
          ref={`match-${row.tableIndex}-${$index}`}
          input-type={'number'}
          ext-class='table-input'
          v-model={row.fieldindex}
          active-type={this.activeType}
          row-data={row}
          table-index={row.tableIndex}
          original-filter-item-select={this.originalFilterItemSelect}
          placeholder={this.$t('请输入行数')}
        ></ValidatorInput>
      )
    };
    const valueInputSlot = {
      default: ({ $index, row }) => (
        <ValidatorInput
          ref={`value-${row.tableIndex}-${$index}`}
          ext-class='table-input'
          v-model={row.word}
          active-type={this.activeType}
          row-data={row}
        ></ValidatorInput>
      )
    };
    const selectSlot = {
      default: ({ row }) => (
        <div class='table-select'>
          <bk-select
            v-model={row.op}
            clearable={false}
          >
            {operatorSelectList.map(option => (
              <bk-option
                id={option.id}
                name={option.name}
              ></bk-option>
            ))}
          </bk-select>
        </div>
      )
    };

    const operatorSlot = {
      default: ({ $index, row }) => (
        <div class='table-operator'>
          <i
            class='bk-icon icon-plus-circle-shape'
            onClick={() => this.handleAddNewSeparator($index, row.tableIndex, 'add')}
          ></i>
          <i
            class='bk-icon icon-minus-circle-shape'
            onClick={() => this.handleAddNewSeparator($index, row.tableIndex, 'delete')}
          ></i>
        </div>
      )
    };

    return (
      <div class='log-filter-container'>
        <div class='switcher-container'>
          <bk-switcher
            v-model={this.filterSwitcher}
            theme='primary'
            size='large'
          ></bk-switcher>
          <div class='switcher-tips'>
            <i class='bk-icon icon-info-circle'></i>
            <span>{this.$t('过滤器支持采集时过滤不符合的日志内容，需采集器版本 XXXXXXXX')}</span>
          </div>
        </div>
        {this.filterSwitcher && (
          <div class='filter-table-container'>
            <div class='bk-button-group'>
              {btnGroupList.map(item => (
                <bk-button
                  class={{ 'is-selected': this.activeType === item.id }}
                  size='small'
                  onClick={() => this.handleClickFilterType(item.id as btnType)}
                >
                  {item.name}
                </bk-button>
              ))}
            </div>
            {!this.isMatchType && (
              <div>
                <div class='separator-select'>
                  <bk-select
                    v-model={this.separator}
                    clearable={false}
                  >
                    {this.globalDataDelimiter.map(option => (
                      <bk-option
                        id={option.id}
                        name={option.name}
                      ></bk-option>
                    ))}
                  </bk-select>
                  <bk-button
                    theme='primary'
                    disabled={!this.logOriginal || !this.separator || this.logOriginalLoading}
                    onClick={() => this.logOriginDebug()}
                  >
                    {this.$t('调试')}
                  </bk-button>
                </div>
                <div class='input-style'>
                  <bk-input
                    v-model={this.logOriginal}
                    v-bkloading={{ isLoading: this.logOriginalLoading }}
                    placeholder={this.$t('请输入日志样例')}
                    type='textarea'
                    rows={3}
                    input-style={inputLogStyle}
                  ></bk-input>
                </div>
              </div>
            )}
            {this.filterData.map((item, index) => (
              <div class='filter-group-table-container'>
                <div class='group-table-head'>
                  <span>{this.$t('第{n}组', { n: index + 1 })}</span>
                  <i
                    class='bk-icon icon-close3-shape'
                    onClick={() => this.handleClickDeleteGroup(index)}
                  ></i>
                </div>
                <bk-table
                  data={item}
                  ref='filterTableRef'
                  dark-header
                  col-border
                >
                  {!this.isMatchType && (
                    <bk-table-column
                      label={this.$t('过滤参数')}
                      prop='fieldindex'
                      scopedSlots={fieldIndexInputSlot}
                    ></bk-table-column>
                  )}
                  <bk-table-column
                    label={this.$t('操作符')}
                    prop='op'
                    scopedSlots={selectSlot}
                  ></bk-table-column>
                  <bk-table-column
                    label='Value'
                    prop='word'
                    scopedSlots={valueInputSlot}
                  ></bk-table-column>
                  <bk-table-column
                    label={this.$t('操作')}
                    width='95'
                    scopedSlots={operatorSlot}
                  ></bk-table-column>
                </bk-table>
              </div>
            ))}
            <div
              class='add-new-group-btn'
              onClick={() => this.handleClickNewGroupBtn()}
            >
              <i class='bk-icon icon-plus-line'></i>
              <span>{this.$t('新增过滤组')}</span>
            </div>
          </div>
        )}
      </div>
    );
  }
}
