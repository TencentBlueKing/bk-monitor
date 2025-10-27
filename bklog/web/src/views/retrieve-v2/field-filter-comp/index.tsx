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

import { TABLE_LOG_FIELDS_SORT_REGULAR, getRegExp } from '@/common/util';
import { builtInInitHiddenList } from '@/const/index.js';
import VueDraggable from 'vuedraggable';

import EmptyStatus from '../../../components/empty-status/index.vue';
import { BK_LOG_STORAGE } from '../../../store/store.type';
import FieldItem from './field-item';
// import FieldSelectConfig from './components/field-select-config.vue';

import FieldSetting from './update/field-setting.vue';

import './index.scss';

@Component
export default class FieldFilterComp extends tsc<object> {
  @Prop({ type: Array, default: () => [] }) totalFields: any[];
  @Prop({ type: Array, default: () => [] }) visibleFields: any[];
  @Prop({ type: Array, default: () => [] }) sortList: any[];
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias: object;
  @Prop({ type: Object, default: () => ({}) }) retrieveParams: object;
  @Prop({ type: Array, default: () => [] }) datePickerValue: any[];
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
  expandedNodes = {}; // 用于存储展开节点的 key
  builtInHeaderList = ['log', 'ip', 'utctime', 'path'];
  builtInInitHiddenList = builtInInitHiddenList;

  isShowAllBuiltIn = false;
  isShowAllIndexSet = false;

  isShowErrInfo = false;
  get errInfo() {
    const key = 'retrieve/getLogTableHead';
    return this.$store.state.apiErrorInfo[key] || '';
  }
  /** 可选字段 */
  get hiddenFields() {
    return this.totalFields.filter(item => !this.visibleFields.some(visibleItem => item === visibleItem));
  }
  /** 显示字段 */
  get showFields() {
    return this.objectHierarchy(this.visibleFields);
  }
  get statisticalFieldsData() {
    // 这里避免初始化的时候数据已经更新，但视图却未更新，加入请求完毕的loading进行监听
    // this.$store.state.indexSetQueryResult.is_loading;
    return this.$store.state.retrieveDropdownData;
  }

  /** 内置字段 */
  indexSetFields() {
    const underlineFieldList: any[] = []; // 下划线的字段
    const otherList: any[] = []; // 其他字段
    const { indexHiddenFields } = this.hiddenFilterFields();
    // 类似__xxx__的字段放最后展示
    for (const fieldItem of indexHiddenFields) {
      if (/^[_]{1,2}/g.test(fieldItem.field_name)) {
        underlineFieldList.push(fieldItem);
        continue;
      }
      otherList.push(fieldItem);
    }
    return this.sortHiddenList([otherList, underlineFieldList]);
  }
  /** 非已选字段 分别生成内置字段和索引字段 */
  hiddenFilterFields() {
    const builtInHiddenFields: any[] = [];
    const indexHiddenFields: any[] = [];
    for (const item of this.hiddenFields) {
      // if (item.field_type === '__virtual__' || item.is_built_in) {
      if (this.builtInInitHiddenList.includes(item.field_name)) {
        builtInHiddenFields.push(item);
        continue;
      }
      indexHiddenFields.push(item);
    }
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
        if (!isHeaderItem) {
          acc.filterHeaderBuiltFields.push(cur);
        }
        return acc;
      },
      {
        headerList: [],
        filterHeaderBuiltFields: [],
      },
    );
    const arr = [...headerList, ...this.sortHiddenList([filterHeaderBuiltFields])];
    const result = this.objectHierarchy(arr);
    return result;
    // return [...headerList, ...this.sortHiddenList([filterHeaderBuiltFields])];
  }
  /** object格式字段的层级展示 */
  objectHierarchy(arrData) {
    const [objArr, otherArr] = arrData.reduce(
      // biome-ignore lint/nursery/noShadow: reason
      ([objArr, otherArr], item) => {
        item.field_name.includes('.') ? objArr.push(item) : otherArr.push(item);
        return [objArr, otherArr];
      },
      [[], []],
    );
    if (!objArr.length) {
      return arrData;
    }
    const objectField: any[] = [];
    for (const item of objArr) {
      this.addToNestedStructure(objectField, item);
    }
    return [
      ...objectField,
      ...otherArr.filter(item => {
        return !objectField.map(field => field.field_name).includes(item.field_name);
      }),
    ];
  }
  /** 递归将数组变成tree */
  addToNestedStructure(targetArray, originalObject) {
    const parts = originalObject.field_name.split('.');
    let currentLevel = targetArray;
    let parentFieldName: null | string = null; // 用于存储父节点的名称
    parts.forEach((part, index) => {
      let existingPart = currentLevel.find(item => item.field_name === part);
      if (!existingPart) {
        existingPart = { field_name: part, filterVisible: true, field_type: 'object' };
        if (parentFieldName !== null) {
          existingPart.parentFieldName = parentFieldName;
        }
        existingPart.fullName = parentFieldName
          ? `${parentFieldName}.${existingPart.field_name}`
          : existingPart.field_name;
        if (index < parts.length - 1) {
          existingPart.children = [];
        }
        currentLevel.push(existingPart);
      }
      parentFieldName = parentFieldName ? `${parentFieldName}.${part}` : part;
      if (index === parts.length - 1) {
        Object.assign(existingPart, originalObject);
      }
      currentLevel = existingPart.children;
    });
  }
  /** 递归将tree变回数组 */
  convertNestedStructureToArray(nestedArray) {
    const flatten = nodes => {
      const result: any[] = [];
      for (const node of nodes) {
        const currentPath = node.field_name;
        const { children, ...restProps } = node;
        if (node.field_type !== 'object') {
          result.push({
            ...restProps,
            field_name: currentPath,
          });
        }
        if (children && children.length > 0) {
          result.push(...flatten(children));
        }
      }
      return result;
    };
    return flatten(nestedArray);
  }
  /** 内置字段展示对象 */
  builtInFieldsShowObj() {
    const builtInFieldsValue = this.builtInFields();
    const { initHiddenList, otherList } = builtInFieldsValue.reduce(
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

    const visibleBuiltLength = builtInFieldsValue.filter(item => item.filterVisible).length;
    const hiddenFieldVisible =
      !!initHiddenList.filter(item => item.filterVisible).length && visibleBuiltLength === builtInFieldsValue.length;
    return {
      // 若没找到初始隐藏的内置字段且内置字段不足10条则不展示展开按钮
      isShowBuiltExpandBtn: visibleBuiltLength || hiddenFieldVisible,
      // 非初始隐藏的字段展示小于10条的 并且不把初始隐藏的字段带上
      builtInShowFields: this.isShowAllBuiltIn || this.searchKeyword ? [...otherList, ...initHiddenList] : [],
    };
  }
  getIsShowIndexSetExpand() {
    return this.indexSetFields().filter(item => item.filterVisible && !item.field_name.includes('.')).length > 10;
  }
  /** 展示的可选字段 */
  get showIndexSetFields() {
    if (this.searchKeyword) {
      return this.objectHierarchy(this.indexSetFields());
    }
    const result = this.objectHierarchy(
      this.isShowAllIndexSet ? this.indexSetFields() : this.sliceFields(this.indexSetFields()),
    );
    return result;
  }
  get filterTypeCount() {
    // 过滤的条件数量
    let count = 0;
    if (this.polymerizable !== '0') {
      count += 1;
    }
    if (this.fieldType !== 'any') {
      count += 1;
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
      default: {
        const { scenario_id_white_list: scenarioIdWhiteList } = (window as any).FIELD_ANALYSIS_CONFIG;
        const { field_analysis_config: fieldAnalysisConfig } = (window as any).FEATURE_TOGGLE_WHITE_LIST;
        const scenarioID = this.indexSetItem.items?.[0]?.scenario_id;
        isFront = !(scenarioIdWhiteList?.includes(scenarioID) && fieldAnalysisConfig?.includes(Number(this.bkBizId)));
        break;
      }
    }
    return isFront;
  }

  get indexSetId() {
    return window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId;
  }

  @Watch('indexSetId')
  watchRouteIndexID() {
    // 切换索引集重置状态
    this.polymerizable = '0';
    this.fieldType = 'any';
    this.isShowAllBuiltIn = false;
    this.isShowAllIndexSet = false;
  }

  @Watch('showFieldAlias')
  watchShowFieldAlias() {
    // 过滤关键字
    this.filterListByCondition();
  }

  @Watch('visibleFields', { immediate: true, deep: true })
  watchVisibleFields() {
    this.dragVisibleFields = this.visibleFields.map(item => item.field_name);
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
    const { searchKeyword } = this;
    const regExp = getRegExp(searchKeyword.trim());
    for (const fieldList of [this.visibleFields, this.hiddenFields]) {
      for (const fieldItem of fieldList) {
        regExp.lastIndex = 0; // 重置lastIndex,这个正则有全局标志
        fieldItem.filterVisible =
          regExp.test(fieldItem.field_name) ||
          regExp.test(fieldItem.field_alias) ||
          regExp.test(fieldItem.query_alias || '');
      }
    }
    this.$nextTick(() => {
      for (const refName of Object.keys(this.$refs)) {
        if (refName.startsWith('bigTreeRef-')) {
          const bigTreeRef = this.$refs[refName];
          bigTreeRef?.filter(searchKeyword);
        }
      }
    });
  }
  filterMethod(keyword, node) {
    const fieldItem = node.data;
    const regExp = getRegExp(keyword.trim());
    return regExp.test(fieldItem.field_name) || regExp.test(fieldItem.query_alias || '');
  }
  handleVisibleMoveEnd() {
    this.$emit('fields-updated', this.dragVisibleFields);
  }
  // 字段显示或隐藏
  handleToggleItem(type: string, fieldItem) {
    const displayFieldNames = this.visibleFields.map(item => item.field_name);
    // object格式单独处理
    if (fieldItem.field_type === 'object') {
      const fieldName = fieldItem.parentFieldName
        ? `${fieldItem.parentFieldName}.${fieldItem.field_name}`
        : fieldItem.field_name;

      if (type === 'visible') {
        // 需要隐藏字段
        const index = this.visibleFields.findIndex(item => fieldName === item.field_name);
        displayFieldNames.splice(index, 1);
      } else {
        // 需要显示字段 如果已存在不进行操作
        if (this.visibleFields.some(item => item.field_name === fieldName)) {
          return;
        }
        displayFieldNames.push(fieldName);
      }
    } else if (type === 'visible') {
      // 需要隐藏字段
      const index = this.visibleFields.findIndex(item => fieldItem.field_name === item.field_name);
      displayFieldNames.splice(index, 1);
    } else {
      // 需要显示字段
      displayFieldNames.push(fieldItem.field_name);
    }
    this.$emit('fields-updated', displayFieldNames);
  }
  /**
   * @desc: 字段名排序
   * @param {Array} list
   * @returns {Array}
   */
  sortHiddenList(list) {
    const sortList: any[] = [];
    for (const item of list) {
      const sortItem = item.sort((a, b) => {
        const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        return sortA.localeCompare(sortB);
      });
      sortList.push(...sortItem);
    }
    return sortList;
  }
  /**
   * @desc: 分割展示字段名（排除object字段名）
   * @param {Array} list
   * @returns {Array}
   */
  sliceFields(Fields) {
    const { withDot, withoutDot } = Fields.reduce(
      (acc, str) => {
        if (str.field_name.includes('.')) {
          acc.withDot.push(str);
        } else {
          acc.withoutDot.push(str);
        }
        return acc;
      },
      { withDot: [], withoutDot: [] },
    );
    return [...withDot, ...withoutDot.slice(0, 10)];
  }
  handleSearchException(type: string) {
    if (type === 'clear-filter') {
      this.searchKeyword = '';
      this.filterListByCondition();
    }
    this.isShowErrInfo = false;
    this.$store.dispatch('requestIndexSetFieldInfo');
  }
  // 记录bigTree展开节点
  expandChange(TreeNode, ref) {
    this.expandedNodes[ref] = this.expandedNodes[ref] || [];
    if (TreeNode.expanded) {
      if (!this.expandedNodes[ref].includes(TreeNode.id)) {
        this.expandedNodes[ref].push(TreeNode.id);
      }
    } else {
      this.expandedNodes[ref] = this.expandedNodes[ref].filter(id => id !== TreeNode.id);
    }
  }
  bigTreeRender(field, index) {
    const defaultExpandedNodes = this.expandedNodes[`bigTreeRef-${index}`];
    const scopedSlots = {
      default: ({ data }) => (
        <FieldItem
          key={data.field_name}
          v-show={data.filterVisible}
          date-picker-value={this.datePickerValue}
          field-alias-map={this.fieldAliasMap}
          field-item={data}
          is-front-statistics={this.isFrontStatistics}
          isFieldObject={true}
          retrieve-params={this.retrieveParams}
          show-field-alias={this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]}
          statistical-field-data={this.statisticalFieldsData[data.field_name]}
          type={index.includes('show') ? 'visible' : 'hidden'}
          onToggleItem={({ type, fieldItem }) => this.handleToggleItem(type, fieldItem)}
        />
      ),
    };
    return (
      <bk-big-tree
        key={field.field_name}
        ref={`bigTreeRef-${index}`}
        class='big-tree'
        data={[field]}
        default-expanded-nodes={defaultExpandedNodes}
        expand-on-click={true}
        filter-method={(keyword, node) => this.filterMethod(keyword, node)}
        options={{ nameKey: 'fullName', idKey: 'fullName', childrenKey: 'children' }}
        scopedSlots={scopedSlots}
        on-expand-change={node => this.expandChange(node, `bigTreeRef-${index}`)}
      />
    );
  }
  render() {
    return (
      <div class='field-filter-box'>
        <div class='form-container'>
          <bk-input
            class='king-input'
            v-model={this.searchKeyword}
            data-test-id='fieldFilter_input_searchFieldName'
            placeholder={this.$t('搜索 字段名')}
            right-icon='icon-search'
            clearable
            onChange={() => this.filterListByCondition()}
            // onClear={() => this.handleSearchException('clear-filter')}
          />
        </div>
        <div
          ref='fieldFilter'
          class='field-filter-container-new'
        >
          {!this.totalFields.filter(item => item.filterVisible).length && (
            <EmptyStatus
              style={{ marginTop: '20%' }}
              emptyType={this.searchKeyword ? 'search-empty' : '500'}
              showText={!!this.searchKeyword}
              onOperation={this.handleSearchException}
            >
              {!this.searchKeyword && (
                <div class='error-empty'>
                  <p>
                    {this.$t('获取字段列表失败')}
                    <i
                      class='bklog-icon bklog-log-refresh'
                      v-bk-tooltips={{ content: this.$t('刷新') }}
                      onClick={() => this.handleSearchException('refresh')}
                    />
                    <i
                      class={`bklog-icon bklog-${this.isShowErrInfo ? 'collapse-small' : 'expand-small'}`}
                      v-bk-tooltips={{ content: this.$t('详情') }}
                      onClick={() => (this.isShowErrInfo = !this.isShowErrInfo)}
                    />
                  </p>
                  {this.isShowErrInfo && <div class='error-info'>{this.errInfo}</div>}
                </div>
              )}
            </EmptyStatus>
          )}
          {!!this.totalFields.filter(item => item.filterVisible).length && (
            <div class='fields-container is-selected'>
              <div class='title'>
                <span>{this.$t('显示字段')}</span>
                <FieldSetting />
              </div>
              {this.visibleFields.filter(item => item.filterVisible).length ? (
                <VueDraggable
                  class='filed-list'
                  v-model={this.dragVisibleFields}
                  {...{ props: this.dragOptions }}
                  animation='150'
                  on-end={this.handleVisibleMoveEnd}
                >
                  <transition-group>
                    {this.visibleFields.map(item => (
                      // item.children?.length ? this.bigTreeRender(item, index+'show') :
                      <FieldItem
                        key={item.field_name}
                        v-show={item.filterVisible}
                        date-picker-value={this.datePickerValue}
                        field-alias-map={this.fieldAliasMap}
                        field-item={item}
                        is-front-statistics={this.isFrontStatistics}
                        retrieve-params={this.retrieveParams}
                        show-field-alias={this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]}
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
            {!!this.indexSetFields().filter(item => item.filterVisible).length && (
              <div class='fields-container not-selected optional-field'>
                <div class='title'>{this.$t('可选字段')}</div>
                <ul class='filed-list'>
                  {this.showIndexSetFields.map((item, index) =>
                    item.children?.length ? (
                      this.bigTreeRender(item, `${index}select`)
                    ) : (
                      <FieldItem
                        key={`${index}-${item}`}
                        v-show={item.filterVisible}
                        date-picker-value={this.datePickerValue}
                        field-alias-map={this.fieldAliasMap}
                        field-item={item}
                        is-front-statistics={this.isFrontStatistics}
                        retrieve-params={this.retrieveParams}
                        show-field-alias={this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]}
                        statistical-field-data={this.statisticalFieldsData[item.field_name]}
                        type='hidden'
                        onToggleItem={({ type, fieldItem }) => this.handleToggleItem(type, fieldItem)}
                      />
                    ),
                  )}
                  {this.getIsShowIndexSetExpand() && (
                    <div
                      class='expand-all'
                      onClick={() => (this.isShowAllIndexSet = !this.isShowAllIndexSet)}
                    >
                      {this.isShowAllIndexSet ? this.$t('收起') : this.$t('展开全部')}
                    </div>
                  )}
                </ul>
              </div>
            )}
            {/* 内置字段 */}
            {!!this.builtInFields().filter(item => item.filterVisible).length && (
              <div class='fields-container not-selected inside-fields'>
                <div
                  class='title'
                  onClick={() => (this.isShowAllBuiltIn = !this.isShowAllBuiltIn)}
                >
                  <span class={['bklog-icon bklog-arrow-down-filled-2', { 'is-expand-all': this.isShowAllBuiltIn }]} />
                  {(this.$t('label-内置字段') as string).replace('label-', '')}
                </div>
                <ul class='filed-list'>
                  {this.builtInFieldsShowObj().builtInShowFields.map((item, index) =>
                    item.children?.length ? (
                      this.bigTreeRender(item, `${index}built`)
                    ) : (
                      <FieldItem
                        key={`${index}-${item}`}
                        v-show={item.filterVisible}
                        date-picker-value={this.datePickerValue}
                        field-alias-map={this.fieldAliasMap}
                        field-item={item}
                        is-front-statistics={this.isFrontStatistics}
                        retrieve-params={this.retrieveParams}
                        show-field-alias={this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]}
                        statistical-field-data={this.statisticalFieldsData[item.field_name]}
                        type='hidden'
                        onToggleItem={({ type, fieldItem }) => this.handleToggleItem(type, fieldItem)}
                      />
                    ),
                  )}
                  {/* {this.builtInFieldsShowObj().isShowBuiltExpandBtn && (
                    <div
                      class='expand-all'
                      onClick={() => (this.isShowAllBuiltIn = !this.isShowAllBuiltIn)}
                    >
                      {!this.isShowAllBuiltIn ? this.$t('展开全部') : this.$t('收起')}
                    </div>
                  )} */}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
