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
import _ from 'lodash';

import { Component, Emit, Prop, Watch, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { Debounce, deepClone } from 'monitor-common/utils';
import CycleInput from 'monitor-pc/components/cycle-input/cycle-input';
import ColumnCheck from '../../../../../../../../performance/column-check/column-check.vue';

import { METHOD_LIST } from '../../../../../../../../../constant/constant';
import FunctionSelect from '../../../../../../../../strategy-config/strategy-config-set-new/monitor-data/function-select';
import type { ICustomTsFields, IUnitItem } from '../../../../../../../service';
import {
  type IColumnConfig,
  type PopoverChildRef,
  type RequestHandlerMap,
  ALL_OPTION,
  CheckboxStatus,
  CHECKED_OPTION,
  RADIO_OPTIONS,
} from '../../../../../../type';
import { fuzzyMatch } from '../../../../../../utils';

import './index.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

/** 组件 Props 接口定义 */
interface IProps {
  /** 选中的分组信息 */
  selectedGroupInfo: { id: number; name: string };
  /** 指标表格数据 */
  metricTable: IMetricItem[];
  /** 单位列表 */
  unitList: IUnitItem[];
  /** 维度表格数据 */
  dimensionTable: ICustomTsFields['dimensions'];
  /** 是否显示弹窗 */
  isShow: boolean;
}

/** 指标项类型定义 */
type IMetricItem = Partial<ICustomTsFields['metrics'][number]> & {
  /** 是否选中 */
  selection: boolean;
  /** 是否为新添加的行 */
  isNew?: boolean;
  /** 错误信息 */
  error?: string;
};

/** 默认分页大小 */
const DEFAULT_PAGE_SIZE = 20;
/** 默认单元格高度 */
const DEFAULT_CELL_HEIGHT = 40;
/** 加载延迟时间(ms) */
const LOAD_DELAY = 300;

/** 批量编辑初始值映射 */
const initMap = {
  config: {
    alias: '',
    unit: '',
    aggregate_method: '',
    interval: 10,
    function: [],
    hidden: false,
    disabled: false,
  },
  dimensions: [],
};

@Component
export default class BatchEdit extends tsc<IProps> {
  @Prop({ default: () => {} }) selectedGroupInfo: IProps['selectedGroupInfo'];
  @Prop({ type: Boolean, default: false }) isShow: IProps['isShow'];
  @Prop({ default: () => [] }) metricTable: IProps['metricTable'];
  @Prop({ default: () => [] }) unitList: IProps['unitList'];
  @Prop({ default: () => [] }) dimensionTable: IProps['dimensionTable'];
  /** 侧边栏宽度 */
  sliderWidth = window.innerWidth * 0.9 > 1280 ? window.innerWidth * 0.9 : 1280;

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 本地表格数据（用于编辑） */
  localTable: IMetricItem[] = [];
  /** 当前页码 */
  currentPage = 1;
  /** 每页条数 */
  pageSize = DEFAULT_PAGE_SIZE;
  /** 单元格高度 */
  cellHeight = DEFAULT_CELL_HEIGHT;
  /** 总页数 */
  totalPages = 0;
  /** 当前显示的表格数据（分页后的数据） */
  showTableData: IMetricItem[] = [];
  /** 批量编辑的临时数据对象 */
  batchEdit: any = {
    config: {
      alias: '',
      unit: '',
      aggregate_method: '',
      interval: 10,
      function: [],
      hidden: false,
      disabled: false,
    },
    dimensions: [],
  };
  /** 编辑模式：全量编辑 | 仅编辑勾选项 */
  editModo: typeof ALL_OPTION | typeof CHECKED_OPTION = ALL_OPTION;
  /** 表格搜索条件列表 */
  search = [];
  /** 底部加载状态配置 */
  bottomLoadingOptions = {
    size: 'small',
    isLoading: false,
  };
  /** 筛选条件对象（用于表格过滤） */
  metricSearchObj = {
    name: [],
    alias: [],
    unit: [],
    func: [],
    aggregate: [],
    show: [],
  };
  /** 待删除的行数据列表 */
  delArray: Partial<ICustomTsFields['metrics'][number]>[] = [];
  /** 表格列配置 */
  fieldsSettings: Record<string, IColumnConfig> = {
    name: {
      label: this.$t('名称') as string,
      minWidth: 150,
      renderFn: props => this.renderNameColumn(props),
      // type: 'selection',
      renderHeaderFn: this.renderNameHeader,
    },
    alias: {
      label: this.$t('别名') as string,
      minWidth: 150,
      renderFn: props => this.renderAliasColumn(props),
    },
    unit: {
      label: this.$t('单位') as string,
      minWidth: 120,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderUnitColumn(props),
    },
    aggregate_method: {
      label: this.$t('汇聚方法') as string,
      minWidth: 120,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderAggregateMethod(props.row),
    },
    interval: {
      label: this.$t('上报周期') as string,
      minWidth: 120,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderInterval(props.row),
    },
    function: {
      label: this.$t('函数') as string,
      minWidth: 140,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: props => this.renderFunction(props.row),
    },
    dimensions: {
      label: this.$t('关联维度') as string,
      minWidth: 180,
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
      minWidth: 80,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: (props, key) => this.renderSwitch(props.row, key as 'disabled' | 'hidden'),
    },
    operate: {
      label: '操作',
      minWidth: 100,
      // fixed: 'right',
      renderFn: props => this.renderOperations(props),
    },
  };
  /** 当前打开的 Popover 对应的字段 key */
  currentPopoverKey: any = null;
  /** Popover 触发元素的 Ref 实例集合 */
  triggerElements = [];
  /** Popover 容器的 Ref 实例集合 */
  popoverRef = [];
  /** Popover 子组件的 Ref 实例集合 */
  popoverChildRef: PopoverChildRef[] = [];

  /** 全选复选框状态：0-未选中，1-部分选中，2-全选 */
  allCheckValue: 0 | 1 | 2 = CheckboxStatus.UNCHECKED;
  /** 维度搜索关键词 */
  searchKey = '';
  /** 保存按钮 loading 状态 */
  saveLoading = false;

  /**
   * 获取维度数据列表
   * 包含搜索关键词（如果存在）和维度表格数据
   * @returns {Array} 维度数据列表
   */
  get dimensions() {
    const newDimension = this.searchKey ? [{ id: this.searchKey, name: this.searchKey, isNew: true }] : [];
    return newDimension.concat(this.dimensionTable.map(({ name }) => ({ id: name, name, isNew: false })));
  }

  /**
   * 获取搜索下拉框的数据配置
   * @returns {Array} 搜索字段配置列表
   */
  get metricSearchData() {
    return [
      {
        name: this.$t('名称'),
        id: 'name',
        multiple: false,
        children: [],
      },
      {
        name: this.$t('别名'),
        id: 'alias',
        multiple: false,
        children: [],
      },
      {
        name: this.$t('单位'),
        id: 'unit',
        multiple: false,
        children: this.unitList,
      },
      {
        name: this.$t('汇聚方法'),
        id: 'aggregate',
        multiple: false,
        children: METHOD_LIST,
      },
      {
        name: this.$t('显/隐'),
        id: 'show',
        multiple: false,
        children: [
          { id: 'true', name: this.$t('显示') },
          { id: 'false', name: this.$t('隐藏') },
        ],
      },
    ];
  }

  /**
   * 获取当前 Popover 对应的 DOM 元素引用
   * 根据不同的字段类型返回不同的 ref 路径
   * @returns {HTMLElement | Vue | string} DOM 元素或组件实例
   */
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
   * 处理搜索条件变化
   * @param {Array} list - 搜索条件列表
   */
  @Debounce(LOAD_DELAY)
  handleSearchChange(list = []) {
    this.search = list;
    const search = {
      name: [],
      alias: [],
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

  /**
   * 根据搜索条件过滤表格数据
   * 支持按名称、别名、单位、汇聚方法、显示状态进行过滤
   */
  handleFilterTable() {
    const { name, alias, unit, aggregate, show } = this.metricSearchObj;
    const nameLength = name.length;
    const aliasLength = alias.length;
    const unitLength = unit.length;
    const aggregateLength = aggregate.length;
    const isShowLength = show.length;

    this.showTableData = this.localTable.filter(item => {
      return (
        (nameLength ? name.some(n => fuzzyMatch(item.name, n)) : true) &&
        (aliasLength ? alias.some(n => fuzzyMatch(item.config.alias, n)) : true) &&
        (unitLength ? unit.some(u => fuzzyMatch(item.config.unit || 'none', u)) : true) &&
        (aggregateLength ? aggregate.some(a => fuzzyMatch(item.config.aggregate_method || 'none', a)) : true) &&
        (isShowLength ? show.some(s => s === String(!item.config.hidden)) : true)
      );
    });
  }

  /**
   * 保存编辑结果
   * 验证新增行的名称，然后提交数据到后端
   */
  async handleSave() {
    try {
      this.saveLoading = true;
      const newRows = this.showTableData.filter(row => row.isNew);
      // 并行执行所有验证
      const validationResults = newRows.map(row => {
        return this.validateName(row);
      });
      // 检查全局有效性
      const allValid = validationResults.every(valid => valid);
      if (!allValid) return;
      // 清除临时状态
      for (const row of newRows) {
        row.isNew = undefined;
        row.error = undefined;
      }
      const metricTableMap = this.metricTable.reduce<Record<string, IMetricItem>>((acc, curr) => {
        acc[curr.id] = curr;
        return acc;
      }, {});
      const updateFields = [];
      for (const row of this.localTable) {
        if (!row.id) {
          updateFields.push(row);
          continue;
        }
        const metricItem = metricTableMap[row.id];
        if (!_.isEqual(metricItem.config, row.config) || !_.isEqual(metricItem.dimensions, row.dimensions)) {
          updateFields.push(row);
        }
      }
      const params = {
        time_series_group_id: this.timeSeriesGroupId,
        update_fields: updateFields,
        delete_fields: this.delArray,
      };
      if (this.isAPM) {
        delete params.time_series_group_id;
        Object.assign(params, {
          app_name: this.appName,
          service_name: this.serviceName,
        });
      }
      await this.requestHandlerMap.modifyCustomTsFields(params as any);
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      this.$emit('editSuccess');
    } finally {
      this.saveLoading = false;
    }
  }

  /**
   * 取消编辑，重置所有状态
   * @emits close - 关闭弹窗事件
   */
  @Emit('close')
  handleCancel() {
    this.delArray = [];
    this.localTable = deepClone(this.metricTable);
    for (const row of this.localTable) {
      row.selection = false;
    }
    this.initTableData();
    this.search = [];
    this.allCheckValue = CheckboxStatus.UNCHECKED;
    return false;
  }

  /**
   * 监听指标表格数据变化
   * @param {IMetricItem[]} newVal - 新的指标表格数据
   */
  @Watch('metricTable', { deep: true, immediate: true })
  handleMetricTableChange(newVal: IMetricItem[]) {
    this.localTable = deepClone(newVal);
    for (const row of this.localTable) {
      row.selection = false;
    }
    this.initTableData();
  }

  /**
   * 监听弹窗显示状态变化
   * @param {boolean} val - 是否显示
   */
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

  /**
   * 初始化表格显示数据
   * 重置分页状态并加载第一页数据
   */
  initTableData() {
    this.showTableData = [];
    this.currentPage = 1;
    this.totalPages = Math.ceil(this.localTable.length / this.pageSize);
    this.showTableData = this.localTable.slice(0, this.pageSize);
  }

  /**
   * 处理表格滚动到底部事件
   * 加载下一页数据（虚拟滚动）
   */
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

  handleCheckAllChange({ value }) {
    const v = value === CheckboxStatus.ALL_CHECKED;
    for (const item of this.localTable) {
      item.selection = v;
    }
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

  /**
   * 清空所有搜索条件
   * 重置搜索状态并刷新表格
   */
  handleClearSearch() {
    this.search = [];
    this.handleSearchChange();
  }

  /**
   * 渲染开关组件
   * @param {IMetricItem} row - 行数据
   * @param {'disabled' | 'hidden'} field - 字段名
   * @param {string} refKey - Ref 键名，用于批量编辑时绑定
   * @returns {JSX.Element | null}
   */
  renderSwitch(row: IMetricItem, field: 'disabled' | 'hidden', refKey = '') {
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
          value={!row.config[field]}
          onChange={v => {
            row.config[field] = !v;
          }}
        />
      </div>
    );
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
              change: this.handleCheckAllChange,
            },
          }}
        />
        <span class='name'>{this.$t('名称')}</span>
      </div>
    );
  }

  /**
   * 渲染名称列
   * 新行显示输入框，已有行显示文本
   * @param {Object} props - 表格列渲染参数
   * @param {IMetricItem} props.row - 行数据
   * @returns {JSX.Element}
   */
  renderNameColumn(props: { row: IMetricItem }) {
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

  /**
   * 渲染别名列
   * @param {Object} props - 表格列渲染参数
   * @param {number} props.$index - 行索引
   * @param {IMetricItem} props.row - 行数据
   * @returns {JSX.Element}
   */
  renderAliasColumn(props: { $index: number; row: IMetricItem }) {
    return (
      <bk-input
        class='slider-input'
        placeholder={this.$t('输入')}
        v-model={props.row.config.alias}
      />
    );
  }
  /** 组件挂载时添加全局点击事件监听 */
  mounted() {
    document.addEventListener('click', this.handleGlobalClick);
  }

  /** 组件销毁前移除全局点击事件监听 */
  beforeDestroy() {
    document.removeEventListener('click', this.handleGlobalClick);
  }

  /**
   * 处理全局点击事件，用于关闭 Popover
   * @param {Event} event - 点击事件对象
   */
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

  /**
   * 切换 Popover 显示状态
   * @param {string} key - 字段 key
   */
  togglePopover(key) {
    if (this.currentPopoverKey && this.currentPopoverKey !== key) {
      this.cancelBatchEdit();
    }
    this.currentPopoverKey = key;
  }

  /**
   * 渲染表格列头部的 Popover 触发器
   * @param {Object} row - 列配置对象
   * @returns {JSX.Element}
   */
  renderPopoverHeader(row) {
    return (
      <div
        ref={el => {
          this.triggerElements[row.key] = el;
        }}
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

  /**
   * 渲染单位选择列
   * @param {Object} props - 表格列渲染参数
   * @param {IMetricItem} props.row - 行数据
   * @param {string} refKey - Ref 键名，用于批量编辑时绑定
   * @returns {JSX.Element | null}
   */
  renderUnitColumn(props: { row: IMetricItem }, refKey = '') {
    if (!props.row.config) return null;

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
        v-model={props.row.config.unit}
        clearable={false}
        placeholder={`${this.$t('输入')}${this.$t('或')}${this.$t('选择')}`}
        popover-width={180}
        allow-create
        searchable
      >
        {this.unitList.map(group => (
          <bk-option-group
            key={group.name}
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

  /**
   * 获取 Popover 提示内容
   * @param {string} type - 字段类型
   * @returns {string} 提示文本
   */
  getPopoverContent(type) {
    switch (type) {
      case 'hidden':
        return this.$t('关闭后，在可视化视图里，将被隐藏');
      default:
        return '';
    }
  }

  /**
   * 渲染 Popover 标签内容
   * @param {Object} params - 参数对象
   * @param {string} params.label - 标签文本
   * @param {string} params.key - 字段类型
   * @returns {JSX.Element}
   */
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

  /**
   * 渲染 Popover 弹窗内容
   * @param {string} type - 字段类型
   * @returns {JSX.Element}
   */
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
        ref={el => {
          this.popoverRef[type] = el;
        }}
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

  /**
   * 确认批量编辑操作
   * 根据编辑模式（全量/勾选）更新对应行的数据
   */
  confirmBatchEdit() {
    const isConfigKey = ['alias', 'unit', 'aggregate_method', 'interval', 'function', 'disabled', 'hidden'].includes(
      this.currentPopoverKey
    );
    if (this.editModo === ALL_OPTION) {
      for (const row of this.showTableData) {
        if (isConfigKey) {
          row.config[this.currentPopoverKey] = this.batchEdit.config[this.currentPopoverKey];
        } else {
          row[this.currentPopoverKey] = this.batchEdit[this.currentPopoverKey];
        }
      }
    } else {
      for (const row of this.showTableData) {
        if (row.selection) {
          if (isConfigKey) {
            row.config[this.currentPopoverKey] = this.batchEdit.config[this.currentPopoverKey];
          } else {
            row[this.currentPopoverKey] = this.batchEdit[this.currentPopoverKey];
          }
        }
      }
    }
    this.cancelBatchEdit();
  }

  /**
   * 隐藏当前打开的 Popover
   */
  hidePopover() {
    const popoverRef = this.popoverChildRef[this.currentPopoverKey]?.$parent;
    popoverRef?.hideHandler();
  }

  /**
   * 取消批量编辑操作
   * 隐藏 Popover 并重置编辑状态
   */
  cancelBatchEdit() {
    this.hidePopover();
    this.editModo = ALL_OPTION;
    this.batchEdit[this.currentPopoverKey] = initMap[this.currentPopoverKey];
    this.currentPopoverKey = null;
  }

  /**
   * 渲染汇聚方法选择列
   * @param {IMetricItem} row - 行数据
   * @param {string} refKey - Ref 键名，用于批量编辑时绑定
   * @returns {JSX.Element | null}
   */
  renderAggregateMethod(row: IMetricItem, refKey = '') {
    return (
      <bk-select
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        placeholder={this.$t('选择')}
        class='slider-select'
        v-model={row.config.aggregate_method}
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

  /**
   * 处理上报周期变化
   * @param {number} v - 新的周期值
   * @param {IMetricItem} row - 行数据
   */
  handleIntervalChange(v: number, row: IMetricItem) {
    row.config.interval = v;
  }

  /**
   * 渲染上报周期输入列
   * @param {IMetricItem} row - 行数据
   * @param {string} refKey - Ref 键名，用于批量编辑时绑定
   * @returns {JSX.Element | null}
   */
  renderInterval(row: IMetricItem, refKey = '') {
    return (
      <CycleInput
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        class='slide-cycle-unit-input'
        isNeedDefaultVal={true}
        minSec={10}
        needAuto={false}
        value={row.config.interval}
        onChange={(v: number) => this.handleIntervalChange(v, row)}
      />
    );
  }

  /**
   * 渲染维度列表项模板
   * @param {Object} node - 维度节点数据
   * @param {*} _ - 未使用的参数
   * @param {Function} highlightKeyword - 高亮关键词的函数
   * @returns {JSX.Element}
   */
  renderMerberList(node, _, highlightKeyword) {
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

  /**
   * 渲染关联维度选择列
   * @param {IMetricItem} row - 行数据
   * @param {number} index - 行索引
   * @param {string} refKey - Ref 键名，用于批量编辑时绑定
   * @returns {JSX.Element}
   */
  renderDimension(row: IMetricItem, index, refKey = '') {
    return (
      <div
        style={index < 5 ? 'top: 0;' : ''}
        class='dimension-input'
      >
        <bk-tag-input
          ref={refKey ? el => el && (this.popoverChildRef[refKey] = el) : ''}
          v-model={row.dimensions}
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
          list={this.dimensions}
          placeholder={`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}
          tpl={this.renderMerberList}
          trigger='focus'
          allowCreate
          collapseTags
          hasDeleteIcon
          fixHeight
          onBlur={() => {
            this.searchKey = '';
          }}
          onInputchange={v => {
            this.searchKey = v.trim();
          }}
        />
      </div>
    );
  }

  /**
   * 处理函数选择变化
   * @param {Array} params - 选中的函数参数
   * @param {IMetricItem} row - 行数据
   */
  handleFunctionsChange(params, row) {
    row.function = params;
  }

  /**
   * 渲染函数选择列
   * @param {IMetricItem} row - 行数据
   * @param {string} refKey - Ref 键名，用于批量编辑时绑定
   * @returns {JSX.Element | null}
   */
  renderFunction(row: IMetricItem, refKey = '') {
    const getKey = obj => {
      return `${obj?.id || ''}_${obj?.params[0]?.value || ''}`;
    };
    return (
      <FunctionSelect
        key={getKey(row.config.function?.[0])}
        ref={refKey ? el => el && (this.popoverChildRef[refKey] = el) : ''}
        class='metric-func-selector'
        v-model={row.config.function}
        isMultiple={false}
        onValueChange={params => this.handleFunctionsChange(params, row)}
      />
    );
  }

  /**
   * 渲染操作列（添加/删除按钮）
   * @param {Object} props - 表格列渲染参数
   * @param {number} props.$index - 行索引
   * @param {IMetricItem} props.row - 行数据
   * @returns {JSX.Element}
   */
  renderOperations(props: { $index: number; row: IMetricItem }) {
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

  /**
   * 验证指标名称
   * 包含同步验证和异步验证
   * @param {IMetricItem} row - 行数据
   * @returns {Promise<boolean>} 验证是否通过
   */
  validateName(row: IMetricItem) {
    // 同步验证
    const syncError = this.validateSync(row);
    if (syncError) {
      row.error = syncError;
      return false;
    }
    // 异步验证
    // const asyncError = await this.validateAsync(row);
    // if (asyncError) {
    //   row.error = asyncError;
    //   return false;
    // }

    row.error = '';
    return true;
  }

  /**
   * 同步验证逻辑
   * 验证名称是否为空、是否重复、是否包含中文
   * @param {IMetricItem} row - 行数据
   * @returns {string} 错误信息，空字符串表示验证通过
   */
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

  /**
   * 异步验证逻辑
   * 调用后端接口验证名称格式（字母、数字、下划线，且必须以字母开头）
   * @param {IMetricItem} row - 行数据
   * @returns {Promise<string>} 错误信息，空字符串表示验证通过
   */
  // async validateAsync(row: IMetricItem): Promise<string> {
  //   try {
  //     const isValid = await validateCustomTsGroupLabel({ data_label: row.name }, { needMessage: false });
  //     return isValid ? '' : (this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string);
  //   } catch {
  //     return this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string;
  //   }
  // }

  /**
   * 清除行的错误信息
   * @param {IMetricItem} row - 行数据
   */
  clearError(row: IMetricItem) {
    if (row.error) row.error = '';
  }

  /**
   * 添加新行
   * @param {number} index - 插入位置索引，-1 表示插入到最后
   */
  handleAddRow(index = -1) {
    const newRow = {
      name: '',
      isNew: true,
      error: '',
      type: 'metric',
      dimensions: [],
      selection: false,
      config: {
        alias: '',
        unit: '',
        aggregate_method: '',
        interval: 10,
        function: [],
        hidden: false,
        disabled: false,
      },
      id: null,
      scope: {
        id: this.selectedGroupInfo.id,
        name: this.selectedGroupInfo.name,
      },
    };
    this.showTableData.splice(index + 1, 0, newRow);
    if (index === -1) {
      this.localTable.push(newRow);
    } else {
      const currentRow = this.showTableData[index];
      const currentIndex = this.localTable.findIndex(item => item.id === currentRow.id);
      this.localTable.splice(currentIndex + 1, 0, newRow);
    }
  }

  /**
   * 删除指定行
   * 如果是已有数据，会添加到删除列表
   * @param {number} index - 要删除的行索引
   */
  handleRemoveRow(index: number) {
    const currentDelData = this.showTableData[index];
    if (!currentDelData.isNew) {
      this.delArray.push({
        type: 'metric',
        name: currentDelData.name,
        scope: currentDelData.scope,
        id: currentDelData.id,
      });
    }
    this.showTableData.splice(index, 1);
    const currentIndex = this.localTable.findIndex(item => item.id === currentDelData.id);
    this.localTable.splice(currentIndex, 1);
  }

  /**
   * 主渲染方法
   * 渲染批量编辑弹窗和表格
   * @returns {JSX.Element}
   */
  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={this.sliderWidth}
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
              placeholder={this.$t('搜索 名称、别名、单位、汇聚方法、显/隐')}
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
                    minWidth={config.minWidth}
                    // fixed={config.fixed}
                    scopedSlots={{
                      default: props => {
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
              loading={this.saveLoading}
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
