import { Tag as TTag } from 'tdesign-vue-next';

import { MessagePlugin as TDesignMessage, Button as TButton } from 'tdesign-vue-next';
import { Popup as TPopup, Drawer as TDrawer, Tooltip as TTooltip } from 'tdesign-vue-next';
import type { PopupInstanceFunctions, PopupVisibleChangeContext } from 'tdesign-vue-next';
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
import type { ApplicationInjections } from '@/shared/types/component-injections';
import { Component as tsc } from 'vue-tsx-support';

import { blobDownload } from '@/shared/lib/util';
import { debounce } from 'lodash-es';

import { axiosInstance } from '@/platform/http/index';
import { BK_LOG_STORAGE } from '../../../../app/state/store.type.ts';
import AggChart from './agg-chart';
import FieldAnalysis from './field-analysis';
import objectFieldTreeMeta from './object-field-tree-meta';

import './field-item.scss';
import { LocationQueryValue } from 'vue-router';

const { resolveObjectFieldChildrenCount, shouldShowObjectFieldTreeMeta } = objectFieldTreeMeta;
interface FieldItemProps {
  type?: string;
  fieldItem?: any;
  fieldAliasMap?: object;
  showFieldAlias?: boolean;
  datePickerValue?: any[];
  retrieveSearchNumber?: number;
  retrieveParams: any;
  visibleFields?: any[];
  statisticalFieldData?: object;
  isFrontStatistics: boolean;
  isFieldObject?: boolean;
  onToggleItem?: (value: { type: string; fieldItem: any }, arg0: { type: string; fieldItem: any }) => void;
}

interface FieldItem {
  $t: ApplicationInjections['$t'];
}

@Component
class FieldItem extends tsc<FieldItemProps> {
  @Prop({ type: String, default: 'visible', validator: (v) => ['visible', 'hidden'].includes(v as string) })
  type!: string;
  @Prop({ type: Object, default: () => ({}) }) fieldItem!: any;
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap!: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias!: boolean;
  @Prop({ type: Array, default: () => [] }) datePickerValue!: any[];
  @Prop({ type: Number, default: 0 }) retrieveSearchNumber!: number;
  @Prop({ type: Object, required: true }) retrieveParams!: any;
  @Prop({ type: Array, default: () => [] }) visibleFields!: any[];
  @Prop({ type: Object, default: () => ({}) }) statisticalFieldData!: object;
  @Prop({ type: Boolean, required: true }) isFrontStatistics!: boolean;
  @Prop({ type: Boolean, default: false }) isFieldObject!: boolean;
  @Ref('analysisPopup') analysisPopupRef!: PopupInstanceFunctions;
  @Ref('statsDrawerContent') statsDrawerContentRef!: HTMLElement;
  isExpand = false;
  analysisActive = false;
  ifShowMore = false;
  fieldData = null;
  distinctCount = 0;
  btnLoading = false;
  expandIconShow = false;

  fieldIconCache: Record<string, { icon: string; color: string; textColor: string }> = {};

  get queryParams() {
    const isScene = this.$store.getters.isSceneMode;
    const baseParams = {
      ...this.retrieveParams,
      field_type: this.fieldItem.field_type,
      agg_field: this.agg_field,
      statisticalFieldData: this.statisticalFieldData,
      isFrontStatisticsL: this.isFrontStatistics,
    };

    if (!isScene) {
      const indexSetIDs = this.isUnionSearch
        ? this.unionIndexList
        : [window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId];
      baseParams.index_set_ids = indexSetIDs;
    }

    return baseParams;
  }

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
    return this.$store.state.retrieve?.flatIndexSetList ?? [];
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
      .filter((item: { index_set_id: any }) => this.unionIndexList.includes(item.index_set_id))
      .map((item: { indexName: any }) => item.indexName);
  }

  /** 聚合 / 请求始终使用业务主键 field_name，禁止把 UI 别名写入请求参数 */
  get agg_field() {
    return this.fieldItem.field_name;
  }

  get computedFieldName() {
    let name = this.$store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]
      ? this.fieldItem.query_alias || this.fieldItem.field_name
      : this.fieldItem.field_name;

    if (this.isFieldObject) {
      const parts = name.split('.');
      name = parts.at(-1) || parts[0];
    }
    return name;
  }

  get isFieldDisplayToggleSupported() {
    return true;
  }

  beforeDestroy() {
    this.instanceDestroy();
    this.detachDrawerOutside();
  }
  @Watch('ifShowMore')
  handleDrawerVisibilityChange(visible: boolean) {
    this.detachDrawerOutside();
    if (visible) document.addEventListener('mousedown', this.handleDrawerOutside, true);
  }
  detachDrawerOutside() {
    document.removeEventListener('mousedown', this.handleDrawerOutside, true);
  }
  handleDrawerOutside(event: MouseEvent) {
    if (!this.ifShowMore) return;
    const drawer = this.statsDrawerContentRef?.closest('.agg-field-item-sideslider');
    if (drawer && event.composedPath().includes(drawer)) return;
    this.closeSlider();
  }
  // 数据变化后关闭图表分析
  @Watch('statisticalFieldData')
  statisticalFieldDataChange() {
    debounce(() => {
      this.instanceDestroy();
    }, 100);
  }
  @Emit('toggleItem')
  emitToggleItem(v: { type: string; fieldItem: any }) {
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
  showMore(fieldData: null, show: boolean) {
    this.ifShowMore = show;
    this.fieldData = fieldData;
  }
  closeSlider() {
    this.ifShowMore = false;
  }
  /** 点击查看图表分析 */
  handleClickAnalysisItem(event?: MouseEvent) {
    if (!this.isShowFieldsAnalysis || this.isFrontStatistics) {
      return;
    }

    // The controlled popup must not treat the opening title click as an outside click.
    event?.stopPropagation();
    this.instanceDestroy();
    this.analysisActive = true;
  }
  handleAnalysisVisibleChange(visible: boolean, context: PopupVisibleChangeContext) {
    // Field/title and action icons retain their explicit V2 click handlers.
    if (context.trigger === 'trigger-element-click') return;
    if (!visible) this.instanceDestroy();
  }

  /** 更新Popper位置 */
  updatePopperInstance() {
    setTimeout(() => {
      this.analysisPopupRef?.update?.();
    }, 100);
  }
  instanceDestroy() {
    this.analysisActive = false;
  }
  /** 联合查询并且有冲突字段 */
  isUnionConflictFields(fieldType: string) {
    return this.isUnionSearch && fieldType === 'conflict';
  }

  getFieldIconColor = (type: string | number) => {
    return this.fieldTypeMap?.[type] ? this.fieldTypeMap?.[type]?.color : '#EAEBF0';
  };

  getFieldIconTextColor = (type: string | number) => {
    return this.fieldTypeMap?.[type]?.textColor;
  };
  /** 下载 */
  downloadFieldStatistics() {
    this.btnLoading = true;
    const isScene = this.$store.getters.isSceneMode;
    const downRequestUrl = isScene ? '/search/scene/field/fetch_value_list/' : '/field/index_set/fetch_value_list/';
    const indexSetIDs = this.isUnionSearch
      ? this.unionIndexList
      : [window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId];
    const data = {
      ...this.retrieveParams,
      ...(isScene ? {} : { index_set_ids: indexSetIDs }),
      field_type: this.fieldItem.field_type,
      agg_field: this.agg_field,
      limit: this.fieldData?.distinct_count,
    };
    axiosInstance
      .post(downRequestUrl, data)
      .then((res) => {
        if (typeof res !== 'string') {
          TDesignMessage('error', { content: this.$t('下载失败') });
          return;
        }
        const routerIndexSet = window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId;
        const lightName = this.indexSetList.find((item) => item.index_set_id === routerIndexSet)?.lightenName;
        const downloadName = `bk_log_search__${lightName.substring(2, lightName.length - 1)}_${this.fieldItem.field_name}.csv`;
        blobDownload(res, downloadName);
      })
      .finally(() => {
        this.btnLoading = false;
      });
  }
  getDistinctCount(val: number) {
    this.distinctCount = val;
  }
  render() {
    const fieldIconInfo = this.getFieldIconInfo(this.fieldItem.field_type);
    const iconStyle = {
      backgroundColor: this.fieldItem.is_full_text ? '' : fieldIconInfo.color,
      color: this.fieldItem.is_full_text ? '' : fieldIconInfo.textColor,
    };
    const childrenCount = resolveObjectFieldChildrenCount(this.fieldItem);
    const showObjectTreeMeta = shouldShowObjectFieldTreeMeta(this.isFieldObject, childrenCount);
    const showAnalysisOperation = this.isShowFieldsAnalysis && !this.isFrontStatistics;
    const showOperationText = showAnalysisOperation || this.isFieldDisplayToggleSupported;

    return (
      <li class='filed-item'>
        <TPopup
          ref='analysisPopup'
          visible={this.analysisActive}
          trigger='click'
          placement='right'
          showArrow
          attach='body'
          overlayClassName='analysis-chart-popup bklog-v3-popover-tag'
          overlayInnerStyle={{ padding: '5px 10px', lineHeight: 'normal' }}
          onVisibleChange={this.handleAnalysisVisibleChange}
          v-slots={{
            content: () =>
              this.analysisActive ? (
                <FieldAnalysis
                  queryParams={this.queryParams}
                  onDownloadFieldStatistics={this.downloadFieldStatistics}
                  onShowMore={this.showMore}
                  onStatisticsInfoFinish={this.updatePopperInstance}
                />
              ) : null,
          }}
        >
          <div class={{ 'filed-title': true, expanded: this.isExpand }}>
            <div onClick={this.handleClickAnalysisItem}>
              {/* 拖动字段位置按钮 */}
              <div class='bklog-drag-dots-box'>
                <span class={['icon bklog-icon bklog-drag-dots', { 'hidden-icon': this.type === 'hidden' }]} />
              </div>

              {/* 字段类型对应的图标 */}
              <div class='bklog-field-icon'>
                <TTooltip
                  content={this.fieldTypeMap[this.fieldItem.field_type]?.name}
                  disabled={!this.fieldTypeMap[this.fieldItem.field_type]}
                >
                  <span style={iconStyle} class={[fieldIconInfo.icon, 'field-type-icon']} />
                </TTooltip>
              </div>

              {/* 字段名 */}
              <span>
                <span class='field-name'>{this.computedFieldName}</span>
                {showObjectTreeMeta && (
                  <span>
                    <span class='field-badge'>{childrenCount}</span>
                    <span class={['bk-icon', 'expand', this.expandIconShow ? 'icon-angle-up' : 'icon-angle-down']} />
                  </span>
                )}

                {this.isUnionConflictFields(this.fieldItem.field_type) && (
                  <TPopup
                    v-slots={{
                      content: () => (
                        <div>
                          <p>{this.$t('该字段在以下索引集存在冲突')}</p>
                          {this.unionConflictFieldsName.map((item: unknown) => (
                            <TTag key={String(item)} variant='light' data-v2-display='tag'>
                              {item}
                            </TTag>
                          ))}
                        </div>
                      ),
                    }}
                    overlayClassName='conflict-popover'
                    placement='top'
                  >
                    <i class='conflict-icon bk-icon icon-exclamation-triangle-shape' />
                  </TPopup>
                )}
              </span>
            </div>
            {showOperationText && (
              <div ref='operationRef' class={['operation-text', { 'analysis-active': this.analysisActive }]}>
                {showAnalysisOperation && (
                  <TTooltip content={this.$t('图表分析')}>
                    <div
                      class='operation-icon-box'
                      onClick={(e) => {
                        e.stopPropagation();
                        this.handleClickAnalysisItem();
                      }}
                    >
                      <i class='bklog-icon bklog-chart-2' />
                    </div>
                  </TTooltip>
                )}
                {this.isFieldDisplayToggleSupported && (
                  <TTooltip content={this.type === 'visible' ? this.$t('隐藏') : this.$t('显示')}>
                    <div
                      class='operation-icon-box'
                      onClick={(e) => {
                        e.stopPropagation();
                        this.handleShowOrHiddenItem();
                      }}
                    >
                      <i class={['bk-icon include-icon', this.type === 'visible' ? 'icon-eye' : 'icon-eye-slash']} />
                    </div>
                  </TTooltip>
                )}
              </div>
            )}
          </div>
        </TPopup>

        {this.ifShowMore && (
          <TDrawer
            v-slots={{
              header: () => (
                <>
                  <div class='agg-sides-slider-header'>
                    <button
                      class='agg-header-close'
                      type='button'
                      aria-label={this.$t('关闭')}
                      onClick={this.closeSlider}
                    >
                      <span class='bklog-icon bklog-arrow-right' />
                    </button>
                    <div class='distinct-num'>
                      <span class='field-name'>{this.fieldItem?.field_name}</span>
                      <div class='col-line' />
                      <span class='distinct-count-label'>{this.$t('去重后字段统计')}</span>
                      <span class='distinct-count-num'>{`(${this.distinctCount})`}</span>
                    </div>
                    <div class='fnBtn'>
                      <TButton
                        loading={this.btnLoading}
                        size='small'
                        onClick={(e: { stopPropagation: () => void }) => {
                          e.stopPropagation();
                          this.downloadFieldStatistics();
                        }}
                        variant={true ? 'text' : 'base'}
                      >
                        <div class='download-btn'>
                          <i class='bklog-icon bklog-download' />
                          <span>{this.$t('下载')}</span>
                        </div>
                      </TButton>
                      {/* <bk-button size='small'>查看仪表盘</bk-button> */}
                    </div>
                  </div>
                </>
              ),
              default: () => (
                <>
                  <div ref='statsDrawerContent' class='agg-sides-content slider-content'>
                    <AggChart
                      fieldName={this.agg_field}
                      fieldType={this.fieldItem.field_type}
                      isFrontStatistics={this.isFrontStatistics}
                      limit={this.fieldData?.distinct_count}
                      parentExpand={this.isExpand}
                      retrieveParams={this.retrieveParams}
                      statisticalFieldData={this.statisticalFieldData}
                      showSearchKeyword={true}
                      onDistinctCount={this.getDistinctCount}
                    />
                  </div>
                </>
              ),
            }}
            size='480px'
            attach='body'
            drawerClassName='agg-field-item-sideslider'
            visible={true}
            closeBtn={false}
            showOverlay={false}
            footer={false}
            closeOnOverlayClick
            onClose={this.closeSlider}
          ></TDrawer>
        )}
      </li>
    );
  }
}

export default FieldItem;
