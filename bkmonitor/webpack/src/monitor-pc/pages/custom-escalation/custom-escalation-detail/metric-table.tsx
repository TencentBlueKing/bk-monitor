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
import { Component, Emit, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import dayjs from 'dayjs';
import { Debounce, deepClone } from 'monitor-common/utils';
import CycleInput from 'monitor-pc/components/cycle-input/cycle-input';

import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import { METHOD_LIST } from '../../../constant/constant';
import ColumnCheck from '../../performance/column-check/column-check.vue';
import FunctionSelect from '../../strategy-config/strategy-config-set-new/monitor-data/function-select';
import { matchRuleFn } from '../group-manage-dialog';
import { DEFAULT_HEIGHT_OFFSET, statusMap } from './type';

import './metric-table.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

interface ILabel {
  name: string;
}
interface IFunc {
  id: string;
  name: string;
}
interface IMetricDetail {
  name: string;
  alias: string;
  labels?: ILabel[];
  status: 'disable' | 'enable';
  unit: string;
  aggregate_method: string;
  disabled?: boolean;
  function: IFunc[];
  hidden: boolean;
  dimensions?: string[];
  reportInterval: string;
  create_time: number;
  update_time: number;
  last_time?: number;
  latestData?: {
    value: string;
    timestamp: string;
  };
  description: string;
  interval: number;
}

interface IListItem {
  id: string;
  name: string;
  disable?: boolean;
}
@Component
export default class IndicatorTable extends tsc<any, any> {
  @Prop({ default: () => [] }) metricTable;
  @Prop({ default: false }) showAutoDiscover;
  @Prop({ default: false }) autoDiscover;
  @Prop({ default: () => [] }) unitList;
  @Prop({ default: () => [], type: Array }) groupSelectList: IListItem[];
  @Prop({ default: () => [], type: Array }) value: string[];
  @Prop({ default: () => [], type: Array }) dimensionTable;
  @Prop({ default: () => {} }) allDataPreview;
  @Prop({ default: 0 }) allCheckValue;
  @Prop({ default: () => [] }) cycleOption: [];
  @Prop({ default: () => new Map(), type: Map }) groupsMap: Map<string, any>;
  @Prop({ default: () => new Map(), type: Map }) metricGroupsMap: Map<string, any>;

  @InjectReactive('metricFunctions') metricFunctions;

  @Ref() readonly descriptionInput!: HTMLInputElement;
  @Ref() readonly aggConditionInput!: HTMLInputElement;
  @Ref() readonly intervalInput!: HTMLInputElement;
  @Ref() readonly batchAddGroupPopover!: HTMLInputElement;
  @Ref() readonly metricTableHeader!: HTMLInputElement;

  table = {
    data: [],
    loading: false,
    select: [],
  };

  canEditName = false; // 编辑别名
  copyDescription = ''; // 别名备份
  canEditFunction = false; // 编辑函数
  copyFunction = ''; // 函数备份
  canEditAgg = false; // 编辑聚合
  copyAggregation = ''; // 聚合备份
  canEditInterval = false; // 编辑聚合
  copyInterval = ''; // 聚合备份

  /* 分组标签pop实例 */
  groupTagInstance = null;

  isShow = false;
  isShowDialog = false;

  loading = false;

  fieldSettingData: any = {};
  showDetail = false;
  groupActiveIndex = -1;
  detailActiveIndex = -1;
  tableInstance = {
    data: [],
    page: 1,
    pageSize: 10,
    total: 0,
    pageList: [10, 20, 50, 100],
  };

  header = {
    value: 0,
    dropdownShow: false,
    list: [{ id: 0, name: this.$t('添加至分组') }],
  };
  editingIndex = -1;

  emptyType = 'empty'; // 空状态
  groupWidth = 200;
  resizeObserver = null;
  rectHeight = 32;
  /** 表格搜索 */
  search = [];

  get computedWidth() {
    return window.innerWidth < 1920 ? 388 : 456;
  }

  get computedHeight() {
    return this.rectHeight + DEFAULT_HEIGHT_OFFSET;
  }

  get selectionLength() {
    const selectionList = this.metricTableVal.filter(item => item.selection);
    return selectionList.length;
  }

  get metricTableVal() {
    this.tableInstance.total = this.metricTable.length;
    return this.metricTable.slice(
      this.tableInstance.pageSize * (this.tableInstance.page - 1),
      this.tableInstance.pageSize * this.tableInstance.page
    );
  }

  get groups() {
    return Array.from(this.groupsMap.keys());
  }

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
        id: 'description',
        multiple: false,
        children: [],
      },
      {
        name: this.$t('单位'),
        id: 'unit',
        multiple: false,
        children: this.unitList,
      },
      // {
      //   name: this.$t('函数'),
      //   id: 'func',
      //   multiple: false,
      //   children: this.metricFunctions,
      // },
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

  created() {
    this.fieldSettingData = {
      name: {
        checked: true,
        disable: false,
        name: this.$t('名称'),
        id: 'name',
      },
      description: {
        checked: true,
        disable: false,
        name: this.$t('别名'),
        id: 'description',
      },
      group: {
        checked: true,
        disable: false,
        name: this.$t('分组'),
        id: 'group',
      },
      status: {
        checked: false, // TODO: 暂不支持配置
        disable: false,
        name: this.$t('状态'),
        id: 'status',
      },
      unit: {
        checked: true,
        disable: false,
        name: this.$t('单位'),
        id: 'unit',
      },
      aggregateMethod: {
        checked: true,
        disable: false,
        name: this.$t('汇聚方法'),
        id: 'aggregateMethod',
      },
      interval: {
        checked: true,
        disable: false,
        name: this.$t('上报周期'),
        id: 'interval',
      },
      function: {
        checked: true,
        disable: false,
        name: this.$t('函数'),
        id: 'function',
      },
      hidden: {
        checked: true,
        disable: false,
        name: this.$t('显示'),
        id: 'hidden',
      },
      enabled: {
        checked: true,
        disable: false,
        name: this.$t('启/停'),
        id: 'enabled',
      },
      set: {
        checked: true,
        disable: false,
        name: this.$t('操作'),
        id: 'set',
      },
    };
    this.table.data = this.metricTableVal;
  }

  /** 获取展示时间 */
  getShowTime(timeStr: number) {
    if (!timeStr) return '-';
    const timestamp = new Date(timeStr * 1000);
    return dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss');
  }

  showMetricDetail(props) {
    this.detailActiveIndex = props.$index;
    this.showDetail = true;
  }

  handleSelectGroup(v: string[], index: number, row) {
    this.$emit('handleSelectGroup', [v, index, row.name]);
    // 处理分组选择逻辑
    this.$nextTick(() => {
      this.handleGroupSelectToggle(row, v);
    });
  }

  handleGroupSelectToggle(row, value) {
    // 处理切换逻辑
    this.groupActiveIndex = -1;
    this.$emit('handleSelectToggle', value, row.name);
  }

  /* 是否为匹配规则匹配的选项 */
  getIsDisable(metricName, key) {
    if (!metricName) {
      return false;
    }
    return this.groupsMap.get(key)?.matchRulesOfMetrics?.includes?.(metricName) || false;
  }
  /* 由匹配规则生成的tip */
  getDisableTip(metricName, groupName) {
    const targetGroup = this.groupsMap.get(groupName);
    let targetRule = '';
    targetGroup?.matchRules?.forEach(rule => {
      if (!targetRule) {
        if (matchRuleFn(metricName, rule)) {
          targetRule = rule;
        }
      }
    });
    return targetRule;
  }

  @Emit('showAddGroup')
  handleShowGroupManage(): boolean {
    return true;
  }

  statusPoint(color1: string, color2: string) {
    return (
      <div
        style={{ background: color2 }}
        class='status-point'
      >
        <div
          style={{ background: color1 }}
          class='point'
        />
      </div>
    );
  }

  renderSelectionHeader() {
    return (
      <ColumnCheck
        {...{
          props: {
            list: this.metricTableVal,
            value: this.allCheckValue,
            defaultType: 'current',
          },
          on: {
            change: this.handleCheckChange,
          },
        }}
      />
    );
  }

  getTableComponent() {
    const nameSlot = {
      /* 名称 */ default: props => (
        <span
          class='name'
          onClick={() => this.showMetricDetail(props)}
        >
          {props.row.name || '--'}
        </span>
      ),
    };
    const descriptionSlot = {
      /* 别名 */ default: props => (
        <div
          class='description-content'
          onClick={() => this.handleDescFocus(props)}
        >
          <bk-input
            ext-cls='description-input'
            readonly={this.editingIndex !== props.$index}
            value={props.row.description}
            show-overflow-tooltips
            onBlur={() => {
              this.editingIndex = -1;
              this.handleEditDescription(props.row);
            }}
            onChange={v => (this.copyDescription = v)}
          />
        </div>
      ),
    };
    const groupSlot = {
      /* 分组 */ default: ({ row, $index }) => (
        <div
          key={this.groupWidth}
          style={`width: ${this.groupWidth - 20}px;`}
          class='table-group-box'
        >
          {this.getGroupCpm(row, $index)}
        </div>
      ),
    };
    const statusSlot = {
      /* 状态 */ default: props => {
        return (
          <span
            class='status-wrap'
            onClick={() => this.handleClickDisabled(props.row)}
          >
            {this.statusPoint(
              statusMap.get(Boolean(props.row?.disabled)).color1,
              statusMap.get(Boolean(props.row?.disabled)).color2
            )}
            <span>{statusMap.get(Boolean(props.row?.disabled)).name}</span>
          </span>
        );
      },
    };
    const hiddenSlot = {
      /* 显示 */ default: props => (
        <bk-switcher
          class='switcher-btn'
          size='small'
          theme='primary'
          value={!props.row.hidden}
          onChange={v => this.handleEditHidden(v, props.row)}
        />
      ),
    };

    const { name, status, group, description, hidden } = this.fieldSettingData;
    return (
      <div class='indicator-table'>
        <bk-table
          v-bkloading={{ isLoading: this.table.loading }}
          empty-text={this.$t('无数据')}
          on-header-dragend={(newWidth, oldWidth, col) => {
            if (col.property === 'group') {
              this.groupWidth = newWidth;
            }
          }}
          on-selection-change={this.handleCheckChange}
          {...{
            props: {
              data: this.metricTableVal,
            },
          }}
        >
          <div slot='empty'>
            <EmptyStatus type={this.emptyType} />
          </div>
          <bk-table-column
            scopedSlots={{
              default: ({ row }) => (
                <bk-checkbox
                  v-model={row.selection}
                  onChange={this.handleRowCheck}
                />
              ),
            }}
            align='center'
            renderHeader={this.renderSelectionHeader}
            type='selection'
          />
          {name.checked && (
            <bk-table-column
              key='name'
              label={this.$t('名称')}
              minWidth='150'
              prop='name'
              scopedSlots={nameSlot}
            />
          )}
          {description.checked && (
            <bk-table-column
              key='description'
              label={this.$t('别名')}
              minWidth='200'
              prop='description'
              scopedSlots={descriptionSlot}
            />
          )}
          {group.checked && (
            <bk-table-column
              key='group'
              width='200'
              label={this.$t('分组')}
              prop='group'
              scopedSlots={groupSlot}
            />
          )}
          {status.checked && (
            <bk-table-column
              key='status'
              label={this.$t('状态')}
              minWidth='125'
              prop='status'
              scopedSlots={statusSlot}
            />
          )}
          {hidden.checked && (
            <bk-table-column
              key='hidden'
              renderHeader={() => (
                <div>
                  <span>{this.$t('显示')}</span>
                  <bk-popover ext-cls='render-header-hidden-popover'>
                    <bk-icon type='info-circle' />
                    <div slot='content'>{this.$t('关闭后，在可视化视图里，将被隐藏')}</div>
                  </bk-popover>
                </div>
              )}
              label={this.$t('显示')}
              minWidth='75'
              prop='hidden'
              scopedSlots={hiddenSlot}
            />
          )}
        </bk-table>
      </div>
    );
  }

  /** 批量添加至分组 */
  handleBatchAdd(groupName) {
    this.batchAddGroupPopover?.hideHandler?.();
    if (!groupName) {
      return;
    }
    this.$emit(
      'handleBatchAddGroup',
      groupName,
      this.metricTableVal.filter(item => item.selection).map(metric => metric.name)
    );
  }

  handChangeSwitcher(v) {
    if (!v) {
      this.isShowDialog = true;
      return false;
    }
    this.switcherChange(true);
    return true;
  }
  @Emit('switcherChange')
  switcherChange(v: boolean) {
    this.isShowDialog = false;
    return v;
  }
  handlePageChange(v: number) {
    this.updateAllSelection();
    this.tableInstance.page = v;
  }

  handleLimitChange(v: number) {
    this.tableInstance.page = 1;
    this.tableInstance.pageSize = v;
    this.updateAllSelection();
  }

  @Emit('rowCheck')
  handleRowCheck() {}

  handleCheckChange({ value }) {
    this.updateAllSelection(value === 2);
  }

  @Emit('updateAllSelection')
  updateAllSelection(v = false) {
    return v;
  }

  @Emit('handleClickSlider')
  handleClickSlider(): boolean {
    return true;
  }

  @Emit('searchChange')
  handleSearchChange(list) {
    this.search = list;
    return list;
  }

  async updateCustomFields(k, v, metricName, showMsg = false) {
    try {
      await this.$store.dispatch('custom-escalation/modifyCustomTsFields', {
        time_series_group_id: this.$route.params.id,
        update_fields: [
          {
            type: 'metric',
            [k]: v,
            name: metricName,
          },
        ],
      });
      if (showMsg) {
        this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      }
    } catch (error) {
      console.log('error', error);
    }
  }

  /** 编辑名称 ↓ */
  async handleEditDescription(metricInfo) {
    this.canEditName = false;
    if (this.copyDescription === metricInfo.description) {
      this.copyDescription = '';
      return;
    }
    await this.updateCustomFields('description', this.copyDescription, metricInfo.name);
    metricInfo.description = this.copyDescription;
  }

  handleDescFocus(props) {
    this.copyDescription = props.row.description;
    this.editingIndex = props.$index;
  }

  handleShowEditDescription(name) {
    this.canEditName = true;
    this.copyDescription = name;
    this.$nextTick(() => {
      this.descriptionInput.focus();
    });
  }
  /** 编辑单位 */
  async handleEditUnit(isShow, metricInfo) {
    if (isShow) return;
    await this.updateCustomFields('unit', metricInfo.unit, metricInfo.name);
  }

  /** 编辑函数 */
  async editFunction(func, metricInfo) {
    await this.updateCustomFields('function', func, metricInfo.name);
  }

  /** 编辑汇聚条件 */
  async editAggregation(metricInfo, isShow) {
    if (isShow) return;
    this.canEditAgg = false;
    if (this.copyAggregation === metricInfo.aggregate_method) return;
    metricInfo.aggregate_method = this.copyAggregation;
    await this.updateCustomFields('aggregate_method', this.copyAggregation, metricInfo.name);
  }
  handleShowEditAgg(aggCondition) {
    this.canEditAgg = true;
    this.copyAggregation = deepClone(aggCondition);
    this.$nextTick(() => {
      this.aggConditionInput?.getPopoverInstance?.()?.show?.();
    });
  }

  /** 编辑周期 */
  handleShowEditInterval(interval) {
    this.canEditInterval = true;
    this.copyInterval = interval;
    this.$nextTick(() => {
      this.intervalInput?.getPopoverInstance?.()?.show?.();
    });
  }
  editInterval(v, metricInfo) {
    // if (isShow) return;
    // this.canEditInterval = false;
    // if (metricInfo.interval === this.copyInterval) {
    //   return;
    // }
    metricInfo.interval = v;
    this.updateCustomFields('interval', v, metricInfo.name);
  }
  editDimension(metricInfo, v) {
    metricInfo.dimensions = v;
    this.updateCustomFields('dimensions', v, metricInfo.name);
  }
  /** 切换显示 */
  handleEditHidden(v, metricInfo) {
    metricInfo.hidden = !metricInfo.hidden;
    this.updateCustomFields('hidden', !v, metricInfo.name, true);
  }
  /** 切换状态 */
  handleClickDisabled(metricInfo) {
    if (this.autoDiscover) return;
    metricInfo.disabled = !metricInfo.disabled;
    this.updateCustomFields('disabled', metricInfo.disabled, metricInfo.name, true);
  }
  getGroupCpm(row, index, showFoot = true) {
    return (
      <bk-select
        key={row.name}
        clearable={false}
        value={row.labels?.map(item => item.name)}
        displayTag
        multiple
        searchable
        onChange={(v: string[]) => this.handleSelectGroup(v, index, row)}
      >
        {this.groupSelectList.map(item => (
          <bk-option
            id={item.name}
            key={item.name}
            v-bk-tooltips={
              !this.getIsDisable(row.name, item.id)
                ? { disabled: true }
                : {
                    content: this.$t('由匹配规则{0}生成', [this.getDisableTip(row.name, item.id)]),
                    placements: ['right'],
                    boundary: 'window',
                    allowHTML: false,
                  }
            }
            disabled={this.getIsDisable(row.name, item.id)}
            name={item.name}
          >
            {item.name}
          </bk-option>
        ))}
        {showFoot && (
          <div
            class='edit-group-manage'
            slot='extension'
            onClick={this.handleShowGroupManage}
          >
            <i class='icon-monitor icon-jia' />
            <span>{this.$t('新建分组')}</span>
          </div>
        )}
      </bk-select>
    );
  }
  getDetailCmp() {
    const renderInfoItem = (props: { label: string; value?: any }, readonly = false) => {
      return (
        <div class='info-item'>
          <span class='info-label'>{props.label}：</span>
          <div class={['info-content', readonly ? 'readonly' : '']}>{props.value ?? '-'}</div>
        </div>
      );
    };

    const metricData: IMetricDetail = this.metricTableVal[this.detailActiveIndex] || {};
    if (!metricData?.name) {
      this.showDetail = false;
      return;
    }
    const getKey = obj => {
      return `${obj?.id || ''}_${obj?.params[0]?.value || ''}`;
    };
    return (
      <div class='metric-card'>
        <div class='card-header'>
          <h2 class='card-title'>{this.$t('指标详情')}</h2>
          <i
            class=' icon-monitor icon-mc-close'
            onClick={() => (this.showDetail = false)}
          />
        </div>

        <div class='card-body'>
          <div class='info-column'>
            {renderInfoItem({ label: '名称', value: metricData.name }, true)}
            <div class='info-item'>
              <span class='info-label'>{this.$t('别名')}：</span>
              {!this.canEditName ? (
                <div
                  class='info-content info-text'
                  v-bk-overflow-tips
                  onClick={() => this.handleShowEditDescription(metricData.description)}
                >
                  {metricData.description || '-'}
                </div>
              ) : (
                <bk-input
                  ref='descriptionInput'
                  v-model={this.copyDescription}
                  onBlur={() => this.handleEditDescription(metricData)}
                />
              )}
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('分组')}：</span>
              <div class='info-content'>
                <div class='group-list'>{this.getGroupCpm(metricData, this.detailActiveIndex, false)}</div>
              </div>
            </div>

            {/* TODO: 暂不支持配置 */}
            {/* <div class='info-item'>
              <span class='info-label'>{this.$t('状态')}：</span>
              <div class='info-content'>
                <span
                  class='status-wrap'
                  onClick={() => this.handleClickDisabled(metricData)}
                >
                  {this.statusPoint(
                    statusMap.get(Boolean(metricData?.disabled)).color1,
                    statusMap.get(Boolean(metricData?.disabled)).color2
                  )}
                  <span>{statusMap.get(Boolean(metricData?.disabled)).name}</span>
                </span>
              </div>
            </div> */}

            <div class='info-item'>
              <span class='info-label'>{this.$t('单位')}：</span>
              {
                <bk-select
                  ext-cls='unit-content unit-ext'
                  v-model={metricData.unit}
                  clearable={false}
                  allow-create
                  searchable
                  onToggle={v => this.handleEditUnit(v, metricData)}
                >
                  {this.unitList.map((group, index) => (
                    <bk-option-group
                      key={index}
                      name={group.name}
                    >
                      {group.formats.map(option => (
                        <bk-option
                          id={option.id}
                          key={option.id}
                          name={option.name}
                        />
                      ))}
                    </bk-option-group>
                  ))}
                </bk-select>
              }
            </div>
            {/* 汇聚方法 */}
            <div class='info-item'>
              <span class='info-label'>{this.$t('汇聚方法')}：</span>
              {!this.canEditAgg ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditAgg(metricData.aggregate_method)}
                >
                  {metricData.aggregate_method || '-'}
                </div>
              ) : (
                <bk-select
                  ref='aggConditionInput'
                  ext-cls='unit-content'
                  v-model={this.copyAggregation}
                  clearable={false}
                  onToggle={v => this.editAggregation(metricData, v)}
                >
                  {METHOD_LIST.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    />
                  ))}
                </bk-select>
              )}
            </div>

            <div class='info-item'>
              <span class='info-label'>{this.$t('函数')}：</span>
              <div class='info-content'>
                <FunctionSelect
                  key={`${metricData.name}_${getKey(metricData.function[0])}`}
                  class='metric-func-selector-add'
                  isMultiple={false}
                  value={metricData.function}
                  onValueChange={params => this.editFunction(params, metricData)}
                />
              </div>
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('关联维度')}：</span>
              {
                <div class='info-content dimension-content'>
                  <bk-select
                    v-bk-tooltips={{
                      disabled: !this.autoDiscover,
                      content: this.$t('已开启自动发现新增指标，无法操作'),
                    }}
                    autoHeight={false}
                    clearable={false}
                    disabled={this.autoDiscover}
                    value={metricData.dimensions}
                    displayTag
                    multiple
                    searchable
                    onChange={v => this.editDimension(metricData, v)}
                  >
                    {this.dimensionTable.map(dim => (
                      <bk-option
                        id={dim.name}
                        key={dim.name}
                        name={dim.name}
                      >
                        {dim.name}
                      </bk-option>
                    ))}
                  </bk-select>
                </div>
              }
            </div>

            {/* 上报周期 */}
            <div class='info-item'>
              <span class='info-label'>{this.$t('上报周期')}：</span>
              <CycleInput
                class='unit-content'
                isNeedDefaultVal={true}
                minSec={10}
                needAuto={false}
                value={metricData.interval}
                onChange={(v: number) => this.editInterval(v, metricData)}
              />
              {/* {!this.canEditInterval ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditInterval(metricData.interval)}
                >
                  {`${metricData.interval}` || 0}
                </div>
              ) : (

              )} */}
            </div>
            {renderInfoItem({ label: '创建时间', value: this.getShowTime(metricData.create_time) }, true)}
            {renderInfoItem({ label: '更新时间', value: this.getShowTime(metricData.update_time) }, true)}
            {renderInfoItem(
              {
                label: '最近数据',
                value: this.allDataPreview[metricData.name]
                  ? `${this.allDataPreview[metricData.name]}(数据时间: ${this.getShowTime(metricData?.last_time)})`
                  : `(${this.$t('近5分钟无数据上报')})`,
              },
              true
            )}
            <div class='info-item'>
              <span class='info-label'>{this.$t('显示')}：</span>
              <bk-switcher
                class='switcher-btn'
                size='small'
                theme='primary'
                value={!metricData.hidden}
                onChange={v => this.handleEditHidden(v, metricData)}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
  mounted() {
    this.handleSetDefault(); // 初始化高度
    this.resizeObserver = new ResizeObserver(this.handleResize);
    if (this.metricTableHeader) {
      this.resizeObserver.observe(this.metricTableHeader);
    }
  }
  destroyed() {
    window.removeEventListener('resize', this.handleClientResize);
    if (this.resizeObserver) {
      this.resizeObserver.disconnect(); // 清除监听
    }
  }
  /** 处理元素尺寸变化（带防抖） */
  @Debounce(100)
  handleResize(entries) {
    const entry = entries[0];
    if (entry) {
      this.rectHeight = entry.contentRect.height;
    }
  }
  /** 初始化或窗口调整时设置默认值 */
  handleSetDefault() {
    if (this.metricTableHeader) {
      const rect = this.metricTableHeader.getBoundingClientRect();
      this.rectHeight = rect.height;
    }
  }
  /** 窗口调整防抖处理 */
  @Debounce(100)
  handleClientResize() {
    this.handleSetDefault();
  }
  render() {
    return (
      <div class='indicator-table-content'>
        <div
          ref='metricTableHeader'
          class='indicator-table-header'
        >
          <div class='indicator-btn'>
            <bk-button
              class='header-btn'
              theme='primary'
              onClick={this.handleClickSlider}
            >
              {this.$t('管理')}
            </bk-button>
            <bk-popover
              ext-cls='header-select-btn-popover'
              arrow={false}
              disabled={!this.selectionLength}
              placement='bottom-start'
              theme='light common-monitor'
              trigger='click'
            >
              <div class={['header-select-btn', { 'btn-disabled': !this.selectionLength }]}>
                <span class='btn-name'> {this.$t('批量操作')} </span>
                <i class={['icon-monitor', this.header.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']} />
              </div>
              <div
                class='header-select-list'
                slot='content'
              >
                {this.header.list.map((option, index) => (
                  <bk-popover
                    key={index}
                    ref='batchAddGroupPopover'
                    ext-cls='header-select-popover'
                    arrow={false}
                    placement='right-start'
                    theme='light common-monitor'
                  >
                    <div class='list-item'>{option.name}</div>
                    <div
                      class='header-select-list mh-300'
                      slot='content'
                    >
                      {Array.from(this.groupsMap.keys()).map(group => (
                        <div
                          key={group}
                          class='list-item'
                          onClick={() => this.handleBatchAdd(group)}
                        >
                          {group}
                        </div>
                      ))}
                    </div>
                  </bk-popover>
                ))}
              </div>
            </bk-popover>
            {this.showAutoDiscover && (
              <div class='list-header-button'>
                <bk-switcher
                  v-bk-tooltips={{
                    disabled: !this.autoDiscover,
                    content: this.$t('暂只支持开启，不支持关闭'),
                  }}
                  // TODO: 暂只支持开启，不支持关闭
                  disabled={this.autoDiscover}
                  preCheck={this.handChangeSwitcher}
                  theme='primary'
                  value={this.autoDiscover}
                />
                <span class='switcher-text'>{this.$t('自动发现新增指标')}</span>
                <span class='alter-info'>
                  <i
                    class='bk-icon icon-info'
                    v-bk-tooltips={{
                      content: this.$t('启用后，将自动发现新增指标/维度'),
                    }}
                  />
                </span>
              </div>
            )}
          </div>
          <SearchSelect
            class='search-table'
            ext-cls='search-table'
            data={this.metricSearchData}
            modelValue={this.search}
            placeholder={this.$t('搜索指标')}
            show-popover-tag-change
            on-change={this.handleSearchChange}
          />
        </div>
        <div class='strategy-config-wrap'>
          {this.loading ? (
            <TableSkeleton type={2} />
          ) : (
            <div
              style={{ height: `calc(100% - ${this.computedHeight}px)` }}
              class='table-box'
            >
              {[
                this.getTableComponent(),
                this.metricTableVal?.length ? (
                  <bk-pagination
                    key='table-pagination'
                    class='list-pagination'
                    v-show={this.metricTableVal.length}
                    align='right'
                    count={this.tableInstance.total}
                    current={this.tableInstance.page}
                    limit={this.tableInstance.pageSize}
                    limit-list={this.tableInstance.pageList}
                    size='small'
                    pagination-able
                    show-total-count
                    on-change={this.handlePageChange}
                    on-limit-change={this.handleLimitChange}
                  />
                ) : undefined,
              ]}
            </div>
          )}
          <div
            style={{ width: `${this.computedWidth}px`, height: `calc(100% - ${this.computedHeight}px)` }}
            class='detail'
            v-show={this.showDetail}
          >
            {this.getDetailCmp()}
          </div>
        </div>
        <bk-dialog
          ext-cls=''
          v-model={this.isShowDialog}
          headerPosition='left'
          title={this.$t('确认关闭？')}
          onCancel={() => {
            this.isShowDialog = false;
          }}
          onConfirm={() => this.switcherChange(false)}
        />
      </div>
    );
  }
}
