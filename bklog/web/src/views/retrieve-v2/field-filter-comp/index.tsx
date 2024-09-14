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

import { Component, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { TABLE_LOG_FIELDS_SORT_REGULAR, Debounce } from '@/common/util';
import VueDraggable from 'vuedraggable';

import FieldItem from './field-item';
import $http from '@/api';

import './index.scss';

@Component
export default class FieldFilterComp extends tsc<object> {
  @Prop({ type: Array, default: () => [] }) totalFields: Array<any>;
  @Prop({ type: Array, default: () => [] }) visibleFields: Array<any>;
  @Prop({ type: Array, default: () => [] }) sortList: Array<any>;
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias: object;
  @Prop({ type: Object, default: () => ({}) }) retrieveParams: object;
  @Prop({ type: Array, default: () => [] }) datePickerValue: Array<any>;
  @Prop({ type: Object, default: () => ({}) }) indexSetItem: any;
  @Ref('filterPopover') readonly filterPopoverRef!: HTMLDivElement;
  @Ref('fieldFilter') readonly fieldFilterRef!: HTMLDivElement;

  searchKeyword = '';
  polymerizable = '0'; // 聚合
  fieldType = 'any'; // 字段类型
  dragOptions = {
    animation: '150',
    tag: 'ul',
    handle: '.bklog-drag-dots',
    'ghost-class': 'sortable-ghost-class',
  };
  dragVisibleFields = [];
  builtInHeaderList = ['log', 'ip', 'utctime', 'path'];
  builtInInitHiddenList = [
    'gseIndex',
    'iterationIndex',
    '__dist_01',
    '__dist_03',
    '__dist_05',
    '__dist_07',
    '__dist_09',
    '__ipv6__',
    '__ext',
  ];
  isShowAllBuiltIn = false;
  isShowAllIndexSet = false;
  fieldContainerHeight = 400;

  /** 可选字段 */
  get hiddenFields() {
    return this.totalFields.filter(item => !this.visibleFields.some(visibleItem => item === visibleItem));
  }
  get statisticalFieldsData() {
    // 这里避免初始化的时候数据已经更新，但视图却未更新，加入请求完毕的loading进行监听
    this.$store.state.indexSetQueryResult.is_loading;
    return this.$store.state.retrieveDropdownData;
  }

  /** 内置字段 */
  indexSetFields() {
    const underlineFieldList = []; // 下划线的字段
    const otherList = []; // 其他字段
    const { indexHiddenFields } = this.hiddenFilterFields();
    // 类似__xxx__的字段放最后展示
    indexHiddenFields.forEach(fieldItem => {
      if (/^[_]{1,2}/g.test(fieldItem.field_name)) {
        underlineFieldList.push(fieldItem);
        return;
      }
      otherList.push(fieldItem);
    });
    return this.sortHiddenList([otherList, underlineFieldList]);
  }
  /** 非已选字段 分别生成内置字段和索引字段 */
  hiddenFilterFields() {
    const builtInHiddenFields = [];
    const indexHiddenFields = [];
    this.hiddenFields.forEach(item => {
      if (item.field_type === '__virtual__' || item.is_built_in) {
        builtInHiddenFields.push(item);
        return;
      }
      indexHiddenFields.push(item);
    });
    return {
      builtInHiddenFields,
      indexHiddenFields,
    };
  }
  /** 排序后的内置字段 */
  builtInFields() {
    const { builtInHiddenFields } = this.hiddenFilterFields();
    const { headerList, filterHeaderBuiltFields } = builtInHiddenFields.reduce(
      (acc, cur) => {
        // 判断内置字段需要排在前面几个字段
        let isHeaderItem = false;
        for (const headerItem of this.builtInHeaderList) {
          if (cur.field_name === headerItem) {
            isHeaderItem = true;
            acc.headerList.push(cur);
            break;
          }
        }
        if (!isHeaderItem) acc.filterHeaderBuiltFields.push(cur);
        return acc;
      },
      {
        headerList: [],
        filterHeaderBuiltFields: [],
      },
    );
    return [...headerList, ...this.sortHiddenList([filterHeaderBuiltFields])];
  }
  /** 内置字段展示对象 */
  builtInFieldsShowObj() {
    const { initHiddenList, otherList } = this.builtInFields().reduce(
      (acc, cur) => {
        if (this.builtInInitHiddenList.includes(cur.field_name)) {
          acc.initHiddenList.push(cur);
        } else {
          acc.otherList.push(cur);
        }
        return acc;
      },
      {
        initHiddenList: [],
        otherList: [],
      },
    );
    const visibleBuiltLength = this.builtInFields().filter(item => item.filterVisible).length;
    const hiddenFieldVisible = !!initHiddenList.filter(item => item.filterVisible).length;
    return {
      // 若没找到初始隐藏的内置字段且内置字段不足10条则不展示展开按钮
      isShowBuiltExpandBtn: visibleBuiltLength > 10 || hiddenFieldVisible,
      // 非初始隐藏的字段展示小于10条的 并且不把初始隐藏的字段带上
      builtInShowFields: this.isShowAllBuiltIn ? [...otherList, ...initHiddenList] : otherList.slice(0, 9),
    };
  }
  getIsShowIndexSetExpand() {
    return this.indexSetFields().filter(item => item.filterVisible).length > 10;
  }
  /** 展示的内置字段 */
  get showIndexSetFields() {
    return this.isShowAllIndexSet ? this.indexSetFields : this.indexSetFields().slice(0, 9);
  }
  get filterTypeCount() {
    // 过滤的条件数量
    let count = 0;
    if (this.polymerizable !== '0') {
      count = count + 1;
    }
    if (this.fieldType !== 'any') {
      count = count + 1;
    }
    return count;
  }
  get filedSettingConfigID() {
    // 当前索引集的显示字段ID
    return this.$store.state.retrieve.filedSettingConfigID;
  }
  get unionIndexList() {
    return this.$store.getters.unionIndexList;
  }
  get isUnionSearch() {
    return this.$store.getters.isUnionSearch;
  }
  get bkBizId() {
    return this.$store.state.bkBizId;
  }
  /** 未开启白名单时 是否由前端来统计总数 */
  get isFrontStatistics() {
    let isFront = true;
    const { field_analysis_config: fieldAnalysisToggle } = (window as any).FEATURE_TOGGLE;
    switch (fieldAnalysisToggle) {
      case 'on':
        isFront = false;
        break;
      case 'off':
        isFront = true;
        break;
      default:
        const { scenario_id_white_list: scenarioIdWhiteList } = (window as any).FIELD_ANALYSIS_CONFIG;
        const { field_analysis_config: fieldAnalysisConfig } = (window as any).FEATURE_TOGGLE_WHITE_LIST;
        const scenarioID = this.indexSetItem.items?.[0]?.scenario_id;
        isFront = !(scenarioIdWhiteList?.includes(scenarioID) && fieldAnalysisConfig?.includes(Number(this.bkBizId)));
        break;
    }
    return isFront;
  }

  @Watch('$route.params.indexId')
  watchRouteIndexID() {
    // 切换索引集重置状态
    this.polymerizable = '0';
    this.fieldType = 'any';
    this.isShowAllBuiltIn = false;
    this.isShowAllIndexSet = false;
  }

  @Watch('visibleFields.length')
  watchVisibleFields() {
    this.dragVisibleFields = this.visibleFields.map(item => item.field_name);
  }

  mounted() {
    window.addEventListener('resize', this.updateContainerHeight);
    this.updateContainerHeight();
  }

  beforeDestroy() {
    window.removeEventListener('resize', this.updateContainerHeight);
  }

  @Debounce(200)
  updateContainerHeight() {
    this.$nextTick(() => {
      const height = Math.floor(window.innerHeight - this.fieldFilterRef?.getBoundingClientRect().top);
      this.fieldContainerHeight = height >= 150 ? height : 150;
    });
  }

  // 字段类型过滤：可聚合、字段类型
  handleFilter({ polymerizable, fieldType }) {
    this.polymerizable = polymerizable;
    this.fieldType = fieldType;
    this.filterListByCondition();
    this.isShowAllBuiltIn = false;
    this.isShowAllIndexSet = false;
  }
  // 按过滤条件对字段进行过滤
  filterListByCondition() {
    const { polymerizable, fieldType, searchKeyword } = this;
    [this.visibleFields, this.hiddenFields].forEach(fieldList => {
      fieldList.forEach(fieldItem => {
        fieldItem.filterVisible =
          fieldItem.field_name.includes(searchKeyword) &&
          !(
            (polymerizable === '1' && !fieldItem.es_doc_values) ||
            (polymerizable === '2' && fieldItem.es_doc_values) ||
            (fieldType === 'number' && !['long', 'integer'].includes(fieldItem.field_type)) ||
            (fieldType === 'date' && !['date', 'date_nanos'].includes(fieldItem.field_type)) ||
            (!['any', 'number', 'date'].includes(fieldType) && fieldItem.field_type !== fieldType)
          );
      });
    });
  }

  handleVisibleMoveEnd() {
    this.$emit('fields-updated', this.dragVisibleFields);
  }
  // 字段显示或隐藏
  async handleToggleItem(type: string, fieldItem) {
    const displayFieldNames = this.visibleFields.map(item => item.field_name);
    if (type === 'visible') {
      // 需要隐藏字段
      const index = this.visibleFields.findIndex(item => fieldItem.field_name === item.field_name);
      displayFieldNames.splice(index, 1);
    } else {
      // 需要显示字段
      displayFieldNames.push(fieldItem.field_name);
    }
    this.$emit('fields-updated', displayFieldNames);
    if (!displayFieldNames.length) return; // 可以设置为全部隐藏，但是不请求接口
    $http
      .request('retrieve/postFieldsConfig', {
        params: { index_set_id: this.$route.params.indexId },
        data: {
          display_fields: displayFieldNames,
          sort_list: this.sortList,
          config_id: this.filedSettingConfigID,
          index_set_id: this.$route.params.indexId,
          index_set_ids: this.unionIndexList,
          index_set_type: this.isUnionSearch ? 'union' : 'single',
        },
      })
      .catch(e => {
        console.warn(e);
      });
  }
  /**
   * @desc: 字段命排序
   * @param {Array} list
   * @returns {Array}
   */
  sortHiddenList(list) {
    const sortList = [];
    list.forEach(item => {
      const sortItem = item.sort((a, b) => {
        const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        return sortA.localeCompare(sortB);
      });
      sortList.push(...sortItem);
    });
    return sortList;
  }

  render() {
    return (
      <div class='field-filter-box'>
        <div class='form-container'>
          <bk-input
            class='king-input'
            v-model={this.searchKeyword}
            data-test-id='fieldFilter_input_searchFieldName'
            placeholder={this.$t('搜索字段名')}
            right-icon='icon-search'
            clearable
            onChange={() => this.filterListByCondition()}
          ></bk-input>
        </div>
        <div
          ref='fieldFilter'
          style={{ height: `${this.fieldContainerHeight}px` }}
          class='field-filter-container'
        >
          {!!this.totalFields.length && (
            <div class='fields-container is-selected'>
              <div class='title'>{this.$t('显示字段')}</div>
              {!!this.visibleFields.length ? (
                <VueDraggable
                  class='filed-list'
                  v-model={this.dragVisibleFields}
                  {...{ props: this.dragOptions }}
                  animation='150'
                  on-end={this.handleVisibleMoveEnd}
                >
                  <transition-group>
                    {this.visibleFields.map(item => (
                      <FieldItem
                        key={item.field_name}
                        v-show={item.filterVisible}
                        date-picker-value={this.datePickerValue}
                        field-alias-map={this.fieldAliasMap}
                        field-item={item}
                        is-front-statistics={this.isFrontStatistics}
                        retrieve-params={this.retrieveParams}
                        show-field-alias={this.showFieldAlias}
                        statistical-field-data={this.statisticalFieldsData[item.field_name]}
                        type='visible'
                        visible-fields={this.visibleFields}
                        onToggleItem={({ type, fieldItem }) => this.handleToggleItem(type, fieldItem)}
                      />
                    ))}
                  </transition-group>
                </VueDraggable>
              ) : (
                <span class='all-field-item'>{this.$t('当前显示全部字段')}</span>
              )}
            </div>
          )}
          <div class='field-filter-roll'>
            {!!this.indexSetFields().length && (
              <div class='fields-container not-selected'>
                <div class='title'>{this.$t('可选字段')}</div>
                <ul class='filed-list'>
                  {this.showIndexSetFields.map(item => (
                    <FieldItem
                      v-show={item.filterVisible}
                      date-picker-value={this.datePickerValue}
                      field-alias-map={this.fieldAliasMap}
                      field-item={item}
                      is-front-statistics={this.isFrontStatistics}
                      retrieve-params={this.retrieveParams}
                      show-field-alias={this.showFieldAlias}
                      statistical-field-data={this.statisticalFieldsData[item.field_name]}
                      type='hidden'
                      onToggleItem={({ type, fieldItem }) => this.handleToggleItem(type, fieldItem)}
                    />
                  ))}
                  {this.getIsShowIndexSetExpand() && (
                    <div
                      class='expand-all'
                      onClick={() => (this.isShowAllIndexSet = !this.isShowAllIndexSet)}
                    >
                      {!this.isShowAllIndexSet ? this.$t('展开全部') : this.$t('收起')}
                    </div>
                  )}
                </ul>
              </div>
            )}

            {!!this.builtInFields().length && (
              <div class='fields-container not-selected'>
                <div class='title'>{(this.$t('label-内置字段') as string).replace('label-', '')}</div>
                <ul class='filed-list'>
                  {this.builtInFieldsShowObj().builtInShowFields.map(item => (
                    <FieldItem
                      v-show={item.filterVisible}
                      date-picker-value={this.datePickerValue}
                      field-alias-map={this.fieldAliasMap}
                      field-item={item}
                      is-front-statistics={this.isFrontStatistics}
                      retrieve-params={this.retrieveParams}
                      show-field-alias={this.showFieldAlias}
                      statistical-field-data={this.statisticalFieldsData[item.field_name]}
                      type='hidden'
                      onToggleItem={({ type, fieldItem }) => this.handleToggleItem(type, fieldItem)}
                    />
                  ))}
                  {this.builtInFieldsShowObj().isShowBuiltExpandBtn && (
                    <div
                      class='expand-all'
                      onClick={() => (this.isShowAllBuiltIn = !this.isShowAllBuiltIn)}
                    >
                      {!this.isShowAllBuiltIn ? this.$t('展开全部') : this.$t('收起')}
                    </div>
                  )}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
