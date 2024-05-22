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
import { Component, Prop, Emit } from 'vue-property-decorator';
import './field-item.scss';
import AggChart from './agg-chart';
import FieldAnalysis from './field-analysis';

@Component
export default class FieldItem extends tsc<{}> {
  @Prop({ type: String, default: 'visible', validator: v => ['visible', 'hidden'].includes(v as string) }) type: string;
  @Prop({ type: Object, default: () => ({}) }) fieldItem: any;
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias: boolean;
  // @Prop({ type: Object, default: () => ({}) }) statisticalFieldData: object;
  @Prop({ type: Object, required: true }) retrieveParams: object;
  @Prop({ type: Array, default: () => [] }) visibleFields: Array<any>;

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
    // 聚合字段有多少个
    return this.fieldItem.field_count ?? 0;
  }
  // 显示融合字段统计比例图表
  get showFieldsChart() {
    return this.fieldItem.field_type !== 'text';
  }
  get isShowFieldsCount() {
    return !['object', 'nested', 'text'].includes(this.fieldItem.field_type);
  }
  get isShowFieldsAnalysis() {
    return ['keyword', 'integer', 'long', 'double', 'bool', 'conflict'].includes(this.fieldItem.field_type);
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
    return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'log-icon icon-unkown';
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
      fieldItem: this.fieldItem
    });
  }
  handleClickAnalysisItem() {
    this.analysisActive = true;
    this.fieldAnalysisInstance = new FieldAnalysis().$mount();
    const indexSetIDs = this.isUnionSearch ? this.unionIndexList : [this.$route.params.indexId];
    this.fieldAnalysisInstance.$props.fieldItem = this.fieldItem;
    this.fieldAnalysisInstance.$props.queryParams = {
      ...this.retrieveParams,
      index_set_ids: indexSetIDs,
      field_type: this.fieldItem.field_type,
      agg_field: this.fieldItem.field_name
    };
    this.operationInstance = this.$bkPopover(this.$refs.operationRef, {
      content: this.fieldAnalysisInstance.$el,
      arrow: true,
      placement: 'right-start',
      boundary: document.querySelector('body'),
      trigger: 'click',
      theme: 'light',
      interactive: true,
      appendTo: document.body,
      onHidden: () => {
        this.instanceDestroy();
      },
      onShow: () => {}
    });
    this.operationInstance.show(100);
  }
  instanceDestroy() {
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
      <li class='filed-item'>
        <div
          class={{ 'filed-title': true, expanded: this.isExpand }}
          onClick={() => this.handleClickItem()}
        >
          <span class={['icon log-icon icon-drag-dots', { 'hidden-icon': this.type === 'hidden' }]}></span>
          {/* 三角符号 */}
          <span class={{ 'icon-right-shape': this.showFieldsChart, 'bk-icon': true }}></span>
          {/* 字段类型对应的图标 */}
          <span
            v-bk-tooltips={{
              content:
                this.fieldTypeMap[this.fieldItem.field_type] && this.fieldTypeMap[this.fieldItem.field_type].name,
              disabled: !this.fieldTypeMap[this.fieldItem.field_type]
            }}
            class={[this.getFieldIcon(this.fieldItem.field_type) || 'log-icon icon-unkown', 'field-type-icon']}
          ></span>
          {/* 字段名 */}
          <span class='overflow-tips field-name'>
            <span v-bk-overflow-tips>
              {this.showFieldAlias ? this.fieldAliasMap[this.fieldItem.field_name] : this.fieldItem.field_name}
            </span>
            <span
              v-show={this.isShowFieldsCount}
              class='field-count'
            >
              ({this.gatherFieldsCount})
            </span>
            {this.isUnionConflictFields(this.fieldItem.field_type) && (
              <bk-popover
                theme='light'
                ext-cls='conflict-popover'
              >
                <i class='conflict-icon bk-icon icon-exclamation-triangle-shape'></i>
                <div slot='content'>
                  <p>{this.$t('该字段在以下索引集存在冲突')}</p>
                  {this.unionConflictFieldsName.map(item => (
                    <bk-tag>{item}</bk-tag>
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
              <span
                onClick={e => {
                  e.stopPropagation();
                  this.handleClickAnalysisItem();
                }}
              >
                {this.$t('字段分析')}
              </span>
            )}
            {/* 设置字段显示或隐藏 */}
            <span
              onClick={e => {
                e.stopPropagation();
                this.handleShowOrHiddenItem();
              }}
            >
              {this.type === 'visible' ? this.$t('隐藏') : this.$t('显示')}
            </span>
          </div>
        </div>
        {/* 显示聚合字段图表信息 */}
        {!!this.showFieldsChart && this.isExpand && (
          <AggChart
            retrieve-params={this.retrieveParams}
            parent-expand={this.isExpand}
            field-name={this.fieldItem.field_name}
            field-type={this.fieldItem.field_type}
          />
        )}
      </li>
    );
  }
}
