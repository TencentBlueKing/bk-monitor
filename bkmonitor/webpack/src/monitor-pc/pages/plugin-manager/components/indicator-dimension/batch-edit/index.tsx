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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { Debounce, deepClone } from 'monitor-common/utils';

import ColumnCheck from '../../../../performance/column-check/column-check.vue';
import { judgeIsIllegal } from '../../../utils';
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
import { createEmptyField, filterFieldsByGroup, fuzzyMatch } from '../utils';

import './index.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

interface IColumnConfig {
  label: string;
  minWidth?: number;
  renderFn: (props: { $index: number; row: IBatchField }, key?: string) => JSX.Element | string;
  renderHeaderFn?: (config: IColumnConfig & { key: string }) => JSX.Element;
  width?: number;
}

interface IEmits {
  onHidden: (v: boolean) => void;
  onSave: (rows: IBatchField[], deletedUids: string[]) => void;
}

interface IProps {
  fieldList: IFlatField[];
  groupList: IPluginGroup[];
  isShow: boolean;
  mode: MonitorType;
  selectedGroup: ISelectedGroup;
  typeList: { id: string; name: string }[];
  unitList: IUnitItem[];
}

const ALL_OPTION = 'allOption';
const CHECKED_OPTION = 'checkedOption';
const RADIO_OPTIONS = [
  { id: ALL_OPTION, label: window.i18n.tc('全量') },
  { id: CHECKED_OPTION, label: window.i18n.tc('勾选项') },
];
enum CheckboxStatus {
  ALL_CHECKED = 2,
  INDETERMINATE = 1,
  UNCHECKED = 0,
}

const initMap: Partial<IBatchField> = {
  description: '',
  type: '',
  unit: '',
  table_name: '',
  is_active: true,
};

@Component
export default class PluginBatchEdit extends tsc<IProps, IEmits> {
  @Prop({ type: Boolean, default: false }) isShow: IProps['isShow'];
  @Prop({ default: 'metric' }) mode: IProps['mode'];
  @Prop({ default: () => [] }) fieldList: IProps['fieldList'];
  @Prop({ default: () => [] }) groupList: IProps['groupList'];
  @Prop({ default: () => ({ name: ALL_LABEL }) }) selectedGroup: IProps['selectedGroup'];
  @Prop({ default: () => [] }) unitList: IProps['unitList'];
  @Prop({ default: () => [] }) typeList: IProps['typeList'];

  localTable: IBatchField[] = [];
  showTableData: IBatchField[] = [];
  deletedUids: string[] = [];
  search = [];
  keyword = '';
  allCheckValue: 0 | 1 | 2 = CheckboxStatus.UNCHECKED;
  editMode: typeof ALL_OPTION | typeof CHECKED_OPTION = ALL_OPTION;
  currentPopoverKey: string = null;
  batchEdit: Partial<IBatchField> = { ...initMap };
  popoverRef = {};
  popoverChildRef = {};
  triggerElements = {};
  headerPopoverRefs = {};
  saveLoading = false;
  selectPopoverOption = {
    boundary: 'body',
    flipBehavior: ['bottom'],
  };

  get sliderWidth() {
    return this.mode === 'metric' ? Math.max(1000, window.innerWidth * 0.8) : 900;
  }

  get defaultGroupName() {
    if (this.selectedGroup.name && this.selectedGroup.name !== ALL_LABEL) {
      return this.selectedGroup.name;
    }
    return GROUP_DEFAULT_NAME;
  }

  get defaultGroupDesc() {
    const group = this.groupList.find(item => item.table_name === this.defaultGroupName);
    return group?.table_desc || this.defaultGroupName;
  }

  get groupSelectList() {
    return this.groupList.map(item => ({
      id: item.table_name,
      name: item.table_name === GROUP_DEFAULT_NAME ? (this.$t('默认分组') as string) : item.table_name,
    }));
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

  get fieldsSettings(): Record<string, IColumnConfig> {
    const settings: Record<string, IColumnConfig> = {
      name: {
        label: this.$t('名称') as string,
        minWidth: 160,
        renderFn: props => this.renderNameColumn(props),
        renderHeaderFn: this.renderNameHeader,
      },
      description: {
        label: this.$t('别名') as string,
        minWidth: 150,
        renderHeaderFn: row => this.renderPopoverHeader(row),
        renderFn: (props, key) => this.renderInputColumn(props.row, key as 'description'),
      },
      table_name: {
        label: this.$t('分组') as string,
        minWidth: 150,
        renderHeaderFn: row => this.renderPopoverHeader(row),
        renderFn: (props, key) => this.renderGroupColumn(props.row, key),
      },
      type: {
        label: this.$t('类型') as string,
        minWidth: 110,
        renderHeaderFn: this.mode === 'metric' ? row => this.renderPopoverHeader(row) : undefined,
        renderFn: (props, key) => this.renderTypeColumn(props.row, key),
      },
    };
    if (this.mode === 'metric') {
      settings.unit = {
        label: this.$t('单位') as string,
        minWidth: 140,
        renderHeaderFn: row => this.renderPopoverHeader(row),
        renderFn: (props, key) => this.renderUnitColumn(props.row, key),
      };
    }
    settings.is_active = {
      label: this.$t('启/停') as string,
      width: 100,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: (props, key) => this.renderSwitch(props.row, key),
    };
    settings.operate = {
      label: this.$t('操作') as string,
      width: 80,
      renderFn: props => this.renderOperations(props),
    };
    return settings;
  }

  @Watch('isShow')
  handleIsShowChange(val: boolean) {
    if (val) {
      this.initTableData();
    }
  }

  @Emit('hidden')
  handleCancel() {
    this.resetState();
    return false;
  }

  mounted() {
    document.addEventListener('click', this.handleGlobalClick);
  }

  beforeDestroy() {
    document.removeEventListener('click', this.handleGlobalClick);
  }

  resetState() {
    this.deletedUids = [];
    this.search = [];
    this.keyword = '';
    this.allCheckValue = CheckboxStatus.UNCHECKED;
    this.editMode = ALL_OPTION;
    this.currentPopoverKey = null;
    this.batchEdit = { ...initMap };
    this.saveLoading = false;
  }

  initTableData() {
    this.resetState();
    const list = filterFieldsByGroup(this.fieldList, this.selectedGroup.name, this.mode);
    this.localTable = deepClone(list).map((item: IFlatField) => ({
      ...item,
      originUid: item.uid,
      selection: false,
      error: '',
    }));
    this.showTableData = this.localTable.slice();
  }

  matchSearch(item: IBatchField) {
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

  applyFilter() {
    if (this.mode === 'dimension') {
      this.showTableData = this.keyword
        ? this.localTable.filter(
            item => fuzzyMatch(item.name, this.keyword) || fuzzyMatch(item.description, this.keyword)
          )
        : this.localTable.slice();
      return;
    }
    this.showTableData = this.search.length
      ? this.localTable.filter(item => this.matchSearch(item))
      : this.localTable.slice();
  }

  @Debounce(300)
  handleSearchChange(list = []) {
    this.search = list;
    this.applyFilter();
  }

  @Debounce(300)
  handleKeywordChange(val: string) {
    this.keyword = val;
    this.applyFilter();
  }

  handleClearSearch() {
    this.search = [];
    this.keyword = '';
    this.applyFilter();
  }

  updateCheckValue() {
    const checkedLength = this.localTable.filter(item => item.selection).length;
    if (checkedLength > 0) {
      this.allCheckValue =
        checkedLength < this.localTable.length ? CheckboxStatus.INDETERMINATE : CheckboxStatus.ALL_CHECKED;
    } else {
      this.allCheckValue = CheckboxStatus.UNCHECKED;
    }
  }

  handleCheckAllChange({ value }) {
    const checked = value === CheckboxStatus.ALL_CHECKED;
    for (const item of this.localTable) {
      this.$set(item, 'selection', checked);
    }
    this.updateCheckValue();
  }

  handleGlobalClick(event: MouseEvent) {
    if (!this.currentPopoverKey) return;
    const containsEls = [this.triggerElements[this.currentPopoverKey], this.popoverRef[this.currentPopoverKey]];
    const clickInside = containsEls.some(el => el?.contains?.(event.target));
    if (!clickInside) {
      this.cancelBatchEdit();
    }
  }

  togglePopover(key: string) {
    if (this.currentPopoverKey && this.currentPopoverKey !== key) {
      this.cancelBatchEdit();
    }
    this.currentPopoverKey = key;
  }

  hidePopover() {
    this.headerPopoverRefs[this.currentPopoverKey]?.hideHandler?.();
  }

  cancelBatchEdit() {
    this.hidePopover();
    this.editMode = ALL_OPTION;
    if (this.currentPopoverKey) {
      this.batchEdit[this.currentPopoverKey] = initMap[this.currentPopoverKey];
    }
    this.currentPopoverKey = null;
  }

  confirmBatchEdit() {
    const key = this.currentPopoverKey as keyof IBatchField;
    const value = this.batchEdit[key];
    const targets =
      this.editMode === ALL_OPTION ? this.showTableData : this.showTableData.filter(item => item.selection);
    for (const row of targets) {
      this.$set(row, key, value);
      if (key === 'table_name') {
        const group = this.groupList.find(item => item.table_name === value);
        row.table_desc = group?.table_desc || String(value || '');
      }
    }
    this.cancelBatchEdit();
  }

  handleAddRow(index = -1) {
    const newRow = createEmptyField(this.mode, this.defaultGroupName, this.defaultGroupDesc);
    if (index === -1) {
      this.localTable.push(newRow);
      this.showTableData.push(newRow);
      return;
    }
    const currentRow = this.showTableData[index];
    const localIndex = this.localTable.findIndex(item => item === currentRow);
    this.showTableData.splice(index + 1, 0, newRow);
    this.localTable.splice((localIndex > -1 ? localIndex : index) + 1, 0, newRow);
  }

  handleRemoveRow(index: number) {
    const current = this.showTableData[index];
    if (!current) return;
    if (!current.isNew && current.originUid) {
      this.deletedUids.push(current.originUid);
    }
    this.showTableData.splice(index, 1);
    const localIndex = this.localTable.findIndex(item => item === current);
    if (localIndex > -1) {
      this.localTable.splice(localIndex, 1);
    }
    this.updateCheckValue();
  }

  validateName(row: IBatchField) {
    const error = this.validateSync(row);
    this.$set(row, 'error', error);
    return !error;
  }

  validateSync(row: IBatchField): string {
    const name = row.name?.trim() || '';
    if (!name) {
      return this.$t('名称不能为空') as string;
    }
    if (!judgeIsIllegal(name)) {
      return this.$t('输入非中文符号') as string;
    }
    if (this.mode === 'metric') {
      const duplicatedInTable = this.localTable.some(item => item !== row && item.name === name);
      const managedUids = new Set(this.localTable.map(item => item.originUid).filter(Boolean));
      const duplicatedOutside = this.fieldList.some(item => {
        return (
          item.monitor_type === 'metric' &&
          item.name === name &&
          !managedUids.has(item.uid) &&
          !this.deletedUids.includes(item.uid)
        );
      });
      if (duplicatedInTable || duplicatedOutside) {
        return this.$t('名称已存在') as string;
      }
    } else if (this.localTable.some(item => item !== row && item.name === name && item.table_name === row.table_name)) {
      return this.$t('名称已存在') as string;
    }
    return '';
  }

  clearError(row: IBatchField) {
    if (row.error) row.error = '';
  }

  handleSave() {
    const newRows = this.localTable.filter(item => item.isNew);
    const allValid = newRows.map(row => this.validateName(row)).every(Boolean);
    if (!allValid) return;
    this.$emit('save', this.localTable, this.deletedUids);
    this.handleCancel();
  }

  renderNameHeader() {
    return (
      <div class='name-header'>
        <ColumnCheck
          {...{
            props: {
              list: [],
              value: this.allCheckValue,
              defaultType: 'current',
            },
            on: {
              change: this.handleCheckAllChange,
            },
          }}
        />
        <span class='name'>{this.$t('名称')}</span>
      </div>
    );
  }

  renderNameColumn(props: { row: IBatchField }) {
    if (props.row.isNew) {
      return (
        <div class='new-name-col'>
          <bk-checkbox
            v-model={props.row.selection}
            onChange={this.updateCheckValue}
          />
          <div
            class='name-editor'
            v-bk-tooltips={{
              content: props.row.error,
              disabled: !props.row.error,
            }}
          >
            <bk-input
              class={{ 'is-error': props.row.error, 'slider-input': true }}
              placeholder={this.mode === 'metric' ? this.$t('输入指标id') : this.$t('输入维度id')}
              value={props.row.name}
              onBlur={v => {
                props.row.name = v;
                this.validateName(props.row);
              }}
              onInput={() => this.clearError(props.row)}
            />
          </div>
        </div>
      );
    }
    return (
      <div class='name-col'>
        <bk-checkbox
          v-model={props.row.selection}
          onChange={this.updateCheckValue}
        />
        <div
          class='name'
          v-bk-overflow-tips
        >
          {props.row.name || '--'}
        </div>
      </div>
    );
  }

  renderInputColumn(row: IBatchField, field: 'description', refKey = '') {
    return (
      <bk-input
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        class='slider-input'
        v-model={row[field]}
        placeholder={this.$t('输入指标别名')}
      />
    );
  }

  renderGroupColumn(row: IBatchField, refKey = '') {
    return (
      <bk-select
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        class='slider-select'
        clearable={false}
        searchable={true}
        value={row.table_name}
        onChange={(v: string) => {
          row.table_name = v;
          const group = this.groupList.find(item => item.table_name === v);
          row.table_desc = group?.table_desc || v;
        }}
      >
        {this.groupSelectList.map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            name={item.name}
          />
        ))}
      </bk-select>
    );
  }

  renderTypeColumn(row: IBatchField, refKey = '') {
    if (this.mode !== 'metric') {
      return <span>{row.type || '--'}</span>;
    }
    return (
      <bk-select
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        class='slider-select'
        clearable={false}
        value={row.type}
        onChange={(v: string) => {
          row.type = v;
        }}
      >
        {this.typeList.map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            name={item.name}
          />
        ))}
      </bk-select>
    );
  }

  renderUnitColumn(row: Partial<IBatchField>, refKey = '') {
    return (
      <bk-select
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        class='slider-select'
        clearable={false}
        popover-options={this.selectPopoverOption}
        popover-width={180}
        searchable={true}
        value={row.unit}
        onChange={(v: string) => {
          row.unit = v;
        }}
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
    );
  }

  renderSwitch(row: Partial<IBatchField>, refKey = '') {
    return (
      <div class='switch-wrap'>
        <bk-switcher
          ref={
            refKey
              ? el => {
                  this.popoverChildRef[refKey] = el;
                }
              : ''
          }
          size='small'
          theme='primary'
          value={row.is_active}
          onChange={(v: boolean) => {
            row.is_active = v;
          }}
        />
      </div>
    );
  }

  renderOperations(props: { $index: number }) {
    return (
      <div class='operations'>
        <i
          class='bk-icon icon-plus-circle-shape'
          onClick={() => this.handleAddRow(props.$index)}
        />
        <i
          class='bk-icon icon-minus-circle-shape'
          onClick={() => this.handleRemoveRow(props.$index)}
        />
      </div>
    );
  }

  renderPopoverLabel({ label }: { key: string; label: string }) {
    return (
      <span>
        {this.$t(label)} <i class='icon-monitor icon-mc-wholesale-editor' />
      </span>
    );
  }

  renderPopoverSlot(type: string) {
    const popoverMap = {
      description: () => this.renderInputColumn(this.batchEdit as IBatchField, 'description', type),
      table_name: () => this.renderGroupColumn(this.batchEdit as IBatchField, type),
      type: () => this.renderTypeColumn(this.batchEdit as IBatchField, type),
      unit: () => this.renderUnitColumn(this.batchEdit, type),
      is_active: () => this.renderSwitch(this.batchEdit, type),
    };
    return (
      <div
        ref={el => {
          this.popoverRef[type] = el;
        }}
        slot='content'
      >
        <div class='unit-config-header'>
          <div class='unit-range'>{this.$t('编辑范围')}</div>
          <bk-radio-group
            class='unit-radio'
            v-model={this.editMode}
          >
            {RADIO_OPTIONS.map(opt => (
              <bk-radio
                key={opt.id}
                disabled={opt.id === CHECKED_OPTION && this.allCheckValue === CheckboxStatus.UNCHECKED}
                value={opt.id}
              >
                {opt.label}
              </bk-radio>
            ))}
          </bk-radio-group>
        </div>
        <div class='unit-selection'>
          <div class='unit-title'>{this.$t(this.fieldsSettings[type].label)}</div>
          {popoverMap[type]?.()}
        </div>
        <div class='unit-config-footer'>
          <bk-button
            theme='primary'
            onClick={this.confirmBatchEdit}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button onClick={this.cancelBatchEdit}>{this.$t('取消')}</bk-button>
        </div>
      </div>
    );
  }

  renderPopoverHeader(row: IColumnConfig & { key: string }) {
    return (
      <div
        ref={el => {
          this.triggerElements[row.key] = el;
        }}
        class='header-trigger'
        onClick={() => this.togglePopover(row.key)}
      >
        <bk-popover
          ref={el => {
            this.headerPopoverRefs[row.key] = el;
          }}
          width='304'
          ext-cls='metric-table-header'
          tippy-options={{
            trigger: 'click',
            hideOnClick: false,
          }}
          animation='slide-toggle'
          arrow={false}
          boundary='viewport'
          offset={'-15, 4'}
          placement='bottom-start'
          theme='light common-monitor'
        >
          {this.renderPopoverLabel(row)}
          {this.renderPopoverSlot(row.key)}
        </bk-popover>
      </div>
    );
  }

  renderEmpty() {
    const hasSearch = this.mode === 'metric' ? !!this.search.length : !!this.keyword;
    return (
      <div class='empty-slider-table'>
        <div class='empty-img'>
          <bk-exception
            class='exception-wrap-item exception-part'
            scene='part'
            type='empty'
          >
            <span class='empty-text'>{this.$t('暂无数据')}</span>
          </bk-exception>
        </div>
        {hasSearch ? (
          <div
            class='add-row'
            onClick={this.handleClearSearch}
          >
            {this.$t('清空检索')}
          </div>
        ) : (
          <div
            class='add-row'
            onClick={() => this.handleAddRow(-1)}
          >
            {this.mode === 'metric' ? this.$t('新增指标') : this.$t('新增维度')}
          </div>
        )}
      </div>
    );
  }

  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={this.sliderWidth}
        ext-cls='plugin-batch-edit-slider'
        isShow={this.isShow}
        quickClose
        onHidden={this.handleCancel}
      >
        <div
          class='sideslider-title'
          slot='header'
        >
          {this.mode === 'metric' ? this.$t('批量编辑指标') : this.$t('批量编辑维度')}
        </div>
        <div
          class='plugin-batch-edit-content'
          slot='content'
        >
          <div class='slider-search'>
            {this.mode === 'metric' ? (
              <SearchSelect
                data={this.metricSearchData}
                modelValue={this.search}
                placeholder={this.$t('搜索 名称、别名、单位、类型、启/停')}
                show-popover-tag-change
                on-change={this.handleSearchChange}
              />
            ) : (
              <bk-input
                placeholder={this.$t('搜索 名称、别名')}
                right-icon='bk-icon icon-search'
                value={this.keyword}
                clearable
                onChange={this.handleKeywordChange}
              />
            )}
          </div>
          <div class='slider-table'>
            <bk-table
              data={this.showTableData}
              empty-text={this.$t('无数据')}
              max-height={window.innerHeight - 240}
              colBorder
            >
              <div slot='empty'>{this.renderEmpty()}</div>
              {Object.entries(this.fieldsSettings).map(([key, config]) => (
                <bk-table-column
                  key={key}
                  width={config.width}
                  scopedSlots={{
                    default: props => (config.renderFn ? config.renderFn(props, key) : props.row[key] || '--'),
                  }}
                  label={this.$t(config.label)}
                  minWidth={config.minWidth}
                  prop={key}
                  renderHeader={config.renderHeaderFn ? () => config.renderHeaderFn({ ...config, key }) : undefined}
                />
              ))}
            </bk-table>
          </div>
          <div class='slider-footer'>
            <bk-button
              loading={this.saveLoading}
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
