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

import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { validateCustomTsGroupLabel } from 'monitor-api/modules/custom_report';
import { Debounce, deepClone } from 'monitor-common/utils';

import ColumnCheck from '../../performance/column-check/column-check.vue';
import {
  type DimensionHeaderKeys,
  type IColumnConfig,
  type IDimensionItem,
  type PopoverChildRef,
  ALL_OPTION,
  CheckboxStatus,
  CHECKED_OPTION,
  RADIO_OPTIONS,
} from './type';
import { fuzzyMatch } from './utils';

import './dimension-table-slide.scss';

const initMap = {
  disabled: false,
  hidden: false,
  common: false,
};
@Component
export default class DimensionTableSlide extends tsc<any> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ default: () => [] }) dimensionTable: any[];

  /** 表格配置 */
  fieldsSettings: Record<string, IColumnConfig> = {
    name: {
      label: '名称',
      width: 175,
      renderFn: props => this.renderNameColumn(props),
      type: 'selection',
      renderHeaderFn: this.renderNameHeader,
    },
    description: { label: '别名', width: 175, renderFn: (props, key) => this.renderInputColumn(props, key) },
    // disabled: { label: '启/停', width: 120, renderFn: (props, key) => this.renderSwitch(props.row, key) },
    common: {
      label: '常用维度',
      width: 140,
      renderFn: (props, key) => this.renderCheckbox(props.row, key),
      renderHeaderFn: row => this.renderPopoverHeader(row),
    },
    hidden: {
      label: '显示',
      width: 120,
      renderFn: (props, key) => this.renderSwitch(props.row, key, true),
      renderHeaderFn: row => this.renderPopoverHeader(row),
    },
    operate: { label: '操作', width: 80, renderFn: props => this.renderOperations(props) },
  };
  /** 维度搜索 */
  search = '';
  /** 表格数据 */
  localTable: IDimensionItem[] = [];
  /** 删除的维度名称列表 */
  delArray: IDimensionItem[] = [];
  /** 全选标志位 */
  allCheckValue: 0 | 1 | 2 = CheckboxStatus.UNCHECKED;
  /** 当前的 Popover Key 值 */
  currentPopoverKey: DimensionHeaderKeys = null;
  /** Ref 实例 */
  popoverRef = [];
  popoverChildRef: PopoverChildRef[] = [];
  triggerElements = [];
  /** 批量编辑 */
  batchEdit: any = {
    unit: '',
    aggregate_method: '',
    interval: 10,
    function: [],
    dimensions: [],
    hidden: false,
    disabled: false,
  };
  /** 编辑模式：全量 | 勾选项 */
  editModo: typeof ALL_OPTION | typeof CHECKED_OPTION = ALL_OPTION;

  /** 抽屉宽度 */
  get width() {
    return window.innerWidth * 0.75;
  }

  get refMap() {
    switch (this.currentPopoverKey) {
      case 'common':
        return '';
      default:
        return '';
    }
  }

  // 响应式处理
  @Watch('dimensionTable', { immediate: true, deep: true })
  handleDimensionTableChange(newVal: IDimensionItem[]) {
    this.localTable = deepClone(newVal);
    this.localTable.map(row => this.$set(row, 'selection', false));
  }

  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={this.width}
        ext-cls='dimension-slider-box'
        isShow={this.isShow}
        quickClose
        onHidden={this.handleCancel}
      >
        <div
          class='sideslider-title'
          slot='header'
        >
          {this.$t('批量编辑维度')}
        </div>
        <div
          class='dimension-slider-content'
          slot='content'
        >
          <div class='slider-search'>
            <bk-input
              v-model={this.search}
              placeholder={this.$t('搜索维度')}
              right-icon='bk-icon icon-search'
              on-change={this.handleSearchChange}
            />
          </div>
          {/* 头部和搜索 */}
          <bk-table
            class='slider-table'
            data={this.localTable}
            colBorder
          >
            <div slot='empty'>
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
                {this.search ? (
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
                    {this.$t('新增维度')}
                  </div>
                )}
              </div>
            </div>
            {Object.entries(this.fieldsSettings).map(([key, config]) => {
              const hasRenderHeader = 'renderHeaderFn' in config;

              return (
                <bk-table-column
                  key={key}
                  width={config.width}
                  scopedSlots={{
                    default: props => {
                      /** 自定义 */
                      if (config?.renderFn) {
                        return config?.renderFn(props, key);
                      }
                      return props.row[key] || '--';
                    },
                  }}
                  label={this.$t(config.label)}
                  prop={key}
                  renderHeader={hasRenderHeader ? () => config.renderHeaderFn({ ...config, key }) : undefined}
                  type={config.type || ''}
                />
              );
            })}
          </bk-table>
          <div class='slider-footer'>
            <bk-button
              // disabled={!this.localTable.length}
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

  @Emit('hidden')
  handleCancel() {
    this.delArray = [];
    this.localTable = deepClone(this.dimensionTable);
    this.localTable.map(row => (row.selection = false));
    this.search = '';
    this.allCheckValue = CheckboxStatus.UNCHECKED;
    return false;
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  @Debounce(300)
  handleSearchChange() {
    this.localTable = this.dimensionTable.filter(item => {
      return fuzzyMatch(item.name, this.search) || fuzzyMatch(item.description, this.search);
    });
  }

  handleClearSearch() {
    this.search = '';
  }

  changeSwitch(row, field, v) {
    row[field] = v;
  }

  // 保存逻辑
  async handleSave() {
    const newRows = this.localTable.filter(row => row.isNew);

    // 并行执行所有验证
    const validationResults = await Promise.all(
      newRows.map(async row => {
        const isValid = await this.validateName(row);
        if (!isValid) {
          // TODO: 错误反馈
          // this.$bkMessage({ message: row.error, theme: 'error' });
        }
        return isValid;
      })
    );

    // 检查全局有效性
    const allValid = validationResults.every(valid => valid);
    if (!allValid) return;

    // 清除临时状态
    for (const row of newRows) {
      row.isNew = undefined;
      row.error = undefined;
    }
    // 提交
    this.$emit('saveInfo', this.localTable, this.delArray);
  }

  // 渲染输入列
  renderInputColumn(props: { $index: number; row: IDimensionItem }, field: string) {
    return (
      <bk-input
        class='slider-input'
        v-model={props.row[field]}
      />
    );
  }

  hidePopover() {
    const popoverRef = this.popoverChildRef[this.currentPopoverKey]?.$parent;
    popoverRef?.hideHandler();
  }

  mounted() {
    document.addEventListener('click', this.handleGlobalClick);
  }

  beforeDestroy() {
    document.removeEventListener('click', this.handleGlobalClick);
  }
  handleGlobalClick(event) {
    if (!this.currentPopoverKey) return;

    const containsEls = [];
    // 获取对应的触发元素
    containsEls.push(this.triggerElements[this.currentPopoverKey]);
    // 获取当前 Popover 元素
    containsEls.push(this.popoverRef[this.currentPopoverKey]);
    this.refMap && containsEls.push(this.refMap);
    // 边缘情况处理

    // 检查点击区域
    const clickInside = containsEls.some(el => el?.contains(event.target));
    if (!clickInside) {
      this.cancelBatchEdit();
    }
  }

  togglePopover(key) {
    if (this.currentPopoverKey && this.currentPopoverKey !== key) {
      this.cancelBatchEdit();
    }
    this.currentPopoverKey = key;
  }

  cancelBatchEdit() {
    this.hidePopover();
    this.editModo = ALL_OPTION;
    this.batchEdit[this.currentPopoverKey] = initMap[this.currentPopoverKey];
    this.currentPopoverKey = null;
  }

  handleRowCheck() {
    this.updateCheckValue();
  }
  handleCheckChange({ value }) {
    const v = value === CheckboxStatus.ALL_CHECKED;
    this.localTable.forEach(item => {
      item.selection = v;
    });
    this.updateCheckValue();
  }
  updateCheckValue() {
    const checkedLength = this.localTable.filter(item => item.selection).length;
    const allLength = this.localTable.length;
    if (checkedLength > 0) {
      this.allCheckValue = checkedLength < allLength ? CheckboxStatus.INDETERMINATE : CheckboxStatus.ALL_CHECKED;
    } else {
      this.allCheckValue = CheckboxStatus.UNCHECKED;
    }
  }

  renderNameHeader() {
    return (
      <div class='name-header'>
        <ColumnCheck
          {...{
            props: {
              list: this.localTable,
              value: this.allCheckValue,
              defaultType: 'current',
            },
            on: {
              change: this.handleCheckChange,
            },
          }}
        />
        <span class='name'>{this.$t('名称')}</span>
      </div>
    );
  }
  getPopoverContent(type) {
    switch (type) {
      case 'hidden':
        return this.$t('关闭后，在可视化视图里，将被隐藏');
      default:
        return '';
    }
  }

  // Label 内容
  renderPopoverLabel({ label, key: type }) {
    const popoverContent = this.getPopoverContent(type);
    if (popoverContent) {
      return (
        <bk-popover ext-cls='slider-header-hidden-popover'>
          <span class='has-popover'>{this.$t(label)}</span> <i class='icon-monitor icon-mc-wholesale-editor' />
          <div slot='content'>{popoverContent}</div>
        </bk-popover>
      );
    }
    return (
      <span>
        {this.$t(label)} <i class='icon-monitor icon-mc-wholesale-editor' />
      </span>
    );
  }
  // 弹窗内容
  renderPopoverSlot(type) {
    const popoverMap = {
      disabled: () => this.renderSwitch(this.batchEdit, type, type),
      hidden: () => this.renderSwitch(this.batchEdit, type, true, type),
      common: () => this.renderCheckbox(this.batchEdit, type, type),
    };
    return (
      <div
        ref={el => (this.popoverRef[type] = el)}
        slot='content'
      >
        <div class='unit-config-header'>
          <div class='unit-range'>{this.$t('编辑范围')}</div>
          <bk-radio-group
            class='unit-radio'
            v-model={this.editModo}
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
          {popoverMap[type]?.(type)}
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

  confirmBatchEdit() {
    if (this.editModo === ALL_OPTION) {
      this.localTable.map((row: IDimensionItem) => {
        row[this.currentPopoverKey as any] = this.batchEdit[this.currentPopoverKey];
      });
    } else {
      this.localTable
        .filter(row => row.selection)
        .map(row => {
          row[this.currentPopoverKey as any] = this.batchEdit[this.currentPopoverKey];
        });
    }
    this.cancelBatchEdit();
  }

  renderPopoverHeader(row) {
    return (
      <div
        ref={el => (this.triggerElements[row.key] = el)}
        class='header-trigger'
        onClick={() => this.togglePopover(row.key)}
      >
        <bk-popover
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

  renderNameColumn(props: { row: IDimensionItem }) {
    if (props.row.isNew) {
      return (
        <div class='new-name-col'>
          <bk-checkbox
            v-model={props.row.selection}
            onChange={this.handleRowCheck}
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
          onChange={this.handleRowCheck}
        />
        <span class='name'>{props.row.name || '--'}</span>
      </div>
    );
  }

  // 渲染开关
  renderSwitch(row: IDimensionItem, field: 'disabled' | 'hidden', isNegation = false, refKey = '') {
    return (
      <bk-switcher
        ref={refKey ? el => (this.popoverChildRef[refKey] = el) : ''}
        size='small'
        theme='primary'
        value={isNegation ? !row[field] : row[field]}
        onChange={v => this.changeSwitch(row, field, isNegation ? !v : v)}
      />
    );
  }
  // 渲染checkbox
  renderCheckbox(row: IDimensionItem, field: 'common', refKey = '') {
    return (
      <bk-checkbox
        ref={refKey ? el => (this.popoverChildRef[refKey] = el) : ''}
        v-model={row[field]}
        false-value={false}
        true-value={true}
      />
    );
  }

  // 操作列
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

  async validateName(row): Promise<boolean> {
    // 同步验证
    const syncError = this.validateSync(row);
    if (syncError) {
      this.$set(row, 'error', syncError);
      return false;
    }
    // 异步验证
    const asyncError = await this.validateAsync(row);
    if (asyncError) {
      this.$set(row, 'error', asyncError);
      return false;
    }

    row.error = '';
    return true;
  }

  // 同步验证逻辑
  validateSync(row): string {
    if (!row.name?.trim()) {
      return this.$t('名称不能为空') as string;
    }
    if (this.localTable.some(item => item !== row && item.name === row.name)) {
      return this.$t('名称已存在') as string;
    }
    if (/[\u4e00-\u9fa5]/.test(row.name.trim())) {
      return this.$t('输入非中文符号') as string;
    }
    return '';
  }

  // 异步验证逻辑
  async validateAsync(row): Promise<string> {
    try {
      const isValid = await validateCustomTsGroupLabel({ data_label: row.name });
      return isValid ? '' : (this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string);
    } catch {
      return this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string;
    }
  }

  clearError(row) {
    if (row.error) row.error = '';
  }

  // 添加/删除行逻辑
  handleAddRow(index: number) {
    this.localTable.splice(index + 1, 0, {
      name: '',
      description: '',
      disabled: false,
      common: false,
      isNew: true,
      selection: false,
    });
  }

  handleRemoveRow(index: number) {
    const item = this.localTable[index];
    if (!item.isNew) {
      this.delArray.push({
        type: 'dimension',
        name: item.name,
      });
    }
    this.localTable.splice(index, 1);
  }
}
