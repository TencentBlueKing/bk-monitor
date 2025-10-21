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

import { Component, Prop, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { BK_LOG_STORAGE } from '../../../store/store.type';
import AggChart from './agg-chart';
import FieldAnalysis from './field-analysis';

import './field-item.scss';

@Component
export default class FieldItem extends tsc<object> {
  @Prop({ type: String, default: 'visible', validator: v => ['visible', 'hidden'].includes(v as string) }) type: string;
  @Prop({ type: Object, default: () => ({}) }) fieldItem: any;
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias: boolean;
  @Prop({ type: Array, default: () => [] }) datePickerValue: any[];
  @Prop({ type: Number, default: 0 }) retrieveSearchNumber: number;
  @Prop({ type: Object, required: true }) retrieveParams: object;
  @Prop({ type: Array, default: () => [] }) visibleFields: any[];
  @Prop({ type: Object, default: () => ({}) }) statisticalFieldData: object;
  @Prop({ type: Boolean, required: true }) isFrontStatistics: boolean;

  isExpand = false;
  analysisActive = false;
  operationInstance = null;
  fieldAnalysisInstance = null;

  get fieldTypeMap() {
    return this.$store.state.globals.fieldTypeMap;
  }
  get unionIndexList() {
    return this.$store.getters.unionIndexList;
  }
  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }
  get unionIndexItemList() {
    return this.$store.getters.unionIndexItemList;
  }
  get gatherFieldsCount() {
    if (this.isFrontStatistics) {
      return Object.keys(this.statisticalFieldData).length;
    }
    return 0;
  }
  // 显示融合字段统计比例图表
  get showFieldsChart() {
    if (this.fieldItem.field_type === 'text') {
      return false;
    }
    return this.isFrontStatistics ? !!this.gatherFieldsCount : this.isShowFieldsAnalysis;
  }
  get isShowFieldsCount() {
    return !['object', 'nested', 'text'].includes(this.fieldItem.field_type) && this.isFrontStatistics;
  }
  get isShowFieldsAnalysis() {
    return (
      ['keyword', 'integer', 'long', 'double', 'bool', 'conflict'].includes(this.fieldItem.field_type) &&
      this.fieldItem.es_doc_values &&
      !/^__dist_/.test(this.fieldItem.field_name)
    );
  }
  get reQueryAggChart() {
    return `${this.retrieveSearchNumber} ${this.datePickerValue.join(',')}`;
  }
  /** 冲突字段索引集名称*/
  get unionConflictFieldsName() {
    return this.unionIndexItemList
      .filter(item => this.unionIndexList.includes(item.index_set_id))
      .map(item => item.indexName);
  }
  beforeDestroy() {
    this.instanceDestroy();
  }

  @Emit('toggleItem')
  emitToggleItem(v) {
    return v;
  }

  getFieldIcon(fieldType: string) {
    return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'bklog-icon bklog-unkown';
  }
  // 点击字段行，展开显示聚合信息
  handleClickItem() {
    if (this.showFieldsChart) {
      this.isExpand = !this.isExpand;
    }
  }
  // 显示或隐藏字段
  handleShowOrHiddenItem() {
    this.instanceDestroy();
    this.emitToggleItem({
      type: this.type,
      fieldItem: this.fieldItem,
    });
  }
  handleClickAnalysisItem() {
    this.instanceDestroy();
    this.analysisActive = true;
    this.fieldAnalysisInstance = new FieldAnalysis().$mount();
    const indexSetIDs = this.isUnionSearch ? this.unionIndexList : [this.$route.params.indexId];
    this.fieldAnalysisInstance.$props.queryParams = {
      ...this.retrieveParams,
      index_set_ids: indexSetIDs,
      field_type: this.fieldItem.field_type,
      agg_field: this.fieldItem.field_name,
    };
    /** 当小窗位置过于靠近底部时会显示不全chart图表，需要等接口更新完后更新Popper位置 */
    this.fieldAnalysisInstance?.$on('statisticsInfoFinish', this.updatePopperInstance);
    this.operationInstance = this.$bkPopover(this.$refs.operationRef, {
      content: this.fieldAnalysisInstance.$el,
      arrow: true,
      placement: 'right-start',
      boundary: 'viewport',
      trigger: 'click',
      theme: 'light',
      interactive: true,
      appendTo: document.body,
      onHidden: () => {
        this.instanceDestroy();
      },
    });
    this.operationInstance.show(100);
  }
  /** 更新Popper位置 */
  updatePopperInstance() {
    setTimeout(() => {
      this.operationInstance.popperInstance.update();
    }, 100);
  }
  instanceDestroy() {
    this.fieldAnalysisInstance?.$off('statisticsInfoFinish', this.updatePopperInstance);
    this.operationInstance?.destroy();
    this.fieldAnalysisInstance?.$destroy();
    this.operationInstance = null;
    this.fieldAnalysisInstance = null;
    this.analysisActive = false;
  }
  /** 联合查询并且有冲突字段 */
  isUnionConflictFields(fieldType: string) {
    return this.isUnionSearch && fieldType === 'conflict';
  }

  render() {
    return (
      <li class='filed-item-old'>
        <div
          class={{ 'filed-title': true, expanded: this.isExpand }}
          onClick={() => this.handleClickItem()}
        >
          <span class={['icon bklog-icon bklog-drag-dots', { 'hidden-icon': this.type === 'hidden' }]} />
          {/* 三角符号 */}
          <span class={{ 'icon-right-shape': this.showFieldsChart, 'bk-icon': true }} />
          {/* 字段类型对应的图标 */}
          <span
            class={[this.getFieldIcon(this.fieldItem.field_type) || 'bklog-icon bklog-unkown', 'field-type-icon']}
            v-bk-tooltips={{
              content: this.fieldTypeMap[this.fieldItem.field_type]?.name,
              disabled: !this.fieldTypeMap[this.fieldItem.field_type],
            }}
          />
          {/* 字段名 */}
          <span class='overflow-tips field-name'>
            <span v-bk-overflow-tips>
              {this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]
                ? this.fieldAliasMap[this.fieldItem.field_name]
                : this.fieldItem.field_name}
            </span>
            <span
              class='field-count'
              v-show={this.isShowFieldsCount}
            >
              ({this.gatherFieldsCount})
            </span>
            {this.isUnionConflictFields(this.fieldItem.field_type) && (
              <bk-popover
                ext-cls='conflict-popover'
                theme='light'
              >
                <i class='conflict-icon bk-icon icon-exclamation-triangle-shape' />
                <div slot='content'>
                  <p>{this.$t('该字段在以下索引集存在冲突')}</p>
                  {this.unionConflictFieldsName.map(item => (
                    <bk-tag key={item}>{item}</bk-tag>
                  ))}
                </div>
              </bk-popover>
            )}
          </span>
          <div
            ref='operationRef'
            class={['operation-text', { 'analysis-active': this.analysisActive }]}
          >
            {this.isShowFieldsAnalysis && (
              <div
                class={{
                  'operation-icon-box': true,
                  'analysis-disabled': !(this.isUnionSearch || this.isFrontStatistics),
                }}
                v-bk-tooltips={{
                  content: this.isUnionSearch || this.isFrontStatistics ? this.$t('暂不支持') : this.$t('图表分析'),
                }}
                onClick={e => {
                  e.stopPropagation();
                  // 联合查询 或 非白名单业务和索引集类型 时不能点击字段分析
                  if (this.isUnionSearch || this.isFrontStatistics) {
                    return;
                  }
                  this.handleClickAnalysisItem();
                }}
              >
                <i class='bklog-icon bklog-log-trend' />
              </div>
            )}
            {/* 设置字段显示或隐藏 */}
            <div
              class='operation-icon-box'
              v-bk-tooltips={{
                content: this.type === 'visible' ? this.$t('点击隐藏') : this.$t('点击显示'),
              }}
              onClick={e => {
                e.stopPropagation();
                this.handleShowOrHiddenItem();
              }}
            >
              <i class={['bk-icon include-icon', `${this.type !== 'visible' ? 'icon-eye' : 'icon-eye-slash'}`]} />
            </div>
          </div>
        </div>
        {/* 显示聚合字段图表信息 */}
        {!!this.showFieldsChart && this.isExpand && (
          <AggChart
            field-name={this.fieldItem.field_name}
            field-type={this.fieldItem.field_type}
            is-front-statistics={this.isFrontStatistics}
            parent-expand={this.isExpand}
            re-query-agg-chart={this.reQueryAggChart}
            retrieve-params={this.retrieveParams}
            statistical-field-data={this.statisticalFieldData}
          />
        )}
      </li>
    );
  }
}
