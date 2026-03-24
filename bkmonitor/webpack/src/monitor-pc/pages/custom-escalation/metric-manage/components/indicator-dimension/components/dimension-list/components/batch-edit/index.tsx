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

import { Debounce, deepClone } from 'monitor-common/utils';

import ColumnCheck from '../../../../../../../../performance/column-check/column-check.vue';
import type { ICustomTsFields } from '../../../../../../../service';
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

/** 组件 Props 接口 */
interface IProps {
  /** 选中的分组信息 */
  selectedGroupInfo: { id: number; name: string };
  /** 维度表格数据 */
  dimensionTable: IDimensionItem[];
  /** 是否显示侧边栏 */
  isShow: boolean;
}

/** 组件事件接口 */
interface IEmits {
  /** 隐藏事件 */
  onHidden: (v: boolean) => void;
  /** 保存信息事件 */
  onSaveInfo: (newRows: IDimensionItem[], delArray: Partial<ICustomTsFields['dimensions'][number]>[]) => void;
}

/** 维度项类型定义 */
type IDimensionItem = Partial<ICustomTsFields['dimensions'][number]> & {
  /** 是否选中 */
  selection?: boolean;
  /** 是否为新添加的项 */
  isNew?: boolean;
  /** 错误信息 */
  error?: string;
};

/** 批量编辑初始值映射 */
const initMap = {
  disabled: false,
  hidden: false,
  common: false,
};

@Component
export default class DimensionTableSlide extends tsc<IProps, IEmits> {
  /** 选中的分组信息 */
  @Prop({ default: () => {} }) selectedGroupInfo: IProps['selectedGroupInfo'];
  /** 是否显示侧边栏 */
  @Prop({ type: Boolean, default: false }) isShow: IProps['isShow'];
  /** 维度表格数据 */
  @Prop({ default: () => [] }) dimensionTable: IProps['dimensionTable'];

  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;

  /** 表格配置 */
  fieldsSettings: Record<string, IColumnConfig> = {
    name: {
      label: '名称',
      width: 175,
      renderFn: props => this.renderNameColumn(props),
      // type: 'selection',
      renderHeaderFn: this.renderNameHeader,
    },
    alias: {
      label: '别名',
      width: 175,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: (props, key) => this.renderInputColumn(props.row, key),
    },
    // disabled: { label: '启/停', width: 120, renderFn: (props, key) => this.renderSwitch(props.row, key) },
    common: {
      label: '常用维度',
      width: 140,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: (props, key) => this.renderCheckbox(props.row, key),
    },
    hidden: {
      label: '显示',
      width: 120,
      renderHeaderFn: row => this.renderPopoverHeader(row),
      renderFn: (props, key) => this.renderSwitch(props.row, key, true),
    },
    operate: { label: '操作', width: 80, renderFn: props => this.renderOperations(props) },
  };
  /** 维度搜索 */
  search = '';
  /** 表格数据 */
  localTable: IDimensionItem[] = [];
  /** 当前显示的表格数据（分页后的数据） */
  showTableData: IDimensionItem[] = [];
  /** 删除的维度名称列表 */
  delArray: Partial<ICustomTsFields['dimensions'][number]>[] = [];
  /** 全选标志位 */
  allCheckValue: 0 | 1 | 2 = CheckboxStatus.UNCHECKED;
  /** 当前的 Popover Key 值 */
  currentPopoverKey: any = null;
  /** Popover 容器 Ref 实例数组 */
  popoverRef = [];
  /** Popover 子组件 Ref 实例数组 */
  popoverChildRef: PopoverChildRef[] = [];
  /** Popover 触发元素数组 */
  triggerElements = [];
  /** 批量编辑配置对象，存储当前批量编辑的字段值 */
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
  /** 编辑模式：全量 | 勾选项 */
  editModo: typeof ALL_OPTION | typeof CHECKED_OPTION = ALL_OPTION;
  /** 保存按钮 loading 状态 */
  saveLoading = false;

  /**
   * 监听维度表格数据变化，同步到本地表格数据
   * @param newVal 新的维度表格数据
   */
  @Watch('dimensionTable', { immediate: true, deep: true })
  handleDimensionTableChange(newVal: IDimensionItem[]) {
    this.localTable = deepClone(newVal);
    for (const row of this.localTable) {
      this.$set(row, 'selection', false);
    }
    this.showTableData = this.localTable.slice(0, this.localTable.length);
  }

  /**
   * 取消操作，重置所有状态并触发隐藏事件
   * @returns false 表示关闭侧边栏
   */
  @Emit('hidden')
  handleCancel() {
    this.delArray = [];
    this.localTable = deepClone(this.dimensionTable);
    for (const row of this.localTable) {
      row.selection = false;
    }
    this.search = '';
    this.allCheckValue = CheckboxStatus.UNCHECKED;
    return false;
  }

  /**
   * 搜索维度，根据名称或别名进行模糊匹配
   * 使用防抖处理，延迟 300ms 执行
   */
  @Debounce(300)
  handleSearchChange() {
    this.showTableData = this.localTable.filter(item => {
      return fuzzyMatch(item.name, this.search) || fuzzyMatch(item.config.alias, this.search);
    });
  }

  /**
   * 清空搜索条件
   */
  handleClearSearch() {
    this.search = '';
    this.showTableData = this.localTable.slice(0, this.localTable.length);
  }

  /**
   * 切换开关状态
   * @param row 维度行数据
   * @param field 字段名
   * @param v 新的值
   */
  changeSwitch(row: IDimensionItem, field: 'disabled' | 'hidden', v: boolean) {
    row.config[field] = v;
  }

  /**
   * 保存维度数据
   * 验证所有新增维度的名称，验证通过后提交数据
   */
  handleSave() {
    try {
      this.saveLoading = true;
      const newRows = this.showTableData.filter(row => row.isNew);
      // 并行执行所有验证
      const validationResults = newRows.map(row => {
        const isValid = this.validateName(row);
        return isValid;
      });
      // 检查全局有效性
      const allValid = validationResults.every(valid => valid);
      if (!allValid) return;
      // 清除临时状态
      for (const row of newRows) {
        row.isNew = undefined;
        row.error = undefined;
      }
      const dimensionTableMap = this.dimensionTable.reduce<Record<string, IDimensionItem>>((acc, curr) => {
        const key = `${curr.name}_${curr.scope.id}`;
        acc[key] = curr;
        return acc;
      }, {});
      const updateArray = [];
      for (const row of this.localTable) {
        const key = `${row.name}_${row.scope.id}`;
        if (!dimensionTableMap[key] || !_.isEqual(dimensionTableMap[key].config, row.config)) {
          updateArray.push(row);
        }
      }
      // 提交
      this.$emit('saveInfo', updateArray, this.delArray);
    } finally {
      this.saveLoading = false;
    }
  }

  /**
   * 渲染输入列
   * @param props 表格行属性
   * @param field 字段名
   */
  renderInputColumn(row: IDimensionItem, field: string, refKey = '') {
    return (
      <bk-input
        class='slider-input'
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        v-model={row.config[field]}
      />
    );
  }

  /**
   * 隐藏当前打开的 Popover
   */
  hidePopover() {
    const popoverRef = this.popoverChildRef[this.currentPopoverKey]?.$parent;
    popoverRef?.hideHandler();
  }

  /**
   * 组件挂载时添加全局点击事件监听
   */
  mounted() {
    document.addEventListener('click', this.handleGlobalClick);
  }

  /**
   * 组件销毁前移除全局点击事件监听
   */
  beforeDestroy() {
    document.removeEventListener('click', this.handleGlobalClick);
  }

  /**
   * 处理全局点击事件，用于关闭 Popover
   * @param event 点击事件对象
   */
  handleGlobalClick(event) {
    if (!this.currentPopoverKey) return;

    const containsEls = [];
    // 获取对应的触发元素
    containsEls.push(this.triggerElements[this.currentPopoverKey]);
    // 获取当前 Popover 元素
    containsEls.push(this.popoverRef[this.currentPopoverKey]);
    // 边缘情况处理

    // 检查点击区域
    const clickInside = containsEls.some(el => el?.contains(event.target));
    if (!clickInside) {
      this.cancelBatchEdit();
    }
  }

  /**
   * 切换 Popover 显示状态
   * @param key Popover 的 key 值
   */
  togglePopover(key) {
    if (this.currentPopoverKey && this.currentPopoverKey !== key) {
      this.cancelBatchEdit();
    }
    this.currentPopoverKey = key;
  }

  /**
   * 取消批量编辑，重置相关状态
   */
  cancelBatchEdit() {
    this.hidePopover();
    this.editModo = ALL_OPTION;
    this.batchEdit[this.currentPopoverKey] = initMap[this.currentPopoverKey];
    this.currentPopoverKey = null;
  }

  /**
   * 获取 Popover 提示内容
   * @param type 字段类型
   * @returns 提示文本
   */
  getPopoverContent(type) {
    switch (type) {
      case 'hidden':
        return this.$t('关闭后，在可视化视图里，将被隐藏');
      default:
        return '';
    }
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
   * 渲染 Popover 标签内容
   * @param label 标签文本
   * @param key 字段类型
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
   * @param type 字段类型
   */
  renderPopoverSlot(type) {
    const popoverMap = {
      alias: () => this.renderInputColumn(this.batchEdit, type, type),
      disabled: () => this.renderSwitch(this.batchEdit, type, type),
      hidden: () => this.renderSwitch(this.batchEdit, type, true, type),
      common: () => this.renderCheckbox(this.batchEdit, type, type),
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
   * 确认批量编辑，根据编辑模式应用批量修改
   */
  confirmBatchEdit() {
    const isConfigKey = ['common', 'disabled', 'hidden', 'alias'].includes(this.currentPopoverKey);
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
   * 渲染表头 Popover 触发器
   * @param row 表头配置对象
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

  handleCheckAllChange({ value }) {
    const v = value === CheckboxStatus.ALL_CHECKED;
    for (const item of this.localTable) {
      this.$set(item, 'selection', v);
    }
    this.updateCheckValue();
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
   * 新增项显示输入框，已有项显示文本
   * @param props 表格行属性
   */
  renderNameColumn(props: { row: IDimensionItem }) {
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
   * 渲染开关组件
   * @param row 维度行数据
   * @param field 字段名（disabled 或 hidden）
   * @param isNegation 是否取反（hidden 字段需要取反显示）
   * @param refKey Ref 键值，用于批量编辑时保存引用
   */
  renderSwitch(row: IDimensionItem, field: 'disabled' | 'hidden', isNegation = false, refKey = '') {
    return (
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
        value={isNegation ? !row.config[field] : row.config[field]}
        onChange={v => this.changeSwitch(row, field, isNegation ? !v : v)}
      />
    );
  }

  /**
   * 渲染复选框组件
   * @param row 维度行数据
   * @param field 字段名（common）
   * @param refKey Ref 键值，用于批量编辑时保存引用
   */
  renderCheckbox(row: IDimensionItem, field: 'common', refKey = '') {
    return (
      <bk-checkbox
        ref={
          refKey
            ? el => {
                this.popoverChildRef[refKey] = el;
              }
            : ''
        }
        v-model={row.config[field]}
        false-value={false}
        true-value={true}
      />
    );
  }

  /**
   * 渲染操作列（添加/删除按钮）
   * @param props 表格行属性
   */
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

  /**
   * 验证维度名称
   * 先进行同步验证，再进行异步验证
   * @param row 维度行数据
   * @returns 验证是否通过
   */
  validateName(row): boolean {
    // 同步验证
    const syncError = this.validateSync(row);
    if (syncError) {
      this.$set(row, 'error', syncError);
      return false;
    }

    row.error = '';
    return true;
  }

  /**
   * 同步验证逻辑
   * 验证名称是否为空、是否重复、是否包含中文
   * @param row 维度行数据
   * @returns 错误信息，无错误返回空字符串
   */
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

  /**
   * 清除错误信息
   * @param row 维度行数据
   */
  clearError(row) {
    if (row.error) row.error = '';
  }

  /**
   * 添加新行
   * 在指定索引后插入一条新的维度记录
   * @param index 插入位置的索引，-1 表示插入到末尾
   */
  handleAddRow(index: number) {
    const newRow = {
      scope: {
        id: this.selectedGroupInfo.id,
        name: this.selectedGroupInfo.name,
      },
      name: '',
      type: 'dimension',
      selection: false,
      isNew: true,
      config: {
        alias: '',
        common: false,
        hidden: false,
      },
    };
    this.showTableData.splice(index + 1, 0, newRow);
    if (index === -1) {
      this.localTable.push(newRow);
    } else {
      const currentRow = this.showTableData[index];
      const currentIndex = this.localTable.findIndex(
        item => `${item.name}_${item.scope.id}` === `${currentRow.name}_${currentRow.scope.id}`
      );
      this.localTable.splice(currentIndex + 1, 0, newRow);
    }
  }

  /**
   * 删除行
   * 如果是已存在的维度，将其添加到删除列表；如果是新添加的，直接删除
   * @param index 要删除的行索引
   */
  handleRemoveRow(index: number) {
    const currentDelData = this.showTableData[index];
    if (!currentDelData.isNew) {
      this.delArray.push({
        type: 'dimension',
        name: currentDelData.name,
        scope: {
          id: this.selectedGroupInfo.id,
          name: this.selectedGroupInfo.name,
        },
      });
    }
    this.showTableData.splice(index, 1);
    const currentIndex = this.localTable.findIndex(
      item => `${item.name}_${item.scope.id}` === `${currentDelData.name}_${currentDelData.scope.id}`
    );
    this.localTable.splice(currentIndex, 1);
  }

  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={760}
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
              clearable
              placeholder={this.$t('搜索 名称、别名')}
              right-icon='bk-icon icon-search'
              on-change={this.handleSearchChange}
            />
          </div>
          {/* 头部和搜索 */}
          <bk-table
            class='slider-table'
            data={this.showTableData}
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
              disabled={!this.localTable.length}
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
