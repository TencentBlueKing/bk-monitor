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

import { Component, Prop, Emit, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { blobDownload } from '@/common/util';
import { debounce } from 'lodash-es';

import { BK_LOG_STORAGE } from '../../../store/store.type';
import AggChart from './agg-chart';
import FieldAnalysis from './field-analysis';
import { axiosInstance } from '@/api';

import './field-item.scss';
@Component
export default class FieldItem extends tsc<object> {
  @Prop({ type: String, default: 'visible', validator: v => ['visible', 'hidden'].includes(v as string) }) type: string;
  @Prop({ type: Object, default: () => ({}) }) fieldItem: any;
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias: boolean;
  @Prop({ type: Array, default: () => [] }) datePickerValue: any[];
  @Prop({ type: Number, default: 0 }) retrieveSearchNumber: number;
  @Prop({ type: Object, required: true }) retrieveParams: any;
  @Prop({ type: Array, default: () => [] }) visibleFields: any[];
  @Prop({ type: Object, default: () => ({}) }) statisticalFieldData: object;
  @Prop({ type: Boolean, required: true }) isFrontStatistics: boolean;
  @Prop({ type: Boolean, default: false }) isFieldObject: boolean;
  @Ref('fieldChart') fieldChartRef: any;
  isExpand = false;
  analysisActive = false;
  operationInstance = null;
  ifShowMore = false;
  fieldData = null;
  distinctCount = 0;
  btnLoading = false;
  expandIconShow = false;
  queryParams = {};

  fieldIconCache: Record<string, { icon: string; color: string; textColor: string }> = {};

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
  get indexSetList() {
    return this.$store.state.retrieve?.indexSetList ?? [];
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
    const validTypes = ['keyword', 'integer', 'long', 'double', 'bool', 'conflict'];
    return (
      validTypes.includes(this.fieldItem.field_type) &&
      this.fieldItem.es_doc_values &&
      !/^__dist_/.test(this.fieldItem.field_name)
    );
  }
  /** 冲突字段索引集名称*/
  get unionConflictFieldsName() {
    return this.unionIndexItemList
      .filter(item => this.unionIndexList.includes(item.index_set_id))
      .map(item => item.indexName);
  }

  get agg_field() {
    const fieldName = this.fieldItem.field_name;
    return this.retrieveParams.showFieldAlias ? (this.fieldAliasMap[fieldName] ?? fieldName) : fieldName;
  }

  get computedFieldName() {
    let name = this.$store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]
      ? this.fieldItem.query_alias || this.fieldItem.alias_name || this.fieldItem.field_name
      : this.fieldItem.field_name;

    if (this.isFieldObject) {
      const parts = name.split('.');
      name = parts.at(-1) || parts[0];
    }
    return name;
  }

  beforeDestroy() {
    this.instanceDestroy();
  }
  // 数据变化后关闭图表分析
  @Watch('statisticalFieldData')
  statisticalFieldDataChange() {
    debounce(() => {
      this.instanceDestroy();
    }, 100);
  }
  @Emit('toggleItem')
  emitToggleItem(v) {
    return v;
  }
  // 缓存图标信息
  getFieldIconInfo(fieldType: string) {
    if (!this.fieldIconCache[fieldType]) {
      const typeMap = this.fieldTypeMap[fieldType] || {};
      this.fieldIconCache[fieldType] = {
        icon: typeMap.icon || 'bklog-icon bklog-unkown',
        color: typeMap.color || '#EAEBF0',
        textColor: typeMap.textColor || '',
      };
    }
    return this.fieldIconCache[fieldType];
  }

  // 显示或隐藏字段
  handleShowOrHiddenItem() {
    this.instanceDestroy();
    this.emitToggleItem({
      type: this.type,
      fieldItem: this.fieldItem,
    });
  }
  showMore(fieldData, show: boolean) {
    this.ifShowMore = show;
    this.fieldData = fieldData;
  }
  closeSlider() {
    this.ifShowMore = false;
  }
  /** 点击查看图表分析 */
  handleClickAnalysisItem() {
    if (!this.isShowFieldsAnalysis || this.isUnionSearch || this.isFrontStatistics) {
      return;
    }

    this.instanceDestroy();
    this.analysisActive = true;

    const indexSetIDs = this.isUnionSearch
      ? this.unionIndexList
      : [window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId];

    this.queryParams = {
      ...this.retrieveParams,
      index_set_ids: indexSetIDs,
      field_type: this.fieldItem.field_type,
      agg_field: this.agg_field,
      statisticalFieldData: this.statisticalFieldData,
      isFrontStatisticsL: this.isFrontStatistics,
    };

    // 使用nextTick确保DOM更新
    this.$nextTick(() => {
      if (!this.fieldChartRef) {
        return;
      }

      this.operationInstance = this.$bkPopover(this.$refs.operationRef, {
        content: this.fieldChartRef,
        arrow: true,
        placement: 'right-center',
        boundary: 'viewport',
        trigger: 'click',
        theme: 'light analysis-chart',
        interactive: true,
        appendTo: document.body,
        onHidden: () => {
          this.instanceDestroy();
        },
      });
      this.operationInstance.show(100);
    });
  }
  /** 更新Popper位置 */
  updatePopperInstance() {
    setTimeout(() => {
      this.operationInstance.popperInstance.update();
    }, 100);
  }
  instanceDestroy() {
    this.operationInstance?.destroy();
    this.operationInstance = null;
    this.analysisActive = false;
  }
  /** 联合查询并且有冲突字段 */
  isUnionConflictFields(fieldType: string) {
    return this.isUnionSearch && fieldType === 'conflict';
  }

  getFieldIconColor = type => {
    return this.fieldTypeMap?.[type] ? this.fieldTypeMap?.[type]?.color : '#EAEBF0';
  };

  getFieldIconTextColor = type => {
    return this.fieldTypeMap?.[type]?.textColor;
  };
  /** 下载 */
  downloadFieldStatistics() {
    this.btnLoading = true;
    const indexSetIDs = this.isUnionSearch
      ? this.unionIndexList
      : [window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId];
    const downRequestUrl = '/field/index_set/fetch_value_list/';
    const data = {
      ...this.retrieveParams,
      index_set_ids: indexSetIDs,
      field_type: this.fieldItem.field_type,
      agg_field: this.agg_field,
      limit: this.fieldData?.distinct_count,
    };
    axiosInstance
      .post(downRequestUrl, data)
      .then(res => {
        if (typeof res !== 'string') {
          this.$bkMessage({
            theme: 'error',
            message: this.$t('下载失败'),
          });
          return;
        }
        const routerIndexSet = window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId;
        const lightName = this.indexSetList.find(item => item.index_set_id === routerIndexSet)?.lightenName;
        const downloadName = `bk_log_search__${lightName.substring(2, lightName.length - 1)}_${this.fieldItem.field_name}.csv`;
        blobDownload(res, downloadName);
      })
      .finally(() => {
        this.btnLoading = false;
      });
  }
  getDistinctCount(val) {
    this.distinctCount = val;
  }
  render() {
    const fieldIconInfo = this.getFieldIconInfo(this.fieldItem.field_type);
    const iconStyle = {
      backgroundColor: this.fieldItem.is_full_text ? '' : fieldIconInfo.color,
      color: this.fieldItem.is_full_text ? '' : fieldIconInfo.textColor,
    };
    const childrenCount = this.fieldItem.children?.length || 0;

    return (
      <li class='filed-item'>
        <div class={{ 'filed-title': true, expanded: this.isExpand }}>
          <div onClick={this.handleClickAnalysisItem}>
            {/* 拖动字段位置按钮 */}
            <div class='bklog-drag-dots-box'>
              <span class={['icon bklog-icon bklog-drag-dots', { 'hidden-icon': this.type === 'hidden' }]} />
            </div>

            {/* 字段类型对应的图标 */}
            <div class='bklog-field-icon'>
              <span
                style={iconStyle}
                class={[fieldIconInfo.icon, 'field-type-icon']}
                v-bk-tooltips={{
                  content: this.fieldTypeMap[this.fieldItem.field_type]?.name,
                  disabled: !this.fieldTypeMap[this.fieldItem.field_type],
                }}
              />
            </div>

            {/* 字段名 */}
            <span>
              <span class='field-name'>{this.computedFieldName}</span>
              {childrenCount > 0 && (
                <span>
                  <span class='field-badge'>{childrenCount}</span>
                  <span class={['bk-icon', 'expand', this.expandIconShow ? 'icon-angle-up' : 'icon-angle-down']} />
                </span>
              )}

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
          </div>
          <div
            ref='operationRef'
            class={['operation-text', { 'analysis-active': this.analysisActive }]}
          >
            {this.isShowFieldsAnalysis && !this.isUnionSearch && !this.isFrontStatistics && (
              <div
                class='operation-icon-box'
                v-bk-tooltips={{ content: this.$t('图表分析') }}
                onClick={e => {
                  e.stopPropagation();
                  this.handleClickAnalysisItem();
                }}
              >
                <i class='bklog-icon bklog-chart-2' />
              </div>
            )}
            <div
              class='operation-icon-box'
              v-bk-tooltips={{
                content: this.type === 'visible' ? this.$t('隐藏') : this.$t('显示'),
              }}
              onClick={e => {
                e.stopPropagation();
                this.handleShowOrHiddenItem();
              }}
            >
              <i class={['bk-icon include-icon', this.type === 'visible' ? 'icon-eye' : 'icon-eye-slash']} />
            </div>
          </div>
          <div style='display: none'>
            <div ref='fieldChart'>
              {this.analysisActive && (
                <FieldAnalysis
                  queryParams={this.queryParams}
                  on-downloadFieldStatistics={this.downloadFieldStatistics}
                  on-showMore={this.showMore}
                  on-statisticsInfoFinish={this.updatePopperInstance}
                />
              )}
            </div>
          </div>
        </div>

        {this.ifShowMore && (
          <bk-sideslider
            width={480}
            class='agg-field-item-sideslider'
            is-show={true}
            show-mask={false}
            quick-close
            transfer
            onAnimation-end={this.closeSlider}
          >
            <template slot='header'>
              <div class='agg-sides-slider-header'>
                <div class='distinct-num'>
                  <span class='field-name'>{this.fieldItem?.field_name}</span>
                  <div class='col-line' />
                  <span class='distinct-count-label'>{this.$t('去重后字段统计')}</span>
                  <span class='distinct-count-num'>{`(${this.distinctCount})`}</span>
                </div>
                <div class='fnBtn'>
                  <bk-button
                    loading={this.btnLoading}
                    size='small'
                    text
                    onClick={e => {
                      e.stopPropagation();
                      this.downloadFieldStatistics();
                    }}
                  >
                    <div class='download-btn'>
                      <i class='bklog-icon bklog-download' />
                      <span>{this.$t('下载')}</span>
                    </div>
                  </bk-button>
                  {/* <bk-button size='small'>查看仪表盘</bk-button> */}
                </div>
              </div>
            </template>
            <template slot='content'>
              <div class='agg-sides-content slider-content'>
                <AggChart
                  field-name={this.agg_field}
                  field-type={this.fieldItem.field_type}
                  is-front-statistics={this.isFrontStatistics}
                  limit={this.fieldData?.distinct_count}
                  parent-expand={this.isExpand}
                  retrieve-params={this.retrieveParams}
                  statistical-field-data={this.statisticalFieldData}
                  onDistinctCount={this.getDistinctCount}
                />
              </div>
            </template>
          </bk-sideslider>
        )}
      </li>
    );
  }
}
