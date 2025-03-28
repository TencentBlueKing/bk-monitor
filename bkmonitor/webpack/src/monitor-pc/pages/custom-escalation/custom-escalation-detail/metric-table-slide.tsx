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

import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { validateCustomTsGroupLabel } from 'monitor-api/modules/custom_report';
import { Debounce, deepClone } from 'monitor-common/utils';

import { METHOD_LIST } from '../../../constant/constant';
import FunctionMenu from '../../strategy-config/strategy-config-set-new/monitor-data/function-menu';
import { statusMap } from './metric-table';

import './metric-table-slide.scss';

// 常量定义
const RADIO_OPTIONS = [
  { id: 'allOption', label: window.i18n.tc('全选') },
  { id: 'checkedOption', label: window.i18n.tc('勾选项') },
];

const FIELD_SETTINGS = {
  name: { label: '名称', width: 175 },
  description: { label: '别名', width: 175 },
  unit: { label: '单位', width: 125 },
  aggregateMethod: { label: '汇聚方法', width: 125 },
  interval: { label: '上报周期', width: 125 },
  // func: { label: '函数', width: 125 },
  dimension: { label: '关联维度', width: 215 },
  disabled: { label: '启/停', width: 115 },
  hidden: { label: '显示', width: 115 },
  set: { label: '操作', width: 50 },
};

const ALL_OPTION = 'allOption';
const CHECKED_OPTION = 'checkedOption';

interface IMetricItem {
  name: string;
  description?: string;
  unit?: string;
  aggregate_method?: string;
  interval?: number;
  function?: any;
  hidden?: boolean;
  disabled?: boolean;
  [key: string]: any;
  isNew?: boolean;
  error?: string;
}

// 模糊匹配
export const fuzzyMatch = (str: string, pattern: string) => {
  const lowerStr = String(str).toLowerCase();
  const lowerPattern = String(pattern).toLowerCase();
  return lowerStr.includes(lowerPattern);
};

@Component
export default class IndicatorTableSlide extends tsc<any> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: Boolean, default: false }) autoDiscover: boolean;
  @Prop({ default: () => [] }) metricTable: IMetricItem[];
  @Prop({ default: () => [] }) unitList: any[];
  @Prop({ default: () => [] }) dimensionTable: any[];
  @Prop({ default: () => [] }) cycleOption: any[];

  @Ref() metricSliderPopover: any;
  @Ref('metricTableRef') metricTableRef: HTMLDivElement;
  @InjectReactive('metricFunctions') metricFunctions;

  localTable: IMetricItem[] = [];
  units: any[] = [];
  inputFocus = -1;
  width = 1400;

  // 单位配置
  unitConfig = { mode: ALL_OPTION, checkedList: [] };
  localUnitConfig = deepClone(this.unitConfig);

  // 表格配置
  tableConfig = {
    loading: false,
    fieldSettings: {
      name: { checked: true, disable: false },
      description: { checked: true, disable: false },
      unit: { checked: true, disable: false },
      aggregateMethod: { checked: true, disable: false },
      interval: { checked: true, disable: false },
      dimension: { checked: true, disable: false },
      func: { checked: true, disable: false },
      disabled: { checked: false, disable: false },
      hidden: { checked: true, disable: false },
      set: { checked: true, disable: false },
    },
    search: '',
  };

  // 删除列表
  delArray = [];

  // 生命周期钩子
  created() {
    this.initData();
  }

  get dimensions() {
    return this.dimensionTable.map(({ name }) => ({ id: name, name }));
  }

  // 数据初始化
  initData() {
    this.localTable = deepClone(this.metricTable);
    this.units = this.unitList;
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  @Debounce(300)
  handleSearchChange() {
    this.localTable = this.metricTable.filter(item => {
      return fuzzyMatch(item.name, this.tableConfig.search) || fuzzyMatch(item.description, this.tableConfig.search);
    });
  }

  // 事件处理
  async handleSave() {
    const newRows = this.localTable.filter(row => row.isNew);

    // 并行执行所有验证
    const validationResults = await Promise.all(
      newRows.map(async row => {
        const isValid = await this.validateName(row);
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

  @Emit('hidden')
  handleCancel() {
    this.delArray = [];
    this.localTable = deepClone(this.metricTable);
    this.tableConfig.search = '';
    return false;
  }

  // 响应式处理
  @Watch('metricTable', { immediate: true, deep: true })
  handleMetricTableChange(newVal: IMetricItem[]) {
    this.localTable = deepClone(newVal);
  }

  @Watch('unitList', { immediate: true })
  handleUnitListChange(newVal: any[]) {
    this.units = newVal;
    this.localUnitConfig = deepClone(this.unitConfig);
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
            <bk-input
              v-model={this.tableConfig.search}
              placeholder={this.$t('搜索指标')}
              right-icon='bk-icon icon-search'
              on-change={this.handleSearchChange}
            />
          </div>
          <div class='slider-table'>
            <bk-table
              ref='metricTableRef'
              v-bkloading={{ isLoading: this.tableConfig.loading }}
              data={this.localTable}
              empty-text={this.$t('无数据')}
              colBorder
            >
              {Object.entries(FIELD_SETTINGS).map(([key, config]) => {
                if (!this.tableConfig.fieldSettings[key].checked) return null;

                return (
                  <bk-table-column
                    key={key}
                    width={config.width}
                    scopedSlots={{
                      default: props => {
                        switch (key) {
                          case 'name':
                            return this.renderNameColumn(props);
                          case 'description':
                            return this.renderDescriptionColumn(props);
                          case 'unit':
                            return this.renderUnitColumn(props);
                          case 'disabled':
                          case 'hidden':
                            return this.renderSwitch(props.row, key);
                          case 'status':
                            return this.renderStatusPoint(props.row);
                          case 'aggregateMethod':
                            return this.renderAggregateMethod(props.row);
                          case 'interval':
                            return this.renderInterval(props.row);
                          case 'dimension':
                            return this.renderDimension(props.row, props.$index);
                          case 'func':
                            return this.renderFunction(props.row);
                          case 'set':
                            return this.renderOperations(props);
                          default:
                            return props.row[key] || '--';
                        }
                      },
                      header:
                        key === 'unit'
                          ? () => (
                              <bk-popover
                                ref='metricSliderPopover'
                                placement='bottom-start'
                                tippyOptions={{ appendTo: 'parent' }}
                              >
                                {this.$t('单位')} <i class='icon-monitor icon-mc-wholesale-editor' />
                                {this.renderUnitConfigPopover()}
                              </bk-popover>
                            )
                          : null,
                    }}
                    label={this.$t(config.label)}
                    prop={key}
                  />
                );
              })}
            </bk-table>
          </div>

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

  // 单位处理逻辑
  private getUnits() {
    if (this.unitConfig.mode === ALL_OPTION) return this.unitList;

    return Array.from(
      this.unitConfig.checkedList
        .reduce((map, [name, child]) => {
          const unit = map.get(name) || { id: name, name, formats: [] };
          unit.formats.push({ id: child, name: child });
          return map.set(name, unit);
        }, new Map())
        .values()
    );
  }

  // 渲染辅助方法
  private renderStatusPoint(row: IMetricItem) {
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

  private renderSwitch(row: IMetricItem, field: 'disabled' | 'hidden') {
    return (
      <div class='switch-wrap'>
        <bk-switcher
          disabled={this.autoDiscover && field === 'disabled'}
          size='small'
          theme='primary'
          value={!row[field]}
          onChange={v => (row[field] = !v)}
        />
      </div>
    );
  }

  // 表格列渲染逻辑
  private renderNameColumn(props: { row: IMetricItem }) {
    if (props.row.isNew) {
      return (
        <div
          class='name-editor'
          v-bk-tooltips={{
            content: props.row.error,
            disabled: !props.row.error,
          }}
        >
          <bk-input
            class={{ 'is-error': props.row.error, 'slider-input': true }}
            v-model={props.row.name}
            onBlur={() => this.validateName(props.row)}
            onInput={() => this.clearError(props.row)}
          />
        </div>
      );
    }
    return <span class='name'>{props.row.name || '--'}</span>;
  }

  private renderDescriptionColumn(props: { row: IMetricItem; $index: number }) {
    return (
      <bk-input
        class={['slider-input', this.inputFocus === props.$index ? 'focus' : '']}
        v-model={props.row.description}
        onBlur={() => (this.inputFocus = -1)}
        onFocus={() => (this.inputFocus = props.$index)}
      />
    );
  }

  private renderUnitColumn(props: { row: IMetricItem }) {
    return (
      <bk-select
        class='slider-select'
        v-model={props.row.unit}
        clearable={false}
        popover-width={180}
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

  // 单位配置弹窗
  private renderUnitConfigPopover() {
    return (
      <div slot='content'>
        <div class='unit-config-header'>
          <span>{this.$t('编辑范围')}</span>
          <bk-radio-group v-model={this.localUnitConfig.mode}>
            {RADIO_OPTIONS.map(opt => (
              <bk-radio
                key={opt.id}
                disabled={opt.id === CHECKED_OPTION && !this.localUnitConfig.checkedList.length}
                value={opt.id}
              >
                {opt.label}
              </bk-radio>
            ))}
          </bk-radio-group>
        </div>

        <div class='unit-selection'>
          <bk-cascade
            v-model={this.localUnitConfig.checkedList}
            list={this.unitList.map(item => ({
              ...item,
              id: item.name,
              children: item.formats || [],
            }))}
            multiple
          />
        </div>

        <div class='unit-config-footer'>
          <bk-button
            theme='primary'
            onClick={this.confirmUnitConfig}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button onClick={this.cancelUnitConfig}>{this.$t('取消')}</bk-button>
        </div>
      </div>
    );
  }

  private confirmUnitConfig() {
    this.unitConfig = deepClone(this.localUnitConfig);
    this.units = this.getUnits();
    this.metricSliderPopover.hide();
  }

  private cancelUnitConfig() {
    this.localUnitConfig = deepClone(this.unitConfig);
    this.metricSliderPopover.hide();
  }

  // 其他渲染方法
  private renderAggregateMethod(row: IMetricItem) {
    return (
      <bk-select
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

  private renderInterval(row: IMetricItem) {
    return (
      <bk-select
        class='slider-select'
        v-model={row.interval}
        clearable={false}
      >
        {this.cycleOption.map(opt => (
          <bk-option
            id={opt.id}
            key={opt.id}
            name={`${opt.name}s`}
          />
        ))}
      </bk-select>
    );
  }

  private renderDimension(row: IMetricItem, index) {
    return (
      <div
        style={index < 5 ? 'top: 0;' : ''}
        class='dimension-input'
      >
        <bk-tag-input
          v-model={row.dimensions}
          v-bk-tooltips={{
            disabled: !this.autoDiscover,
            content: this.$t('已开启自动发现新增指标，无法操作'),
          }}
          clearable={false}
          disabled={this.autoDiscover}
          list={this.dimensions}
          placeholder={this.$t('请输入')}
          trigger='focus'
          allowCreate
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

  private renderFunction(row: IMetricItem) {
    return (
      <FunctionMenu
        list={this.metricFunctions}
        onFuncSelect={v => (row.function = v)}
      >
        {row.function?.id || '--'}
      </FunctionMenu>
    );
  }

  private renderOperations(props: { $index: number }) {
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

  private async validateName(row: IMetricItem): Promise<boolean> {
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
  private validateSync(row: IMetricItem): string {
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
  private async validateAsync(row: IMetricItem): Promise<string> {
    try {
      const isValid = await validateCustomTsGroupLabel({ data_label: row.name });
      return isValid ? '' : (this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string);
    } catch {
      return this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string;
    }
  }

  private clearError(row: IMetricItem) {
    if (row.error) row.error = '';
  }

  // 行操作处理
  private handleAddRow(index: number) {
    const newRow = {
      name: '',
      isNew: true,
      error: '',
      type: 'metric',
      dimensions: [],
    };
    this.localTable.splice(index + 1, 0, newRow);
  }

  private handleRemoveRow(index: number) {
    const currentDelData = this.localTable[index];
    if (!currentDelData.isNew) {
      this.delArray.push({
        type: 'metric',
        name: currentDelData.name,
      });
    }
    this.localTable.splice(index, 1);
  }
}
