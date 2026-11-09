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

import type { FieldInfoItem } from '@/app/state/store.type';
import { Component, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { TABLE_LOG_FIELDS_SORT_REGULAR, getRegExp } from '@/shared/lib/util';
import { builtInInitHiddenList } from '@/shared/constants/index.ts';
import { isFeatureToggleOn } from '@/shared/composables/use-feature-toggle';
import VueDraggable from 'vuedraggable-vue3';
import { Input, Tree as TTree, Tooltip as TTooltip } from 'tdesign-vue-next';
import 'tdesign-vue-next/es/input/style/index.css';

import EmptyStatus from '../../../../shared/ui/empty-status/index.vue';
import { storeRuntimeCacheService } from '../../../../app/state/services/runtime-cache.service.js';
import { BK_LOG_STORAGE } from '../../../../app/state/store.type.ts';
import FieldItem from './field-item';
// import FieldSelectConfig from './components/field-select-config.vue';

import FieldSetting from './update/field-setting.vue';

import './index.scss';

interface FieldTreeNode extends FieldInfoItem {
  children?: FieldTreeNode[];
  fullName?: string;
  full_name?: string;
  parentFieldName?: string;
  parent_field_name?: string;
  filterVisible?: boolean;
}

Object.assign(VueDraggable, { compatConfig: { MODE: 3 } });
// Vue.Draggable 4.1 emits `end`, but its published declaration omits Sortable events.
// Keep the installed props and add only the event used by this business list.
type FieldDragInstance = InstanceType<typeof VueDraggable> & {
  $props: InstanceType<typeof VueDraggable>['$props'] & { onEnd?: () => void };
};
const FieldDraggable = VueDraggable as typeof VueDraggable & (new () => FieldDragInstance);

interface FieldFilterCompProps {
  totalFields?: FieldTreeNode[];
  visibleFields?: FieldTreeNode[];
  sortList?: any[];
  fieldAliasMap?: object;
  showFieldAlias?: boolean;
  retrieveParams?: object;
  datePickerValue?: any[];
  indexSetItem?: any;
  onFieldsUpdated?: (value0: string[]) => void;
}

@Component
export default class FieldFilterComp extends tsc<FieldFilterCompProps> {
  @Prop({ type: Array, default: () => [] }) totalFields!: FieldTreeNode[];
  @Prop({ type: Array, default: () => [] }) visibleFields!: FieldTreeNode[];
  @Prop({ type: Array, default: () => [] }) sortList!: any[];
  @Prop({ type: Object, default: () => ({}) }) fieldAliasMap!: object;
  @Prop({ type: Boolean, default: false }) showFieldAlias!: boolean;
  @Prop({ type: Object, default: () => ({}) }) retrieveParams!: object;
  @Prop({ type: Array, default: () => [] }) datePickerValue!: any[];
  @Prop({ type: Object, default: () => ({}) }) indexSetItem!: any;
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
  dragVisibleFields: string[] = [];
  expandedNodes: Record<string, string[]> = {}; // 用于存储展开节点的 key
  expandedFieldIds: Record<string, boolean> = {}; // 按 fullName 记录已展开节点，只挂载下一层 children
  builtInHeaderList = ['log', 'ip', 'utctime', 'path'];
  builtInInitHiddenList = builtInInitHiddenList;

  isShowAllBuiltIn = false;
  isShowAllIndexSet = false;

  isShowErrInfo = false;
  fieldTreeBroken = false;

  errorCaptured(err: unknown) {
    console.error('[field-filter] render failed', err);
    this.fieldTreeBroken = true;
    return false;
  }
  get errInfo() {
    const isScene = this.$store.getters.isSceneMode;
    const key = isScene ? 'retrieve/getSceneFields' : 'retrieve/getLogTableHead';
    return this.$store.state.apiErrorInfo[key] || '';
  }
  get isFieldLoading() {
    return this.$store.state.indexFieldInfo.is_loading;
  }
  get hasFilterVisibleFields() {
    return this.totalFields.length > 0;
  }
  /** 可选字段 */
  get hiddenFields() {
    const visibleFieldNames = new Set(this.visibleFields.map((item) => item?.field_name).filter(Boolean));
    return this.totalFields.filter((item) => item?.field_name && !visibleFieldNames.has(item.field_name));
  }
  /** 显示字段 */
  get showFields() {
    return this.objectHierarchy(this.visibleFields);
  }
  get statisticalFieldsData() {
    // 版本号用于触发视图更新，实际大对象存放在 runtime cache / IndexedDB 镜像中。
    void this.$store.state.retrieveDropdownDataVersion;
    return storeRuntimeCacheService.getRetrieveDropdownData(this.$store.state.indexId || 'default');
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
  objectHierarchy(arrData: FieldTreeNode[]) {
    const tree = this.$store.getters.fieldTree;
    return this.pickFieldTree(tree, arrData);
  }
  /** 递归将tree变回数组 */
  convertNestedStructureToArray(nestedArray: FieldTreeNode[]) {
    const flatten = (nodes: FieldTreeNode[]): FieldTreeNode[] => {
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
      (acc: { initHiddenList: any[]; otherList: any[] }, cur: { field_name: string }) => {
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

    const visibleBuiltLength = builtInFieldsValue.filter((item) => item.filterVisible).length;
    const hiddenFieldVisible =
      !!initHiddenList.filter((item: { filterVisible: any }) => item.filterVisible).length &&
      visibleBuiltLength === builtInFieldsValue.length;

    return {
      // 若没找到初始隐藏的内置字段且内置字段不足10条则不展示展开按钮
      isShowBuiltExpandBtn: visibleBuiltLength || hiddenFieldVisible,
      // 非初始隐藏的字段展示小于10条的 并且不把初始隐藏的字段带上
      builtInShowFields: this.isShowAllBuiltIn || this.searchKeyword ? [...otherList, ...initHiddenList] : [],
    };
  }
  get indexSetFieldTree() {
    return this.objectHierarchy(this.indexSetFields());
  }
  getIsShowIndexSetExpand() {
    const tree = this.indexSetFieldTree;
    return tree.length > 10 || tree.some((item) => item.children?.length);
  }
  get expandedFieldIdSet() {
    return new Set(Object.keys(this.expandedFieldIds).filter((id) => this.expandedFieldIds[id]));
  }
  /** 只把已展开节点的下一层 children 交给树，避免一次挂上全部后代 */
  hydrateVisibleTree(node: FieldTreeNode, expandedSet: Set<string>): FieldTreeNode {
    const childList = node.children || [];
    if (!childList.length) {
      return { ...node, children: undefined };
    }
    const nodeId = node.fullName || node.full_name || node.field_name;
    if (!expandedSet.has(nodeId)) {
      return {
        ...node,
        children: childList.map((child) => ({
          ...child,
          children: undefined,
        })),
      };
    }
    return {
      ...node,
      children: childList.map((child) => this.hydrateVisibleTree(child, expandedSet)),
    };
  }
  markSearchExpanded(
    nodes: FieldTreeNode[] | undefined,
    keyword: string,
    expanded: Record<string, boolean>,
    ancestors: string[] = [],
  ) {
    if (!keyword) {
      return false;
    }
    const regExp = getRegExp(keyword.trim());
    let matched = false;
    for (const node of nodes || []) {
      const nodeId = node.fullName || node.full_name || node.field_name;
      const selfMatch =
        regExp.test(node.field_name || '') ||
        regExp.test(node.field_alias || '') ||
        regExp.test(node.query_alias || '');
      const childMatch = this.markSearchExpanded(node.children, keyword, expanded, [...ancestors, nodeId]);
      if (selfMatch || childMatch) {
        matched = true;
        ancestors.forEach((id) => {
          expanded[id] = true;
        });
      }
    }
    return matched;
  }
  getLazyFieldTree(nodes: FieldTreeNode[]) {
    const expanded = { ...this.expandedFieldIds };
    if (this.searchKeyword) {
      this.markSearchExpanded(nodes, this.searchKeyword, expanded);
    }
    const expandedSet = new Set(Object.keys(expanded).filter((id) => expanded[id]));
    return (nodes || []).map((node: FieldTreeNode) => this.hydrateVisibleTree(node, expandedSet));
  }
  /** 折叠时最多 10 个根；展开全部也只按层挂载，不一次渲染 1117 个节点 */
  get showIndexSetFields() {
    const tree = this.indexSetFieldTree;
    const roots = this.searchKeyword || this.isShowAllIndexSet ? tree : tree.slice(0, 10);
    return this.getLazyFieldTree(roots);
  }
  get builtInLazyShowFields() {
    return this.getLazyFieldTree(this.builtInFieldsShowObj().builtInShowFields);
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
        const { scenario_id_white_list: scenarioIdWhiteList } = (window as any).FIELD_ANALYSIS_CONFIG || {};
        const scenarioID = this.indexSetItem.items?.[0]?.scenario_id;
        isFront = !(
          scenarioIdWhiteList?.includes(scenarioID) && isFeatureToggleOn('field_analysis_config', this.bkBizId)
        );
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
    this.expandedNodes = {};
    this.expandedFieldIds = {};
  }

  @Watch('showFieldAlias')
  watchShowFieldAlias() {
    // 过滤关键字
    this.filterListByCondition();
  }

  @Watch('visibleFields', { immediate: true, deep: true })
  watchVisibleFields() {
    this.dragVisibleFields = this.visibleFields.map((item) => item.field_name);
  }

  // 字段类型过滤：可聚合、字段类型
  handleFilter({ polymerizable, fieldType }: { polymerizable: string; fieldType: string }) {
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
          regExp.test(fieldItem.field_alias ?? '') ||
          regExp.test(fieldItem.query_alias || '');
      }
    }
  }
  filterMethod(keyword: string, node: { data: any }) {
    const fieldItem = node.data;
    const regExp = getRegExp(keyword.trim());
    return regExp.test(fieldItem.field_name) || regExp.test(fieldItem.query_alias || '');
  }
  handleVisibleMoveEnd() {
    this.$emit('fields-updated', this.dragVisibleFields);
  }
  getFieldFullName(fieldItem: FieldTreeNode) {
    if (fieldItem.full_name || fieldItem.fullName) {
      return fieldItem.full_name || fieldItem.fullName;
    }

    const parentFieldName = fieldItem.parentFieldName || fieldItem.parent_field_name;
    const fieldName = fieldItem.field_name;
    if (parentFieldName && typeof fieldName === 'string' && !fieldName.startsWith(`${parentFieldName}.`)) {
      return `${parentFieldName}.${fieldName}`;
    }

    return fieldName;
  }

  getDisplayFieldName(fieldItem: { field_type: string; field_name: any }) {
    return fieldItem.field_type === 'object' ? this.getFieldFullName(fieldItem) : fieldItem.field_name;
  }

  // 字段显示或隐藏
  handleToggleItem(type: string, fieldItem: { field_type: string; field_name: any }) {
    const displayFieldNames = this.visibleFields.map((item) => item.field_name);
    const fieldName = this.getDisplayFieldName(fieldItem);

    if (!fieldName) {
      return;
    }

    if (type === 'visible') {
      // 需要隐藏字段
      const index = displayFieldNames.findIndex((item) => item === fieldName);
      if (index > -1) {
        displayFieldNames.splice(index, 1);
      }
    } else {
      // 需要显示字段 如果已存在不进行操作
      if (displayFieldNames.includes(fieldName)) {
        return;
      }
      displayFieldNames.push(fieldName);
    }
    this.$emit('fields-updated', displayFieldNames);
  }
  /**
   * @desc: 字段名排序
   * @param {Array} list
   * @returns {Array}
   */
  sortHiddenList(list: FieldTreeNode[][]) {
    const sortList: any[] = [];
    for (const item of list) {
      const sortItem = item.sort((a: { field_name: string }, b: { field_name: string }) => {
        const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        return sortA.localeCompare(sortB);
      });
      sortList.push(...sortItem);
    }
    return sortList;
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
  expandChange(TreeNode: { id: any; expanded: any }, ref: string) {
    this.expandedNodes[ref] = this.expandedNodes[ref] || [];
    const nodeId = TreeNode.id;
    if (TreeNode.expanded) {
      if (!this.expandedNodes[ref].includes(nodeId)) {
        this.expandedNodes[ref].push(nodeId);
      }
      if (nodeId) {
        this.expandedFieldIds[nodeId] = true;
      }
    } else {
      this.expandedNodes[ref] = this.expandedNodes[ref].filter((id: unknown) => id !== nodeId);
      if (nodeId) {
        delete this.expandedFieldIds[nodeId];
      }
    }
  }
  bigTreeRender(field: FieldTreeNode, index: string) {
    const searchExpanded = { ...this.expandedFieldIds };
    if (this.searchKeyword) this.markSearchExpanded([field], this.searchKeyword, searchExpanded);
    const defaultExpandedNodes = Array.from(
      new Set([
        ...(this.expandedNodes[`bigTreeRef-${index}`] || []),
        ...Object.keys(searchExpanded).filter((id) => searchExpanded[id]),
      ]),
    );
    const scopedSlots = {
      default: ({ data }: { data: FieldTreeNode }) => (
        <FieldItem
          key={data.field_name}
          v-show={data.filterVisible}
          datePickerValue={this.datePickerValue}
          fieldAliasMap={this.fieldAliasMap}
          fieldItem={data}
          isFrontStatistics={this.isFrontStatistics}
          isFieldObject={true}
          retrieveParams={this.retrieveParams}
          showFieldAlias={this.showFieldAlias}
          statisticalFieldData={this.statisticalFieldsData[data.field_name]}
          type={index.includes('show') ? 'visible' : 'hidden'}
          onToggleItem={({ type, fieldItem }: { type: string; fieldItem: FieldTreeNode }) =>
            this.handleToggleItem(type, fieldItem)
          }
        />
      ),
    };
    return (
      <TTree
        key={field.field_name}
        class='big-tree'
        icon={false}
        transition={false}
        data={[field]}
        expanded={defaultExpandedNodes}
        expandOnClickNode
        keys={{ label: 'fullName', value: 'fullName', children: 'children' }}
        filter={this.searchKeyword ? (node) => this.filterMethod(this.searchKeyword, { data: node.data }) : undefined}
        v-slots={{
          label: (scope: { node?: { data?: FieldTreeNode } } = {} as any) => {
            const data = scope?.node?.data;
            if (!data) return [];
            const content = scopedSlots.default({ data });
            if (content == null || content === false) return [];
            return Array.isArray(content) ? content : [content];
          },
        }}
        onExpand={(values, { node }) => {
          if (node.value == null) return;
          this.expandChange({ id: node.value, expanded: values.includes(node.value) }, `bigTreeRef-${index}`);
        }}
      />
    );
  }
  pickFieldTree(treeData: FieldTreeNode[], arrData: FieldTreeNode[]): FieldTreeNode[] {
    if (!treeData?.length || !arrData?.length) {
      return [];
    }

    const sourceByName = new Map(arrData.map((item) => [item.field_name, item]));
    const visit = (node: FieldTreeNode): FieldTreeNode | null => {
      const children = (node.children ?? [])
        .map(visit)
        .filter((item): item is NonNullable<typeof item> => Boolean(item));
      const fieldName = node.full_name || node.fullName || node.field_name || '';
      const sourceField = fieldName ? sourceByName.get(fieldName) : undefined;
      if (!sourceField && !children.length) {
        return null;
      }
      const fullName = sourceField?.fullName || sourceField?.full_name || node.fullName || node.full_name || fieldName;

      return {
        ...(sourceField ?? node),
        field_name: sourceField?.field_name || node.field_name || fullName,
        fullName,
        full_name: fullName,
        filterVisible: sourceField?.filterVisible ?? node.filterVisible ?? true,
        children: children.length ? children : undefined,
      };
    };

    return treeData.map(visit).filter((item): item is NonNullable<typeof item> => Boolean(item));
  }
  render() {
    return (
      <div class='field-filter-box'>
        <div class='form-container'>
          <Input
            class='king-input'
            value={this.searchKeyword}
            data-test-id='fieldFilter_input_searchFieldName'
            placeholder={this.$t('搜索 字段名')}
            suffixIcon={() => <i class='bk-icon icon-search' />}
            clearable
            onChange={(value) => {
              this.searchKeyword = value as string;
              this.filterListByCondition();
            }}
            // onClear={() => this.handleSearchException('clear-filter')}
          />
        </div>
        <div ref='fieldFilter' class='field-filter-container-new'>
          {!this.isFieldLoading && !this.hasFilterVisibleFields && (!!this.searchKeyword || !!this.errInfo) && (
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
                    <TTooltip content={this.$t('刷新')}>
                      <i class='bklog-icon bklog-log-refresh' onClick={() => this.handleSearchException('refresh')} />
                    </TTooltip>
                    <TTooltip content={this.$t('详情')}>
                      <i
                        class={`bklog-icon bklog-${this.isShowErrInfo ? 'collapse-small' : 'expand-small'}`}
                        onClick={() => (this.isShowErrInfo = !this.isShowErrInfo)}
                      />
                    </TTooltip>
                  </p>
                  {this.isShowErrInfo && <div class='error-info'>{this.errInfo}</div>}
                </div>
              )}
            </EmptyStatus>
          )}
          {this.hasFilterVisibleFields && (
            <div class='fields-container is-selected'>
              <div class='title'>
                <span>{this.$t('显示字段')}</span>
                <FieldSetting />
              </div>
              {this.visibleFields.filter((item) => item.filterVisible).length ? (
                <FieldDraggable
                  class='filed-list'
                  v-model={this.dragVisibleFields}
                  itemKey={(name: string) => name}
                  {...this.dragOptions}
                  onEnd={this.handleVisibleMoveEnd}
                  v-slots={{
                    item: (slotProps?: { element?: string }) => {
                      const element = slotProps?.element;
                      const item = element
                        ? this.visibleFields.find((field) => field.field_name === element)
                        : undefined;
                      if (!item) return [];
                      return [
                        <FieldItem
                          key={item.field_name}
                          v-show={item.filterVisible}
                          datePickerValue={this.datePickerValue}
                          fieldAliasMap={this.fieldAliasMap}
                          fieldItem={item}
                          isFrontStatistics={this.isFrontStatistics}
                          retrieveParams={this.retrieveParams}
                          showFieldAlias={this.showFieldAlias}
                          statisticalFieldData={this.statisticalFieldsData[item.field_name]}
                          type='visible'
                          visibleFields={this.visibleFields}
                          onToggleItem={({ type, fieldItem }: { type: string; fieldItem: FieldTreeNode }) =>
                            this.handleToggleItem(type, fieldItem)
                          }
                        />,
                      ];
                    },
                  }}
                />
              ) : (
                <span class='all-field-item'>{this.$t('当前显示全部字段')}</span>
              )}
            </div>
          )}
          <div class='field-filter-roll'>
            {!!this.indexSetFieldTree.some((item) => item.filterVisible) && (
              <div class='fields-container not-selected optional-field'>
                <div class='title'>{this.$t('可选字段')}</div>
                <ul class='filed-list'>
                  {this.showIndexSetFields.map((item: FieldTreeNode, index: number) =>
                    item.children?.length && !this.fieldTreeBroken ? (
                      this.bigTreeRender(item, `${index}select`)
                    ) : (
                      <FieldItem
                        key={`${index}-${item}`}
                        v-show={item.filterVisible}
                        datePickerValue={this.datePickerValue}
                        fieldAliasMap={this.fieldAliasMap}
                        fieldItem={item}
                        isFrontStatistics={this.isFrontStatistics}
                        retrieveParams={this.retrieveParams}
                        showFieldAlias={this.showFieldAlias}
                        statisticalFieldData={this.statisticalFieldsData[item.field_name]}
                        type='hidden'
                        onToggleItem={({ type, fieldItem }: { type: string; fieldItem: FieldTreeNode }) =>
                          this.handleToggleItem(type, fieldItem)
                        }
                      />
                    ),
                  )}
                  {this.getIsShowIndexSetExpand() && (
                    <div class='expand-all' onClick={() => (this.isShowAllIndexSet = !this.isShowAllIndexSet)}>
                      {this.isShowAllIndexSet ? this.$t('收起') : this.$t('展开全部')}
                    </div>
                  )}
                </ul>
              </div>
            )}
            {/* 内置字段 */}
            {!!this.builtInFields().filter((item) => item.filterVisible).length && (
              <div class='fields-container not-selected inside-fields'>
                <div class='title' onClick={() => (this.isShowAllBuiltIn = !this.isShowAllBuiltIn)}>
                  <span class={['bklog-icon bklog-arrow-down-filled-2', { 'is-expand-all': this.isShowAllBuiltIn }]} />
                  {(this.$t('label-内置字段') as string).replace('label-', '')}
                </div>
                <ul class='filed-list'>
                  {this.builtInLazyShowFields.map((item: FieldTreeNode, index: number) =>
                    item.children?.length && !this.fieldTreeBroken ? (
                      this.bigTreeRender(item, `${index}built`)
                    ) : (
                      <FieldItem
                        key={`${index}-${item}`}
                        v-show={item.filterVisible}
                        datePickerValue={this.datePickerValue}
                        fieldAliasMap={this.fieldAliasMap}
                        fieldItem={item}
                        isFrontStatistics={this.isFrontStatistics}
                        retrieveParams={this.retrieveParams}
                        showFieldAlias={this.showFieldAlias}
                        statisticalFieldData={this.statisticalFieldsData[item.field_name]}
                        type='hidden'
                        onToggleItem={({ type, fieldItem }: { type: string; fieldItem: FieldTreeNode }) =>
                          this.handleToggleItem(type, fieldItem)
                        }
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
