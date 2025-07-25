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

import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { validateCustomTsGroupLabel } from 'monitor-api/modules/custom_report';
import { Debounce, deepClone } from 'monitor-common/utils';
import CycleInput from 'monitor-pc/components/cycle-input/cycle-input';

import { METHOD_LIST } from '../../../constant/constant';
import ColumnCheck from '../../performance/column-check/column-check.vue';
import FunctionSelect from '../../strategy-config/strategy-config-set-new/monitor-data/function-select';
import { statusMap } from './type';
import {
  type IColumnConfig,
  type IMetricItem,
  type MetricHeaderKeys,
  type PopoverChildRef,
  ALL_OPTION,
  CheckboxStatus,
  CHECKED_OPTION,
  RADIO_OPTIONS,
} from './type';
import { fuzzyMatch } from './utils';

import './metric-table-slide.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

// 常量定义

// 默认分页大小
const DEFAULT_PAGE_SIZE = 20;
// 默认单元格高度
const DEFAULT_CELL_HEIGHT = 40;
// 加载延迟时间(ms)
const LOAD_DELAY = 300;

const initMap = {
  unit: '',
  aggregate_method: '',
  interval: 10,
  function: [],
  dimensions: [],
  disabled: false,
  hidden: false,
};

@Component
export default class IndicatorTableSlide extends tsc<any> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: Boolean, default: false }) autoDiscover: boolean;
  @Prop({ default: () => [] }) metricTable: IMetricItem[];
  @Prop({ default: () => [] }) unitList: any[];
  @Prop({ default: () => [] }) dimensionTable: any[];
  @Prop({ default: () => [] }) cycleOption: any[];

  @InjectReactive('metricFunctions') metricFunctions;

  localTable: IMetricItem[] = [];
  units: any[] = [];

  currentPage = 1;
  pageSize = DEFAULT_PAGE_SIZE;
  cellHeight = DEFAULT_CELL_HEIGHT;
  totalPages = 0;
  showTableData: IMetricItem[] = [];
  bottomLoadingOptions = {
    size: 'small',
    isLoading: false,
  };

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
  /** 表格搜索 */
  search = [];
  /* 筛选条件(简化) */
  metricSearchObj = {
    name: [],
    description: [],
    unit: [],
    func: [],
    aggregate: [],
    show: [],
  };
  /** 删除的行name列表 */
  delArray: Array<{ name: string; type: string }> = [];

  fieldsSettings: Record<string, IColumnConfig> = {
    name: {
      label: '名称',
      width: 175,
      renderFn: props => this.renderNameColumn(props),
      type: 'selection',
      renderHeaderFn: this.renderNameHeader,
    },
    description: {
      label: '别名',
      width: 175,
      renderFn: props => this.renderDescriptionColumn(props),
    },
    unit: {
      label: '单位',
      width: 125,
      renderFn: props => this.renderUnitColumn(props),
      renderHeaderFn: row => this.renderPopoverHeader(row),
    },
    aggregate_method: {
      label: '汇聚方法',
      width: 125,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderAggregateMethod(props.row),
    },
    interval: {
      label: '上报周期',
      width: 145,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderInterval(props.row),
    },
    function: {
      label: '函数',
      width: 145,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderFunction(props.row),
    },
    dimensions: {
      label: '关联维度',
      width: 215,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderDimension(props.row, props.$index),
    },
    // disabled: {
    //   label: '启/停',
    //   width: 80,
    //   renderHeaderFn: row => this.renderPopoverHeader(row),
    //   renderFn: (props, key) => this.renderSwitch(props.row, key as 'disabled' | 'hidden'),
    // },
    hidden: {
      label: '显示',
      width: 80,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: (props, key) => this.renderSwitch(props.row, key as 'disabled' | 'hidden'),
    },
    operate: {
      label: '操作',
      width: 50,
      renderFn: props => this.renderOperations(props),
    },
  };
  currentPopoverKey: MetricHeaderKeys = null;
  triggerElements = [];
  popoverRef = [];
  popoverChildRef: PopoverChildRef[] = [];

  /** 全选标志位 */
  allCheckValue: 0 | 1 | 2 = CheckboxStatus.UNCHECKED;
  searchKey = '';

  /** 抽屉宽度 */
  get width() {
    return window.innerWidth * 0.75;
  }

  get dimensions() {
    const newDimension = this.searchKey ? [{ id: this.searchKey, name: this.searchKey, isNew: true }] : [];
    return newDimension.concat(this.dimensionTable.map(({ name }) => ({ id: name, name, isNew: false })));
  }

  get metricSearchData() {
    return [
      {
        name: window.i18n.t('名称'),
        id: 'name',
        multiple: false,
        children: [],
      },
      {
        name: window.i18n.t('别名'),
        id: 'description',
        multiple: false,
        children: [],
      },
      {
        name: window.i18n.t('单位'),
        id: 'unit',
        multiple: false,
        children: this.units,
      },
      {
        name: window.i18n.t('汇聚方法'),
        id: 'aggregate',
        multiple: false,
        children: METHOD_LIST,
      },
      {
        name: window.i18n.t('显/隐'),
        id: 'show',
        multiple: false,
        children: [
          { id: 'true', name: window.i18n.t('显示') },
          { id: 'false', name: window.i18n.t('隐藏') },
        ],
      },
    ];
  }

  get refMap() {
    switch (this.currentPopoverKey) {
      case 'unit':
      case 'aggregate_method':
        return this.popoverChildRef[this.currentPopoverKey]?.$refs?.selectDropdown?.$refs?.html;
      case 'interval':
        return this.popoverChildRef[this.currentPopoverKey]?.$refs?.cyclePopover?.$refs?.html;
      case 'function':
        return this.popoverChildRef[this.currentPopoverKey]?.$children?.[0]?.$refs?.menuPanel;
      case 'dimensions':
        return this.popoverChildRef[this.currentPopoverKey]?.$refs?.selectorList;
      default:
        return '';
    }
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  @Debounce(LOAD_DELAY)
  handleSearchChange(list = []) {
    this.search = list;
    const search = {
      name: [],
      description: [],
      unit: [],
      func: [],
      aggregate: [],
      show: [],
    };

    for (const item of this.search) {
      if (item.type === 'text') {
        item.id = 'name';
        item.values = [{ id: item.name, name: item.name }];
      }
      if (item.id === 'unit') {
        for (const v of item.values) {
          v.id = v.name;
        }
      }
      search[item.id] = [...new Set(search[item.id].concat(item.values.map(v => v.id)))];
    }

    this.metricSearchObj = search;
    this.handleFilterTable();
  }

  handleFilterTable() {
    const { name, description, unit, aggregate, show } = this.metricSearchObj;
    const nameLength = name.length;
    const descriptionLength = description.length;
    const unitLength = unit.length;
    const aggregateLength = aggregate.length;
    const isShowLength = show.length;

    this.localTable = this.metricTable.filter(item => {
      return (
        (nameLength ? name.some(n => fuzzyMatch(item.name, n)) : true) &&
        (descriptionLength ? description.some(n => fuzzyMatch(item.description, n)) : true) &&
        (unitLength ? unit.some(u => fuzzyMatch(item.unit || 'none', u)) : true) &&
        (aggregateLength ? aggregate.some(a => fuzzyMatch(item.aggregate_method || 'none', a)) : true) &&
        (isShowLength ? show.some(s => s === String(!item.hidden)) : true)
      );
    });

    this.initTableData();
  }

  // 事件处理
  async handleSave() {
    const newRows = this.showTableData.filter(row => row.isNew);

    // 并行执行所有验证
    const validationResults = await Promise.all(
      newRows.map(async row => {
        return await this.validateName(row);
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

  @Emit('hidden')
  handleCancel() {
    this.delArray = [];
    this.localTable = deepClone(this.metricTable);
    this.localTable.map(row => (row.selection = false));
    this.initTableData();
    this.search = [];
    this.allCheckValue = CheckboxStatus.UNCHECKED;
    return false;
  }

  // 响应式处理
  @Watch('metricTable', { deep: true, immediate: true })
  handleMetricTableChange(newVal: IMetricItem[]) {
    this.localTable = deepClone(newVal);
    this.localTable.map(row => (row.selection = false));
    this.initTableData();
  }

  @Watch('unitList', { immediate: true })
  handleUnitListChange(newVal: any[]) {
    this.units = newVal;
  }

  @Watch('isShow')
  handleIsShowChange(val) {
    if (val) {
      this.$nextTick(() => {
        const height = window.innerHeight - 160;
        this.pageSize = Math.floor(height / this.cellHeight);
        this.initTableData();
      });
    }
  }

  initTableData() {
    this.showTableData = [];
    this.currentPage = 1;
    this.totalPages = Math.ceil(this.localTable.length / this.pageSize);
    this.showTableData = this.localTable.slice(0, this.pageSize);
  }

  /** 滚动加载更多 */
  handleScrollToBottom() {
    if (this.currentPage < this.totalPages) {
      this.bottomLoadingOptions.isLoading = true;
      setTimeout(() => {
        const startIndex = this.showTableData.length;
        const endIndex = startIndex + this.pageSize;
        const newData = this.localTable.slice(startIndex, endIndex);
        this.showTableData = [...this.showTableData, ...newData];
        this.currentPage++;
        this.bottomLoadingOptions.isLoading = false;
      }, LOAD_DELAY);
    }
  }

  // 主渲染逻辑
  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={this.width}
        ext-cls='metric-slider-box'
        isShow={this.isShow}
        quickClose
        onHidden={this.handleCancel}
      >
        <div
          class='sideslider-title'
          slot='header'
        >
          {this.$t('批量编辑指标')}
        </div>

        <div
          class='metric-slider-content'
          slot='content'
        >
          <div class='slider-search'>
            <SearchSelect
              data={this.metricSearchData}
              modelValue={this.search}
              placeholder={this.$t('搜索指标')}
              show-popover-tag-change
              on-change={this.handleSearchChange}
            />
          </div>
          <div class='slider-table'>
            <bk-table
              data={this.showTableData}
              empty-text={this.$t('无数据')}
              max-height={window.innerHeight - 240}
              scroll-loading={this.bottomLoadingOptions}
              colBorder
              on-scroll-end={this.handleScrollToBottom}
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
                  {this.search.length ? (
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
                      {this.$t('新增指标')}
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
                        if (config.renderFn) {
                          return config.renderFn(props, key);
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
          </div>

          <div class='slider-footer'>
            <bk-button
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

  handleClearSearch() {
    this.search = [];
    this.handleSearchChange();
  }

  // 渲染辅助方法
  renderStatusPoint(row: IMetricItem) {
    const status = statusMap.get(!!row.disabled);
    return (
      <div
        style={{ background: status.color2 }}
        class='status-point'
      >
        <div
          style={{ background: status.color1 }}
          class='point'
        />
        <span class='status-text'>{status.name}</span>
      </div>
    );
  }

  renderSwitch(row: IMetricItem, field: 'disabled' | 'hidden', refKey = '') {
    return (
      <div class='switch-wrap'>
        <bk-switcher
          ref={refKey ? el => (this.popoverChildRef[refKey] = el) : ''}
          disabled={this.autoDiscover && field === 'disabled'}
          size='small'
          theme='primary'
          value={!row[field]}
          onChange={v => (row[field] = !v)}
        />
      </div>
    );
  }
  handleRowCheck() {
    this.updateCheckValue();
  }
  // 表格列渲染逻辑
  renderNameColumn(props: { row: IMetricItem }) {
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

  renderDescriptionColumn(props: { $index: number; row: IMetricItem }) {
    return (
      <bk-input
        class='slider-input'
        v-model={props.row.description}
      />
    );
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
    if (this.currentPopoverKey === 'interval') {
      containsEls.push(this.popoverChildRef[this.currentPopoverKey]?.$refs?.unitList);
    }
    if (this.currentPopoverKey === 'dimensions') {
      containsEls.push(event.target.closest('.bk-selector-list'));
    }
    if (this.currentPopoverKey === 'function') {
      containsEls.push(this.popoverChildRef[this.currentPopoverKey]?.$children?.[0]?.$el);
      containsEls.push(event.target.closest('.select-panel'));
      containsEls.push(event.target.closest('.func-item'));
      containsEls.push(event.target.closest('.function-menu-panel'));
    }
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

  handleCheckChange({ value }) {
    const v = value === CheckboxStatus.ALL_CHECKED;
    this.localTable.forEach(item => (item.selection = v));
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
          disabled={row.key === 'dimensions' && this.autoDiscover}
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

  renderUnitColumn(props: { row: IMetricItem }, refKey = '') {
    return (
      <bk-select
        ref={refKey ? el => (this.popoverChildRef[refKey] = el) : ''}
        class='slider-select'
        v-model={props.row.unit}
        clearable={false}
        placeholder={`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}
        popover-width={180}
        allow-create
        searchable
      >
        {this.units.map(group => (
          <bk-option-group
            key={group.id}
            name={group.name}
          >
            {group.formats.map(opt => (
              <bk-option
                id={opt.id}
                key={opt.id}
                name={opt.name}
              />
            ))}
          </bk-option-group>
        ))}
      </bk-select>
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
      unit: () => this.renderUnitColumn({ row: this.batchEdit }, type),
      aggregate_method: () => this.renderAggregateMethod(this.batchEdit, type),
      interval: () => this.renderInterval(this.batchEdit, type),
      function: () => this.renderFunction(this.batchEdit, type),
      dimensions: () => this.renderDimension(this.batchEdit, 0, type),
      disabled: () => this.renderSwitch(this.batchEdit, type, type),
      hidden: () => this.renderSwitch(this.batchEdit, type, type),
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
      this.localTable.map((row: IMetricItem) => {
        row[this.currentPopoverKey as any] = this.batchEdit[this.currentPopoverKey];
      });
    } else {
      this.showTableData
        .filter(row => row.selection)
        .map(row => {
          row[this.currentPopoverKey as any] = this.batchEdit[this.currentPopoverKey];
        });
    }
    this.cancelBatchEdit();
  }

  hidePopover() {
    const popoverRef = this.popoverChildRef[this.currentPopoverKey]?.$parent;
    popoverRef?.hideHandler();
  }

  cancelBatchEdit() {
    this.hidePopover();
    this.editModo = ALL_OPTION;
    this.batchEdit[this.currentPopoverKey] = initMap[this.currentPopoverKey];
    this.currentPopoverKey = null;
  }

  // 其他渲染方法
  renderAggregateMethod(row: IMetricItem, refKey = '') {
    return (
      <bk-select
        ref={refKey ? el => (this.popoverChildRef[refKey] = el) : ''}
        class='slider-select'
        v-model={row.aggregate_method}
        clearable={false}
      >
        {METHOD_LIST.map(m => (
          <bk-option
            id={m.id}
            key={m.id}
            name={m.name}
          />
        ))}
      </bk-select>
    );
  }

  /** 修改上报周期 */
  handleIntervalChange(v: number, row: IMetricItem) {
    row.interval = v;
  }

  renderInterval(row: IMetricItem, refKey = '') {
    return (
      <CycleInput
        ref={refKey ? el => (this.popoverChildRef[refKey] = el) : ''}
        class='slide-cycle-unit-input'
        isNeedDefaultVal={true}
        minSec={10}
        needAuto={false}
        value={row.interval}
        onChange={(v: number) => this.handleIntervalChange(v, row)}
      />
    );
  }

  renderMerberList(node, ctx, highlightKeyword) {
    const parentClass = 'bk-selector-node bk-selector-member';
    const textClass = 'text';
    const innerHtml = highlightKeyword(node.name);
    return (
      <div class={parentClass}>
        <span
          class={textClass}
          domPropsInnerHTML={node.isNew ? `${this.$t('新增 "{0}" 维度', [innerHtml])}` : innerHtml}
        />
      </div>
    );
  }

  renderDimension(row: IMetricItem, index, refKey = '') {
    return (
      <div
        style={index < 5 ? 'top: 0;' : ''}
        class='dimension-input'
      >
        <bk-tag-input
          ref={refKey ? el => el && (this.popoverChildRef[refKey] = el) : ''}
          v-model={row.dimensions}
          v-bk-tooltips={{
            disabled: !this.autoDiscover,
            content: this.$t('已开启自动发现新增指标，无法操作'),
          }}
          filterCallback={(filterVal, filterKey, data) => {
            const isPrecise = this.dimensions.find((item, index) => index !== 0 && item[filterKey] === filterVal);
            return data.filter((item, index) => {
              if (index === 0 && isPrecise) {
                return false;
              }
              return fuzzyMatch(item[filterKey], filterVal);
            });
          }}
          clearable={false}
          disabled={this.autoDiscover}
          list={this.dimensions}
          placeholder={`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}
          tpl={this.renderMerberList}
          trigger='focus'
          allowCreate
          onBlur={() => {
            this.searchKey = '';
          }}
          onInputchange={v => {
            this.searchKey = v.trim();
          }}
          {...{
            props: {
              'has-delete-icon': true,
              'fix-height': true,
              'collapse-tags': true,
            },
          }}
        />
      </div>
    );
  }

  handleFunctionsChange(params, row) {
    row.function = params;
  }

  renderFunction(row: IMetricItem, refKey = '') {
    const getKey = obj => {
      return `${obj?.id || ''}_${obj?.params[0]?.value || ''}`;
    };
    return (
      <FunctionSelect
        key={getKey(row.function?.[0])}
        ref={refKey ? el => el && (this.popoverChildRef[refKey] = el) : ''}
        class='metric-func-selector'
        v-model={row.function}
        isMultiple={false}
        onValueChange={params => this.handleFunctionsChange(params, row)}
      />
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

  async validateName(row: IMetricItem): Promise<boolean> {
    // 同步验证
    const syncError = this.validateSync(row);
    if (syncError) {
      row.error = syncError;
      return false;
    }
    // 异步验证
    const asyncError = await this.validateAsync(row);
    if (asyncError) {
      row.error = asyncError;
      return false;
    }

    row.error = '';
    return true;
  }

  // 同步验证逻辑
  validateSync(row: IMetricItem): string {
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
  async validateAsync(row: IMetricItem): Promise<string> {
    try {
      const isValid = await validateCustomTsGroupLabel({ data_label: row.name }, { needMessage: false });
      return isValid ? '' : (this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string);
    } catch {
      return this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string;
    }
  }

  clearError(row: IMetricItem) {
    if (row.error) row.error = '';
  }

  // 行操作处理
  handleAddRow(index = -1) {
    const newRow = {
      name: '',
      isNew: true,
      error: '',
      type: 'metric',
      dimensions: [],
      function: [],
      selection: false,
    };
    this.showTableData.splice(index + 1, 0, newRow);
    this.localTable.splice(index + 1, 0, newRow);
  }

  handleRemoveRow(index: number) {
    const currentDelData = this.showTableData[index];
    if (!currentDelData.isNew) {
      this.delArray.push({
        type: 'metric',
        name: currentDelData.name,
      });
    }
    this.showTableData.splice(index, 1);
    this.localTable.splice(index, 1);
  }
}
