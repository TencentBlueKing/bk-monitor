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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, deepClone } from 'monitor-common/utils/utils';

import FieldList from './field-list';

import type { FieldFilteringType, FieldListType, FieldValue, IFilterCondition, IOption } from '../typings';

import './field-filtering.scss';

const { i18n } = window;
/**
 * @description: 事件检索的字段过滤操作组件
 */
@Component
export default class FieldFiltering extends tsc<FieldFilteringType.IProps, FieldFilteringType.IEvent> {
  @Prop({ default: () => [], type: Array }) value: FieldValue[];
  @Prop({ default: 0, type: Number }) total: number;
  @Ref('fieldTypePopover') fieldTypePopoverRef: any;
  /** 字段列表数据 */
  localValue: FieldValue[] = [];

  /** 自动搜索关键字 */
  searchKeyword = '';

  /** 字段类型筛选选中的值 */
  fieldTypeValue: FieldFilteringType.IFieldTypeValue = {
    aggVal: 'all',
    fieldType: 'all',
  };
  fieldTypevalueCache: FieldFilteringType.IFieldTypeValue = {
    aggVal: 'all',
    fieldType: 'all',
  };

  /** 字段可聚合配置 */
  fieldAggList: IOption[] = [
    { id: 'all', name: i18n.t('不限') },
    { id: 'yes', name: i18n.t('是') },
    { id: 'no', name: i18n.t('否') },
  ];
  /** 字段数据类型可选列表 */
  fieldTypeList: IOption[] = [
    { id: 'all', name: i18n.t('不限') },
    { id: 'number', name: i18n.t('数字') },
    { id: 'string', name: i18n.t('字符串') },
    { id: 'text', name: i18n.t('文本') },
    { id: 'date', name: i18n.t('时间') },
  ];

  /** 字段过滤选中的数量统计 */
  get fieldTypeCheckedCount() {
    return Object.keys(this.fieldTypeValue).reduce((count, key) => {
      this.fieldTypeValue[key] !== 'all' && (count += 1);
      return count;
    }, 0);
  }
  /** 已添加字段 */
  get isCheckedList() {
    return this.localValue.filter(item => this.keywordMatch(item));
  }
  // /** 可选字段 */
  // get noCheckedList() {
  //   return this.localValue.filter(item => !item.checked && this.keywordMatch(item))
  // }

  @Watch('value', { immediate: true })
  valueChange(val: FieldValue[]) {
    this.localValue = deepClone(val);
  }

  mounted() {
    this.$root.$el.addEventListener('click', this.handleCloseFieldType);
  }

  beforeDestroy() {
    this.$root.$el.removeEventListener('click', this.handleCloseFieldType);
  }

  /**
   * @description: 搜索是否匹配的字段
   * @param {FieldValue} item
   * @return {boolean}
   */
  keywordMatch(item: FieldValue) {
    const target = item.fieldName.toLocaleLowerCase();
    return target.includes(this.searchKeyword.trim().toLocaleLowerCase());
  }

  /**
   * @description: 更新类型筛选的缓存
   */
  fieldTypePopShow() {
    this.fieldTypevalueCache = deepClone(this.fieldTypeValue);
  }
  /**
   * @description: 更新类型筛选的值
   */
  handleConfirmFieldType() {
    this.fieldTypeValue = deepClone(this.fieldTypevalueCache);
    this.handleCloseFieldType();
  }

  /** 关闭类型筛选的弹层 */
  handleCloseFieldType() {
    this.fieldTypePopoverRef?.instance?.hide?.();
  }

  /**
   * @description: 更新搜索关键字
   * @param {string} val
   */
  @Debounce(300)
  handleSearchChange(val: string) {
    this.searchKeyword = val;
  }

  /**
   * @description: 添加过滤条件
   * @param {IFilterCondition} val
   * @return {*}
   */
  @Emit('addCondition')
  handleAddCondition(val: IFilterCondition.localValue) {
    return val;
  }

  @Emit('change')
  handleValueChnage(obj: FieldListType.IEvent['onCheckedChange']) {
    const target = this.localValue.find(item => item.field === obj.field);
    target.checked = obj.checked;
    return deepClone(this.localValue);
  }

  render() {
    return (
      <div class='field-filtering-wrapper'>
        <div class='field-filtering-title'>{this.$t('维度过滤')}</div>
        <div class='field-search-row'>
          <bk-input
            right-icon='bk-icon icon-search'
            value={this.searchKeyword}
            onChange={this.handleSearchChange}
          />
          {/* <span class="line"></span> */}
          {/* <bk-popover
            class="field-type-popover"
            theme="light"
            trigger="click"
            boundary="window"
            ref="fieldTypePopover"
            tippy-options={{ hideOnClick: false }}
            on-show={this.fieldTypePopShow}>
            <span class="field-type-wrap">
              <i class="icon-monitor icon-filter-fill"></i>
              <span class="text">{this.$t('字段类型过滤')}</span>
              { !!this.fieldTypeCheckedCount && <span class="count">{this.fieldTypeCheckedCount}</span>}
            </span>
            <div slot="content" class="field-filtering-type-content">
              <div class="field-type-label">{this.$t('可聚合')}</div>
              <bk-radio-group vModel={this.fieldTypevalueCache.aggVal} class="agg-radio-group">
                {
                  this.fieldAggList.map(opt => <bk-radio value={opt.id}>{opt.name}</bk-radio>)
                }
              </bk-radio-group>
              <div class="field-type-label">{this.$t('字段类型')}</div>
              <bk-select clearable={false} vModel={this.fieldTypevalueCache.fieldType}>
                {
                  this.fieldTypeList.map(item => (
                    <bk-option
                      id={item.id}
                      name={item.name} />
                  ))
                }
              </bk-select>
              <div class="field-type-btn-group">
                <bk-button text={true} onClick={this.handleConfirmFieldType}>{this.$t('确认')}</bk-button>
                <bk-button text={true} onClick={this.handleCloseFieldType}>{this.$t('取消')}</bk-button>
              </div>
            </div>
          </bk-popover> */}
        </div>
        <div class='field-list-wrap'>
          {this.isCheckedList.length ? (
            <FieldList
              total={this.total}
              value={this.isCheckedList}
              onAddCondition={this.handleAddCondition}
              onCheckedChange={this.handleValueChnage}
            />
          ) : (
            <bk-exception
              scene='part'
              type='empty'
            />
          )}
        </div>
      </div>
    );
  }
}
