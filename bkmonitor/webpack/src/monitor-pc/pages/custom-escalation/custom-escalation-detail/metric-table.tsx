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

const { i18n: I18N } = window;

import dayjs from 'dayjs';
import { deepClone } from 'monitor-common/utils';

import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import { METHOD_LIST } from '../../../constant/constant';
import ColumnCheck from '../../performance/column-check/column-check.vue';
import FunctionMenu from '../../strategy-config/strategy-config-set-new/monitor-data/function-menu';
import GroupSearchMultiple from './group-search-multiple';

import './metric-table.scss';

export const statusMap = new Map([
  [false, { name: window.i18n.tc('启用'), color1: '#3FC06D', color2: 'rgba(63,192,109,0.16)' }],
  [true, { name: window.i18n.tc('停用'), color1: '#FF9C01', color2: 'rgba(255,156,1,0.16)' }],
]);

interface ILabel {
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
  function: {
    id: string;
    name: string;
  };
  hidden: boolean;
  dimensions?: string[];
  reportInterval: string;
  create_time: number;
  update_time: number;
  latestData?: {
    value: string;
    timestamp: string;
  };
  description: string;
  interval: number;
}
interface GroupLabel {
  name: string;
}

interface IGroupListItem {
  name: string;
  matchRules: string[];
  manualList: string[];
  matchRulesOfMetrics?: string[]; // 匹配规则匹配的指标数
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
  @Prop({ default: () => { } }) allDataPreview;
  @Prop({ default: () => [] }) cycleOption: [];
  @Prop({ default: () => new Map(), type: Map }) groupsMap: Map<string, any>;
  @Prop({ default: () => new Map(), type: Map }) metricGroupsMap: Map<string, any>;

  @InjectReactive('metricFunctions') metricFunctions;

  @Ref() readonly descriptionInput!: HTMLInputElement;
  @Ref() readonly unitInput!: HTMLInputElement;
  @Ref() readonly aggConditionInput!: HTMLInputElement;
  @Ref() readonly dimensionInput!: HTMLInputElement;
  @Ref() readonly intervalInput!: HTMLInputElement;

  table = {
    data: [],
    loading: false,
    select: [],
  };

  canEditName = false; // 编辑别名
  copyDescription = ''; // 别名备份
  canEditUnit = false; // 编辑单位
  copyUnit = ''; // 单位备份
  canEditFunction = false; // 编辑函数
  copyFunction = ''; // 函数备份
  canEditAgg = false; // 编辑聚合
  copyAggregation = ''; // 聚合备份
  canEditInterval = false; // 编辑聚合
  copyInterval = ''; // 聚合备份
  canEditDimension = false; // 编辑维度
  copyDimension = []; // 编辑维度

  isAutoDiscover = false;
  /* 分组标签pop实例 */
  groupTagInstance = null;

  allCheckValue: 0 | 1 | 2 = 0; // 0: 取消全选 1: 半选 2: 全选

  isShow = false;
  isShowDialog = false;

  loading = false;

  fieldSettingData: any = {};
  showDetail = false;
  activeIndex = -1;
  tableInstance = {
    total: 0,
    data: [],
    keyword: '',
    page: 1,
    pageSize: 10,
    pageList: [10, 20, 50, 100],
    // pageList: [1, 2, 5, 10],
  };

  header = {
    value: 0,
    dropdownShow: false,
    list: [{ id: 0, name: I18N.t('添加至分组') }],
    keyword: '',
    keywordObj: [], // 搜索框绑定值
    condition: [], // 搜索条件接口参数
    conditionList: [], // 搜索可选项
    handleSearch: () => { },
  };
  unit = {
    value: true,
    index: -1,
    toggle: false,
  };

  // unitList = []; // 单位list
  get selectionLeng() {
    const selectionList = this.metricTableVal.filter(item => item.selection);
    return selectionList.length;
  }

  get metricTableVal() {
    this.changePageCount(this.metricTable.length);
    return this.metricTable.slice(
      this.tableInstance.pageSize * (this.tableInstance.page - 1),
      this.tableInstance.pageSize * this.tableInstance.page
    );
  }

  get isFta() {
    return false;
  }

  emptyType = 'empty'; // 空状态

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
        checked: true,
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

  @Watch('autoDiscover')
  updateAutoDiscover(v: boolean) {
    this.isAutoDiscover = v;
  }

  /** 获取展示时间 */
  getShowTime(timeStr: number) {
    const timestamp = new Date(timeStr * 1000);
    return dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss');
  }

  changePageCount(count: number) {
    this.tableInstance.total = count;
  }

  //  指标/维度表交互
  handleMouseenter(index) {
    this.unit.value = true;
    this.unit.index = index;
  }

  //  指标/维度表交互
  handleMouseLeave() {
    if (!this.unit.toggle) {
      this.unit.value = false;
      this.unit.index = -1;
    }
  }

  //  指标/维度表交互
  handleToggleChange(value) { }

  showMetricDetail(props) {
    this.activeIndex = props.$index;
    this.showDetail = true;
  }

  handClickRow(row, type: 'add' | 'del') {
    if (type === 'add') {
      this.table.data.splice(row.$index + 1, 0, {
        unit: [],
      });
      return;
    }
    this.table.data.splice(row.$index, 1);
  }
  @Emit('handleSelectGroup')
  handleSelectGroup(v: string[], index: number, row) {
    // 处理分组选择逻辑
    return [v, index, row.name];
  }

  handleGroupSelectToggle(isShow, row) {
    // 处理切换逻辑
    if (isShow) return;
    this.$emit(
      'handleSelectToggle',
      row.labels.map(label => label.name),
      row.name
    );
  }

  /* 分组tag tip展示 */
  handleGroupTagTip(event, groupName) {
    const groupItem = this.groupsMap.get(groupName);
    const manualCount = groupItem?.manualList?.length || 0;
    const matchRules = groupItem?.matchRules || [];
    this.groupTagInstance = this.$bkPopover(event.target, {
      placement: 'top',
      boundary: 'window',
      arrow: true,
      content: `<div>${this.$t('手动分配指标数')}：${manualCount}</div><div>${this.$t('匹配规则')}：${matchRules.length ? matchRules.join(',') : '--'
        }</div>`,
    });
    this.groupTagInstance.show();
  }
  handleRemoveGroupTip() {
    this.groupTagInstance?.hide?.();
    this.groupTagInstance?.destroy?.();
  }

  handleShowGroupManage(show: boolean) {
    // 显示分组管理
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

  getGroupCpm(row, index, showFoot = true) {
    return (
      <GroupSearchMultiple
        groups-map={this.groupsMap}
        list={this.groupSelectList}
        metric-name={row.name}
        value={row.labels.map((item: GroupLabel) => item.name)}
        onChange={(v: string[]) => this.handleSelectGroup(v, index, row)}
        onToggle={v => this.handleGroupSelectToggle(v, row)}
      >
        {row.labels?.length ? (
          <div class='table-group-tags'>
            {row.labels.map(item => (
              <span
                key={item.name}
                class='table-group-tag'
                onMouseenter={e => this.handleGroupTagTip(e, item.name)}
                onMouseleave={this.handleRemoveGroupTip}
              >
                {item.name}
              </span>
            ))}
          </div>
        ) : (
          <div class='table-group-select'>{this.$t('未分组')}</div>
        )}

        {showFoot && (
          <div
            class='edit-group-manage'
            slot='extension'
            onClick={() => this.handleShowGroupManage(true)}
          >
            <span class='icon-monitor icon-a-1jiahao' />
            <span>{this.$t('新建分组')}</span>
          </div>
        )}
      </GroupSearchMultiple>
    );
  }

  renderSelectionHeader() {
    return (
      <ColumnCheck
        {...{
          props: {
            list: [],
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
      /* 别名 */ default: props => props.row.description || '--',
      // /* 别名 */ default: ({ row }) =>
      //   !this.canEditName ? (
      //     <div
      //       class='info-content'
      //       onClick={() => this.handleShowEditDescription(row.description)}
      //     >
      //       {row.description ?? '-'}
      //     </div>
      //   ) : (
      //     <bk-input
      //       ref='descriptionInput'
      //       v-model={this.copyDescription}
      //       onBlur={() => this.handleEditDescription(row)}
      //     />
      //   ),
    };
    const groupSlot = {
      /* 分组 */ default: ({ row, $index }) => this.getGroupCpm(row, $index),
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

    const { name, status, group, description } = this.fieldSettingData;
    return (
      <bk-table
        class='indicator-table'
        v-bkloading={{ isLoading: this.table.loading }}
        empty-text={this.$t('无数据')}
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
            width='150'
            label={this.$t('名称')}
            prop='name'
            scopedSlots={nameSlot}
          />
        )}
        {description.checked && (
          <bk-table-column
            key='description'
            width='200'
            label={this.$t('别名')}
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
            width='75'
            label={this.$t('状态')}
            prop='status'
            scopedSlots={statusSlot}
          />
        )}
      </bk-table>
    );
  }

  handChangeSwitcher(v) {
    if (!v) {
      this.isShowDialog = true;
      return;
    }
    this.switcherChange(true);
  }
  @Emit('switcherChange')
  switcherChange(v: boolean) {
    this.isShowDialog = false;
    this.isAutoDiscover = v;
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

  handleRowCheck() {
    this.updateCheckValue();
  }

  updateCheckValue() {
    const checkedLeng = this.metricTableVal.filter(item => item.selection).length;
    const allLeng = this.metricTableVal.length;
    this.allCheckValue = 0;
    if (checkedLeng > 0) {
      this.allCheckValue = checkedLeng < allLeng ? 1 : 2;
    } else {
      this.allCheckValue = 0;
    }
  }

  handleCheckChange({ value }) {
    this.updateAllSelection(value === 2);
    this.updateCheckValue();
  }

  @Emit('updateAllSelection')
  updateAllSelection(v = false) {
    return v;
  }

  @Emit('handleClickSlider')
  handleClickSlider(): boolean {
    return true;
  }

  async updateCustomFields(k, v, metricName) {
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
  }

  /** 编辑名称 ↓ */
  async handleEditDescription(metricInfo) {
    this.canEditName = false;
    if (!this.copyDescription || this.copyDescription === metricInfo.description) {
      return;
    }
    await this.updateCustomFields('description', this.copyDescription, metricInfo.name);
    metricInfo.description = this.copyDescription;
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
    this.canEditUnit = false;
    if (!this.copyUnit || this.copyUnit === metricInfo.unit) {
      return;
    }
    metricInfo.unit = this.copyUnit;
    await this.updateCustomFields('unit', this.copyUnit, metricInfo.name);
  }

  handleShowEditUnit(unit) {
    this.canEditUnit = true;
    this.copyUnit = unit;
    this.$nextTick(() => {
      this.unitInput?.getPopoverInstance?.()?.show?.();
    });
  }

  /** 编辑函数 */
  async editFunction(func, metricInfo) {
    if (!func?.name || func?.name === metricInfo?.function?.name) {
      return;
    }
    metricInfo.function = func;
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
  editInterval(metricInfo, isShow) {
    if (isShow) return;
    this.canEditInterval = false;
    if (metricInfo.interval === this.copyInterval) {
      return;
    }
    metricInfo.interval = this.copyInterval;
    this.updateCustomFields('interval', this.copyInterval, metricInfo.name);
  }

  /** 编辑维度 */
  handleShowEditDimension(dimension) {
    this.canEditDimension = true;
    this.copyDimension = deepClone(dimension);
    this.$nextTick(() => {
      this.dimensionInput?.getPopoverInstance?.()?.show?.();
    });
  }
  editDimension(metricInfo, isShow) {
    if (isShow) return;
    this.canEditDimension = false;
    if (JSON.stringify(metricInfo.dimensions) === JSON.stringify(this.copyDimension)) {
      return;
    }
    metricInfo.dimensions = this.copyDimension;
    this.updateCustomFields('dimensions', this.copyDimension, metricInfo.name);
  }
  /** 切换显示 */
  handleEditHidden(v, metricInfo) {
    this.updateCustomFields('hidden', !v, metricInfo.name);
  }
  /** 切换状态 */
  handleClickDisabled(metricInfo) {
    if (this.isAutoDiscover) return;
    metricInfo.disabled = !metricInfo.disabled;
    this.updateCustomFields('disabled', metricInfo.disabled, metricInfo.name);
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

    const metricData: IMetricDetail = this.metricTableVal[this.activeIndex] || {};
    if (!metricData?.name) {
      this.showDetail = false;
      return;
    }
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
                  class='info-content'
                  onClick={() => this.handleShowEditDescription(metricData.description)}
                >
                  {metricData.description ?? '-'}
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
              <div class='info-content group-list'>{this.getGroupCpm(metricData, this.activeIndex, false)}</div>
            </div>

            <div class='info-item'>
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
            </div>

            <div class='info-item'>
              <span class='info-label'>{this.$t('单位')}：</span>
              {!this.canEditUnit ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditUnit(metricData.unit)}
                >
                  {metricData.unit ?? '-'}
                </div>
              ) : (
                <bk-select
                  ref='unitInput'
                  ext-cls='unit-content'
                  v-model={this.copyUnit}
                  clearable={false}
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
              )}
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
                {
                  <FunctionMenu
                    class='init-add'
                    list={this.metricFunctions}
                    onFuncSelect={v => this.editFunction(v, metricData)}
                  >
                    {metricData.function?.name ?? '-'}
                  </FunctionMenu>
                }
              </div>
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('关联维度')}：</span>
              {this.isAutoDiscover || !this.canEditDimension ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditDimension(metricData.dimensions)}
                >
                  {metricData.dimensions?.length ? (
                    <div class='table-dimension-tags'>
                      {metricData.dimensions.map(item => (
                        <span
                          key={item}
                          class='table-dimension-tag'
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div class='table-dimension-select'>{this.$t('-')}</div>
                  )}
                </div>
              ) : (
                <div class='info-content'>
                  <bk-select
                    ref='dimensionInput'
                    extCls='dimension-content'
                    v-model={this.copyDimension}
                    clearable={false}
                    collapseTag={false}
                    displayTag
                    multiple
                    searchable
                    onToggle={v => this.editDimension(metricData, v)}
                  >
                    {this.dimensionTable.map(dim => (
                      <bk-option
                        id={dim.name}
                        key={dim.name}
                        class='dimension-tag'
                        name={dim.name}
                      >
                        {dim.name}
                      </bk-option>
                    ))}
                  </bk-select>
                </div>
              )}
            </div>

            {/* 上报周期 */}
            <div class='info-item'>
              <span class='info-label'>{this.$t('上报周期')}：</span>
              {!this.canEditInterval ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditInterval(metricData.interval)}
                >
                  {`${metricData.interval}s` || 0}
                </div>
              ) : (
                <bk-select
                  ref='intervalInput'
                  ext-cls='unit-content'
                  v-model={this.copyInterval}
                  clearable={false}
                  placeholder={this.$t('请选择')}
                  onToggle={v => this.editInterval(metricData, v)}
                >
                  {this.cycleOption.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={`${option.name}s`}
                    />
                  ))}
                </bk-select>
              )}
            </div>
            {renderInfoItem({ label: '创建时间', value: this.getShowTime(metricData.create_time) }, true)}
            {renderInfoItem({ label: '更新时间', value: this.getShowTime(metricData.update_time) }, true)}
            {renderInfoItem(
              { label: '最近数据', value: this.allDataPreview[metricData.name] || `(${this.$t('近5分钟无数据上报')})` },
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
  render() {
    return (
      <div class='indicator-table-content'>
        <div class='indicator-table-header'>
          <div class='indicator-btn'>
            <bk-button
              class='header-btn'
              disabled={!this.metricTableVal.length}
              theme='primary'
              onClick={this.handleClickSlider}
            >
              {this.$t('编辑')}
            </bk-button>
            <bk-dropdown-menu
              class='header-select'
              disabled={!this.selectionLeng}
              trigger='click'
            >
              <div
                class={['header-select-btn', { 'btn-disabled': !this.selectionLeng }]}
                slot='dropdown-trigger'
              >
                <span class='btn-name'> {this.$t('批量操作')} </span>
                <i class={['icon-monitor', this.header.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']} />
              </div>
              <ul
                class='header-select-list'
                slot='dropdown-content'
              >
                {this.header.list.map((option, index) => (
                  <li
                    key={index}
                    class={'list-item'}
                    onClick={() => { }}
                  >
                    {option.name}
                  </li>
                ))}
              </ul>
            </bk-dropdown-menu>
            {this.showAutoDiscover && (
              <div class='list-header-button'>
                <bk-switcher
                  preCheck={this.handChangeSwitcher}
                  theme='primary'
                  value={this.isAutoDiscover}
                />
                <span class='switcher-text'>{this.$t('自动发现新增指标')}</span>
                <span class='alter-info'>
                  <i class='bk-icon icon-info' />
                  {this.$t('打开后，除了采集启用的指标，还会采集未来新增的指标')}
                </span>
              </div>
            )}
          </div>
          <bk-input
            ext-cls='search-table'
            placeholder={this.$t('搜索')}
            right-icon='icon-monitor icon-mc-search'
          />
        </div>
        <div class='strategy-config-wrap'>
          {this.loading ? (
            <TableSkeleton type={2} />
          ) : (
            <div class='table-box'>
              {[
                this.getTableComponent(),
                this.metricTableVal?.length ? (
                  <bk-pagination
                    key='table-pagination'
                    class='list-pagination'
                    v-show={this.metricTableVal.length}
                    align='right'
                    count={this.metricTable.length}
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
            class='detail'
            v-show={this.showDetail}
          >
            {this.getDetailCmp()}
          </div>
        </div>
        {
          <bk-dialog
            v-model={this.isShowDialog}
            headerPosition='left'
            title={this.$t('确认关闭？')}
            onCancel={() => {
              this.isShowDialog = false;
            }}
            onConfirm={() => this.switcherChange(false)}
          />
        }
      </div>
    );
  }
}
