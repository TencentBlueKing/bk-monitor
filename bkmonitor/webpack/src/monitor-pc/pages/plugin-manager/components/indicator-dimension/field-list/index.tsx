/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Inject, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { Debounce } from 'monitor-common/utils';

import EmptyStatus from '../../../../../components/empty-status/empty-status';
import PluginBatchEdit from '../batch-edit';
import PluginMetricDetail from '../metric-detail';

import type { EmptyStatusType } from '../../../../../components/empty-status/types';

import {
  ALL_LABEL,
  GROUP_DEFAULT_NAME,
  type IBatchField,
  type IFlatField,
  type IPluginGroup,
  type ISelectedGroup,
  type IUnitItem,
  type MonitorType,
} from '../types';
import { fieldUid, filterFieldsByGroup, fuzzyMatch } from '../utils';

import './index.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

interface IEmits {
  onBatchMove: (targetName: string, uids: string[]) => void;
  onEditField: (uid: string, patch: Partial<IFlatField>) => void;
  onMoveField: (uid: string, targetName: string) => void;
  onSaveBatch: (rows: IBatchField[], deletedUids: string[]) => void;
  onShowAddGroup: () => void;
}

interface IProps {
  canManage?: boolean;
  fieldList: IFlatField[];
  groupList: IPluginGroup[];
  mode: MonitorType;
  selectedGroup: ISelectedGroup;
  typeList: { id: string; name: string }[];
  unitList: IUnitItem[];
}

@Component
export default class PluginFieldList extends tsc<IProps, IEmits> {
  @Prop({ default: 'metric' }) mode: IProps['mode'];
  @Prop({ default: () => [] }) fieldList: IProps['fieldList'];
  @Prop({ default: () => [] }) groupList: IProps['groupList'];
  @Prop({ default: () => ({ name: ALL_LABEL }) }) selectedGroup: IProps['selectedGroup'];
  @Prop({ default: () => [] }) unitList: IProps['unitList'];
  @Prop({ default: () => [] }) typeList: IProps['typeList'];
  @Prop({ default: true }) canManage: boolean;

  @Inject({ from: 'authority', default: () => ({ MANAGE_AUTH: true }) }) authority;
  @Inject({ from: 'handleShowAuthorityDetail', default: () => () => {} }) handleShowAuthorityDetail;

  @Ref() readonly metricDetailRef!: HTMLDivElement;
  @Ref() readonly tableBoxRef!: HTMLDivElement;

  search = [];
  keyword = '';
  emptyType: EmptyStatusType = 'empty';
  editingIndex = -1;
  copyAlias = '';
  tableInstance = {
    page: 1,
    pageSize: 30,
    pageList: [10, 20, 30, 50, 100],
  };
  selectedMap: Record<string, IFlatField> = {};
  allCheckValue: 0 | 1 | 2 = 0;
  isShowBatchEdit = false;
  showDetail = false;
  detailUid = '';
  tableBoxHeight = window.innerHeight;
  selectPopoverOption = {
    boundary: 'body',
    flipBehavior: ['bottom'],
  };
  tableHeight = window.innerHeight - 360;
  refreshCount = 0;

  get tableKey() {
    return `${this.mode}-${this.selectedGroup.name}-${this.tableInstance.pageSize}-${this.tableInstance.page}-${this.refreshCount}`;
  }

  get groupSelectList() {
    return this.groupList.map(item => ({
      id: item.table_name,
      name: item.table_name === GROUP_DEFAULT_NAME ? (this.$t('默认分组') as string) : item.table_name,
    }));
  }

  get groupNames() {
    return this.groupList.map(item => item.table_name);
  }

  get metricSearchData() {
    const unitList = this.unitList.flatMap(item => item.formats || []);
    return [
      { name: this.$t('名称'), id: 'name', multiple: false, children: [] },
      { name: this.$t('别名'), id: 'alias', multiple: false, children: [] },
      { name: this.$t('单位'), id: 'unit', multiple: false, children: unitList },
      { name: this.$t('类型'), id: 'type', multiple: false, children: this.typeList },
      {
        name: this.$t('启/停'),
        id: 'status',
        multiple: false,
        children: [
          { id: 'true', name: this.$t('启用') },
          { id: 'false', name: this.$t('停用') },
        ],
      },
    ];
  }

  get filteredList() {
    const base = filterFieldsByGroup(this.fieldList, this.selectedGroup.name, this.mode);
    if (this.mode === 'dimension') {
      if (!this.keyword) return base;
      return base.filter(item => fuzzyMatch(item.name, this.keyword) || fuzzyMatch(item.description, this.keyword));
    }
    if (!this.search.length) return base;
    return base.filter(item => this.matchSearch(item));
  }

  get pagedList() {
    const start = (this.tableInstance.page - 1) * this.tableInstance.pageSize;
    return this.filteredList.slice(start, start + this.tableInstance.pageSize);
  }

  get selectionLength() {
    return Object.keys(this.selectedMap).length;
  }

  get computedWidth() {
    return window.innerWidth < 1920 ? 388 : 456;
  }

  get metricData() {
    return this.fieldList.find(item => item.uid === this.detailUid) || ({} as IFlatField);
  }

  @Watch('pagedList', { deep: true })
  handlePagedListChange() {
    console.log('handlePagedListChange = ', this.refreshCount);
    this.refreshCount++;
  }

  @Watch('mode')
  @Watch('selectedGroup', { immediate: true })
  handleFilterContextChange() {
    this.tableInstance.page = 1;
    this.search = [];
    this.keyword = '';
    this.selectedMap = {};
    this.allCheckValue = 0;
    this.editingIndex = -1;
    this.showDetail = false;
    this.detailUid = '';
  }

  @Watch('metricData', { immediate: true, deep: true })
  handleMetricDataChange() {
    if (!this.metricData?.name) {
      this.showDetail = false;
    }
  }

  @Watch('fieldList')
  handleFieldListChange() {
    this.syncPageSelection();
  }

  @Watch('search', { immediate: true, deep: true })
  handleSearchWatch() {
    this.emptyType = this.search.length || this.keyword ? 'search-empty' : 'empty';
  }

  resizeTableHeight() {
    this.tableHeight = window.innerHeight - 360;
  }

  matchSearch(item: IFlatField) {
    if (this.search.length === 1 && this.search[0].type === 'text') {
      return fuzzyMatch(item.name, this.search[0].id);
    }
    return this.search.every(cond => {
      const values = (cond.values || []).map(v => String(v.id));
      if (!values.length) return true;
      if (cond.id === 'name') return values.some(v => fuzzyMatch(item.name, v));
      if (cond.id === 'alias') return values.some(v => fuzzyMatch(item.description, v));
      if (cond.id === 'unit') return values.includes(item.unit);
      if (cond.id === 'type') return values.includes(item.type);
      if (cond.id === 'status') return values.includes(String(!!item.is_active));
      return true;
    });
  }

  ensureManage() {
    if (this.canManage) return true;
    this.handleShowAuthorityDetail();
    return false;
  }

  handleManage() {
    if (!this.ensureManage()) return;
    this.isShowBatchEdit = true;
  }

  handleSaveBatch(rows: IBatchField[], deletedUids: string[]) {
    this.isShowBatchEdit = false;
    this.$emit('saveBatch', rows, deletedUids);
  }

  handleShowAddGroup() {
    if (!this.ensureManage()) return;
    this.$emit('showAddGroup');
  }

  @Debounce(300)
  handleSearchChange(list = []) {
    this.tableInstance.page = 1;
    this.search = list;
  }

  handleKeywordChange(val: string) {
    this.tableInstance.page = 1;
    this.keyword = val;
    this.emptyType = val ? 'search-empty' : 'empty';
  }

  handleEmptyOperation(type: string) {
    if (type === 'clear-filter') {
      this.search = [];
      this.keyword = '';
    }
  }

  handlePageChange(v: number) {
    this.tableInstance.page = v;
    this.syncPageSelection();
  }

  handleLimitChange(v: number) {
    this.tableInstance.page = 1;
    this.tableInstance.pageSize = v;
    this.syncPageSelection();
  }

  handleDescFocus(props) {
    this.copyAlias = props.row.description || '';
    this.editingIndex = props.$index;
  }

  handleEditDescription(row: IFlatField) {
    if (this.copyAlias === (row.description || '')) {
      this.editingIndex = -1;
      return;
    }
    if (!this.ensureManage()) {
      this.editingIndex = -1;
      return;
    }
    this.$emit('editField', row.uid, { description: this.copyAlias });
    this.editingIndex = -1;
  }

  handleEditActive(row: IFlatField, val: boolean) {
    if (!this.ensureManage()) return;
    this.$emit('editField', row.uid, { is_active: val });
  }

  handleEditType(row: IFlatField, val: string) {
    if (!this.ensureManage()) return;
    this.$emit('editField', row.uid, { type: val });
  }

  handleEditUnit(row: IFlatField, val: string) {
    console.log('handleEditUnit = ', row.uid, val);
    if (!this.ensureManage()) return;
    this.$emit('editField', row.uid, { unit: val });
  }

  handleGroupChange(row: IFlatField, targetName: string) {
    if (targetName === row.table_name) return;
    if (!this.ensureManage()) return;
    this.$emit('moveField', row.uid, targetName);
  }

  handleRowCheck(row: IFlatField) {
    if (row.selection) {
      this.$set(this.selectedMap, row.uid, row);
    } else {
      this.$delete(this.selectedMap, row.uid);
    }
    this.updateCheckValue();
  }

  handleCheckAll(val: boolean) {
    for (const item of this.pagedList) {
      if (val) {
        this.$set(this.selectedMap, item.uid, item);
      } else {
        this.$delete(this.selectedMap, item.uid);
      }
    }
    this.syncPageSelection();
  }

  syncPageSelection() {
    for (const item of this.pagedList) {
      item.selection = !!this.selectedMap[item.uid];
    }
    this.updateCheckValue();
  }

  updateCheckValue() {
    const checkedLength = this.pagedList.filter(item => item.selection).length;
    if (checkedLength > 0) {
      this.allCheckValue = checkedLength < this.pagedList.length ? 1 : 2;
    } else {
      this.allCheckValue = 0;
    }
  }

  handleBatchAdd(groupName: string) {
    if (!this.ensureManage()) return;
    const uids = Object.keys(this.selectedMap);
    if (!uids.length) return;
    this.$emit('batchMove', groupName, uids);
    this.selectedMap = {};
    this.allCheckValue = 0;
  }

  /** 与设置指标&维度页 handleFindUnitName 一致 */
  getUnitName(id: string) {
    if (!id || id === 'none' || id === '--') return '--';
    let name = id;
    for (const group of this.unitList) {
      const res = (group.formats || []).find(item => item.id === id);
      if (res) {
        name = res.name;
      }
    }
    return name;
  }

  getGroupLabel(name: string) {
    return name === GROUP_DEFAULT_NAME ? this.$t('默认分组') : name;
  }

  showMetricDetail(props) {
    if (this.mode !== 'metric') return;
    this.detailUid = props.row.uid;
    this.showDetail = true;
    setTimeout(() => {
      this.tableBoxHeight = (this.tableBoxRef?.scrollHeight || 0) + 63;
    });
  }

  handleClickDetailOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    const isClickDetail = this.metricDetailRef?.contains(target);
    const isNodeExisted = !document.contains(target);
    const isClickSelectPanel = ['bk-select-search-input', 'bk-option-content-default', 'bk-option-name'].includes(
      target.className
    );
    const isClickSelectDropdown = !!target.closest?.('.bk-select-dropdown-content, .tippy-popper');
    if (isClickDetail || isNodeExisted || isClickSelectPanel || isClickSelectDropdown) {
      return;
    }
    if (this.showDetail) {
      this.showDetail = false;
    }
  }

  mounted() {
    document.addEventListener('click', this.handleClickDetailOutside);
    window.addEventListener('resize', this.resizeTableHeight);
  }

  destroyed() {
    document.removeEventListener('click', this.handleClickDetailOutside);
    window.removeEventListener('resize', this.resizeTableHeight);
  }

  renderSelectionHeader() {
    return (
      <bk-checkbox
        indeterminate={this.allCheckValue === 1}
        value={this.allCheckValue === 2}
        onChange={this.handleCheckAll}
      />
    );
  }

  handleMoveField(uid: string, targetName: string) {
    if (this.detailUid === uid) {
      const field = this.fieldList.find(item => item.uid === uid);
      if (field) {
        this.detailUid = fieldUid(targetName, field.monitor_type, field.name);
      }
    }
    this.$emit('moveField', uid, targetName);
  }

  render() {
    const nameSlot = {
      default: props =>
        this.mode === 'metric' ? (
          <div
            class='name'
            v-bk-overflow-tips
            onClick={(e: MouseEvent) => {
              e.stopPropagation();
              this.showMetricDetail(props);
            }}
          >
            {props.row.name || '--'}
          </div>
        ) : (
          <span>{props.row.name || '--'}</span>
        ),
    };
    const aliasSlot = {
      default: props => (
        <div
          class='description-content'
          onClick={() => this.handleDescFocus(props)}
        >
          <bk-input
            ext-cls='description-input'
            readonly={this.editingIndex !== props.$index || !this.canManage}
            value={props.row.description}
            onBlur={() => {
              this.editingIndex = -1;
              this.handleEditDescription(props.row);
            }}
            onChange={v => {
              this.copyAlias = v;
            }}
            onEnter={() => this.handleEditDescription(props.row)}
          />
        </div>
      ),
    };
    const groupSlot = {
      default: ({ row }) => (
        <div class='table-group-box'>
          <bk-select
            clearable={false}
            disabled={!this.canManage}
            searchable={true}
            value={row.table_name}
            onChange={(v: string) => this.handleGroupChange(row, v)}
          >
            {this.groupSelectList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
            <div
              class='edit-group-manage'
              slot='extension'
              onClick={this.handleShowAddGroup}
            >
              <i class='icon-monitor icon-jia' />
              <span>{this.$t('新建分组')}</span>
            </div>
          </bk-select>
        </div>
      ),
    };
    const typeSlot = {
      default: ({ row }) =>
        this.mode === 'metric' ? (
          <bk-select
            clearable={false}
            disabled={!this.canManage}
            value={row.type}
            onChange={(v: string) => this.handleEditType(row, v)}
          >
            {this.typeList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
          </bk-select>
        ) : (
          <span>{row.type || '--'}</span>
        ),
    };
    const unitSlot = {
      default: ({ row }) =>
        this.unitList.length ? (
          <bk-select
            clearable={false}
            disabled={!this.canManage}
            popover-options={this.selectPopoverOption}
            popover-width={120}
            searchable={true}
            value={row.unit}
            onChange={(v: string) => this.handleEditUnit(row, v)}
          >
            {this.unitList.map(group => (
              <bk-option-group
                key={group.id || group.name}
                name={group.name}
              >
                {(group.formats || []).map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-option-group>
            ))}
          </bk-select>
        ) : (
          <span>{this.getUnitName(row.unit)}</span>
        ),
    };
    const statusSlot = {
      default: ({ row }) => (
        <div class='is-active'>
          <bk-switcher
            disabled={!this.canManage}
            size='small'
            theme='primary'
            value={row.is_active}
            onChange={(v: boolean) => this.handleEditActive(row, v)}
          />
        </div>
      ),
    };

    return (
      <div class='plugin-field-list'>
        <div class='plugin-field-list-header'>
          <div class='indicator-btn'>
            <bk-button
              theme='primary'
              onClick={this.handleManage}
            >
              {this.$t('管理')}
            </bk-button>
            {this.mode === 'metric' && (
              <bk-popover
                ext-cls='header-select-btn-popover'
                arrow={false}
                disabled={!this.selectionLength}
                placement='bottom-start'
                theme='light common-monitor'
                trigger='click'
              >
                <div
                  class={['header-select-btn', { 'btn-disabled': !this.selectionLength }]}
                  v-bk-tooltips={{
                    content: this.$t('请先选择指标'),
                    disabled: this.selectionLength,
                  }}
                >
                  <span class='btn-name'>{this.$t('批量操作')}</span>
                  <i class='icon-monitor icon-arrow-down' />
                </div>
                <div
                  class='header-select-list'
                  slot='content'
                >
                  <bk-popover
                    ext-cls='header-select-popover'
                    arrow={false}
                    placement='right-start'
                    theme='light common-monitor'
                  >
                    <div class='list-item'>{this.$t('移动至分组')}</div>
                    <div
                      style='width: 280px;'
                      class='header-select-list mh-300'
                      slot='content'
                    >
                      {this.groupNames.map(group => (
                        <div
                          key={group}
                          class='list-item'
                          onClick={() => this.handleBatchAdd(group)}
                        >
                          {this.getGroupLabel(group)}
                        </div>
                      ))}
                    </div>
                  </bk-popover>
                </div>
              </bk-popover>
            )}
          </div>
          {this.mode === 'metric' ? (
            <SearchSelect
              class='search-table'
              data={this.metricSearchData}
              modelValue={this.search}
              placeholder={this.$t('搜索 名称、别名、单位、类型、启/停')}
              show-popover-tag-change={true}
              on-change={this.handleSearchChange}
            />
          ) : (
            <bk-input
              ext-cls='search-table'
              placeholder={this.$t('搜索 名称、别名')}
              right-icon='icon-monitor icon-mc-search'
              value={this.keyword}
              clearable
              onChange={this.handleKeywordChange}
            />
          )}
        </div>
        <div class='list-body'>
          <div
            ref='tableBoxRef'
            class='table-box'
          >
            <bk-table
              key={this.tableKey}
              v-bkloading={{ isLoading: false }}
              data={this.pagedList}
              height={this.tableHeight}
              outer-border={false}
              class='field-list-table'
            >
              <div slot='empty'>
                <EmptyStatus
                  type={this.emptyType}
                  onOperation={this.handleEmptyOperation}
                />
              </div>
              {this.mode === 'metric' && (
                <bk-table-column
                  key='selection'
                  width='50'
                  align='center'
                  renderHeader={this.renderSelectionHeader}
                  scopedSlots={{
                    default: ({ row }) => (
                      <bk-checkbox
                        v-model={row.selection}
                        onChange={() => this.handleRowCheck(row)}
                      />
                    ),
                  }}
                />
              )}
              <bk-table-column
                key='name'
                min-width='150'
                label={this.$t('名称')}
                prop='name'
                scopedSlots={nameSlot}
              />
              <bk-table-column
                key='alias'
                min-width='180'
                label={this.$t('别名')}
                scopedSlots={aliasSlot}
              />
              <bk-table-column
                key='group'
                min-width='160'
                label={this.$t('分组')}
                scopedSlots={groupSlot}
              />
              <bk-table-column
                key='type'
                min-width='100'
                label={this.$t('类型')}
                scopedSlots={typeSlot}
              />
              {this.mode === 'metric' && (
                <bk-table-column
                  key='unit'
                  min-width='140'
                  label={this.$t('单位')}
                  scopedSlots={unitSlot}
                />
              )}
              <bk-table-column
                key='status'
                width='120'
                label={this.$t('启/停')}
                scopedSlots={statusSlot}
              />
            </bk-table>
            {this.filteredList.length ? (
              <bk-pagination
                class='list-pagination'
                align='right'
                count={this.filteredList.length}
                current={this.tableInstance.page}
                limit={this.tableInstance.pageSize}
                limit-list={this.tableInstance.pageList}
                size='small'
                show-total-count
                on-change={this.handlePageChange}
                on-limit-change={this.handleLimitChange}
              />
            ) : undefined}
          </div>
          {this.mode === 'metric' && (
            <div
              ref='metricDetailRef'
              style={{ width: `${this.computedWidth}px`, height: `${this.tableBoxHeight}px` }}
              class='detail'
              v-show={this.showDetail}
            >
              <PluginMetricDetail
                canManage={this.canManage}
                groupList={this.groupList}
                metricData={this.metricData}
                typeList={this.typeList}
                unitList={this.unitList}
                onClose={() => {
                  this.showDetail = false;
                }}
                onEditField={(uid, patch) => this.$emit('editField', uid, patch)}
                onMoveField={this.handleMoveField}
              />
            </div>
          )}
        </div>
        <PluginBatchEdit
          fieldList={this.fieldList}
          groupList={this.groupList}
          isShow={this.isShowBatchEdit}
          mode={this.mode}
          selectedGroup={this.selectedGroup}
          typeList={this.typeList}
          unitList={this.unitList}
          onHidden={v => (this.isShowBatchEdit = v)}
          onSave={this.handleSaveBatch}
        />
      </div>
    );
  }
}
