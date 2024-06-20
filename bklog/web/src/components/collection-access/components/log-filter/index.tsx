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
import {
  btnType,
  ISelectItem,
  ITableRowItem,
  operatorSelectList,
  btnGroupList,
  operatorMapping,
  tableRowBaseObj
} from './type';
import $http from '../../../../api';
import { deepClone, Debounce } from '../../../../common/util';
import { Form } from 'bk-magic-vue';
import ValidatorInput from './validator-input';

const inputLogStyle = {
  backgroundColor: '#313238',
  height: '82px',
  lineHeight: '24px',
  color: '#C4C6CC',
  borderRadius: '2px'
};

@Component
export default class LogFilter extends tsc<{}> {
  @Prop({ type: Object, required: true }) conditions: object;
  @Prop({ type: Boolean, default: false }) isCloneOrUpdate: boolean;

  /** 日志过滤开关 */
  filterSwitcher = false;
  isFirstClickFilterType = true;
  /** 当前过滤的日志类型 字符串或分隔符  */
  activeType: btnType = 'match';
  separator = '|';
  filterData: Array<Array<ITableRowItem>> = [
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
  originalFilterItemSelect: Array<ISelectItem> = [];
  /** 分隔符原始日志 */
  logOriginal = '';
  logOriginalLoading = false;

  get globalDataDelimiter() {
    return this.$store.getters['globals/globalsData']?.data_delimiter || [];
  }
  get curCollect() {
    return this.$store.getters['collect/curCollect'] || {};
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
  @Watch('shouldWatchValue', { immediate: true, deep: true })
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
        this.isCloneOrUpdate && this.getLogOriginal();
        break;
      default:
        break;
    }
  }
  /** 设置过滤分组 */
  splitFilters(filters: Array<ITableRowItem>) {
    const groups = [];
    let currentGroup: Array<ITableRowItem> = [];

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
    if (currentGroup.length > 0) {
      groups.push(currentGroup);
    }

    return groups;
  }
  /** 删除分组 */
  handleClickDeleteGroup(index: number) {
    if (this.filterData.length === 1) return;
    this.filterData.splice(index, 1);
  }
  /** 新增分组 */
  handleClickNewGroupBtn() {
    if (this.filterData.length >= 10) return;
    this.filterData.push([{ ...tableRowBaseObj, tableIndex: this.filterData.length }]);
  }
  /** 组内新增 */
  handleAddNewSeparator(rowIndex: number, tableIndex: number, operateType = 'add') {
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
    if (this.isCloneOrUpdate && this.isFirstClickFilterType && type === 'separator') {
      this.isFirstClickFilterType = false;
      this.getLogOriginal(false);
    }
  }
  /** 输入框内数据Form验证 */
  async inputValidate() {
    return new Promise(async (resolve, reject) => {
      if (!this.filterSwitcher) {
        resolve(true);
        return;
      }
      let isCanSubmit = true;

      for (const fIndex in this.filterData) {
        for (const iIndex in this.filterData[fIndex]) {
          let matchNotError = true;
          // 字符串类型过滤暂时无过滤参数（全文）
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
        const newData = (fItem as any).map((item: ITableRowItem, index: number) => {
          const { tableIndex, ...reset } = item;
          // 将数组中第一组的内容为and，后面的分组第一个logic_op参数为or来区分组与组
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
  /** 获取分隔符调试的原始日志 */
  getLogOriginal(isDebug = true) {
    $http
      .request(
        'source/dataList',
        {
          params: {
            collector_config_id: this.curCollect.collector_config_id
          }
        },
        {
          catchIsShowMessage: false
        }
      )
      .then(res => {
        if (res.data && res.data.length) {
          const firstData = res.data[0];
          this.logOriginal = firstData.etl.data || '';
          if (this.logOriginal && isDebug) this.logOriginDebug();
        }
      })
      .catch(() => {});
  }

  /** 获取分隔符调试后的下拉框 */
  async logOriginDebug() {
    try {
      this.logOriginalLoading = true;
      const res = await $http.request('clean/getEtlPreview', {
        data: {
          etl_config: 'bk_log_delimiter',
          etl_params: { separator: this.separator },
          data: this.logOriginal
        }
      });
      this.originalFilterItemSelect = res.data.fields.map(item => ({
        name: `${this.$t('第{n}行', { n: item.field_index })} | ${item.value}`,
        id: String(item.field_index),
        value: item.value
      }));
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
          v-model={row.fieldindex}
          active-type={this.activeType}
          row-data={row}
          table-index={row.tableIndex}
          original-filter-item-select={this.originalFilterItemSelect}
          placeholder={this.$t('请输入行数')}
        />
      )
    };
    const valueInputSlot = {
      default: ({ $index, row }) => (
        <ValidatorInput
          ref={`value-${row.tableIndex}-${$index}`}
          v-model={row.word}
          active-type={this.activeType}
          row-data={row}
        />
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
              />
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
          />
          <i
            class={['bk-icon icon-minus-circle-shape', { disabled: $index === 0 }]}
            onClick={() => this.handleAddNewSeparator($index, row.tableIndex, 'delete')}
          />
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
            <i class='bk-icon icon-info-circle' />
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
                      />
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
                  />
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
                    />
                  )}
                  <bk-table-column
                    label={this.$t('操作符')}
                    prop='op'
                    scopedSlots={selectSlot}
                  />
                  <bk-table-column
                    label='Value'
                    prop='word'
                    scopedSlots={valueInputSlot}
                  />
                  <bk-table-column
                    label={this.$t('操作')}
                    width='95'
                    scopedSlots={operatorSlot}
                  />
                </bk-table>
              </div>
            ))}
            <div
              class='add-new-group-btn'
              onClick={() => this.handleClickNewGroupBtn()}
            >
              <i class='bk-icon icon-plus-line' />
              <span>{this.$t('新增过滤组')}</span>
            </div>
          </div>
        )}
      </div>
    );
  }
}
