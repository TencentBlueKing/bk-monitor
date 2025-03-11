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
import { Component, Emit, Inject, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

const { i18n: I18N } = window;

import dayjs from 'dayjs';

// import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import GroupSelectMultiple from '../group-select-multiple';
import IndicatorTableSlide from './metric-table-slide';

import './metric-table.scss';

export const statusMap = new Map([
  [false, { name: window.i18n.tc('启用'), color1: '#3FC06D', color2: 'rgba(63,192,109,0.16)' }],
  [true, { name: window.i18n.tc('停用'), color1: '#FF9C01', color2: 'rgba(255,156,1,0.16)' }],
]);

interface MetricDetail {
  name: string;
  alias: string;
  labels?: string[];
  status: 'disable' | 'enable';
  unit: string;
  aggregation: string;
  func: string;
  dimensions?: string[];
  reportInterval: string;
  createTime: string;
  updateTime: string;
  latestData?: {
    value: string;
    timestamp: string;
  };
}

const StatusTag = {
  props: {
    status: {
      type: String as () => 'disable' | 'enable',
      required: true,
    },
  },
  render() {
    const statusConfig = {
      enable: { color: '#3FC06D', text: '启用' },
      disable: { color: '#FF9C01', text: '停用' },
    };
    const config = statusConfig[this.status];

    return (
      <span
        style={{
          color: config.color,
          backgroundColor: `${config.color}26`,
        }}
        class='status-tag'
      >
        <span
          style={{ backgroundColor: config.color }}
          class='status-dot'
        />
        {config.text}
      </span>
    );
  },
};

const DataPreview = {
  props: {
    value: String,
    time: String,
  },
  render() {
    return (
      <div class='data-preview'>
        <span class='data-value'>{this.value}</span>
        <span class='data-time'>（数据时间：{this.time}）</span>
      </div>
    );
  },
};

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
  @Prop([]) unitList;
  @Prop({ default: () => [], type: Array }) groupSelectList: IListItem[];
  @Prop({ default: () => [], type: Array }) value: string[];
  @Prop({ default: () => new Map(), type: Map }) groupsMap: Map<string, any>;
  table = {
    // data: Array(1).fill({
    //   id: 'haha',
    //   name: '张三',
    //   enabled: true,
    //   unit: ['haha', 'haha2', 'haha3'],
    //   hidden: true,
    //   aggregateMethod: 2,
    //   func: 'lala',
    //   interval: '60',
    //   description: '里斯',
    // }),
    data: [],
    loading: false,
    select: [],
  };

  /* 分组标签pop实例 */
  groupTagInstance = null;

  allCheckValue: 0 | 1 | 2 = 0; // 0: 取消全选 1: 半选 2: 全选

  isShow = false;

  loading = false;

  fieldSettingData: any = {};
  showDetail = false;
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
  handleToggleChange(value) {
    this.unit.toggle = value;
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

  mounted() { }

  showMetricDetail(props) {
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
    console.log('v', v, index, row);
    return [v, index];
  }

  handleGroupSelectToggle() {
    // 处理切换逻辑
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

  getTableComponent() {
    const overflowGroupDom = (props, type, customTip = '' /* 通用组样式 */) => (
      <div class='col-classifiy'>
        {props.row[type].length > 0 ? (
          <div
            ref={`table-${type}-${props.$index}`}
            class='col-classifiy-wrap'
            v-bk-tooltips={{
              placements: ['top-start'],
              boundary: 'window',
              content: () => customTip || props.row[type].join('、 '),
              delay: 200,
              allowHTML: false,
            }}
          >
            {props.row[type]?.map((item, index) => (
              <span
                key={`${item}-${index}`}
                class='classifiy-label gray'
              >
                <span class='text-overflow'>{item}</span>
              </span>
            ))}
            {props.row[`overflow${type}`] ? <span class='classifiy-overflow gray'>...</span> : undefined}
          </div>
        ) : (
          <div>--</div>
        )}
      </div>
    );

    const statusPoint = (color1: string, color2: string) => (
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

    const enabledDom = (props, type: 'enabled' | 'hidden' /* 通用开关样式 */) => (
      <div class='switch-wrap'>
        <bk-switcher
          key={props.row.id}
          v-model={props.row[type]}
          // pre-check={() => this.handlePreSwitchChange(props.row, type)}
          size='small'
          theme='primary'
        />
        {/* {!this.authority.MANAGE_AUTH ? (
          <div
            class='switch-wrap-modal'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={(e: Event) => {
              e.stopPropagation();
              e.preventDefault();
              !this.authority.MANAGE_AUTH && this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH);
            }}
          />
        ) : undefined} */}
      </div>
    );
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
    };
    const groupSlot = {
      /* 分组 */ default: ({ row, $index }) => {
        return (
          <GroupSelectMultiple
            groups-map={this.groupsMap}
            list={this.groupSelectList}
            metric-name={row.name}
            value={row.labels.map((item: GroupLabel) => item.name)}
            onChange={(v: string[]) => this.handleSelectGroup(v, $index, row)}
            onToggle={this.handleGroupSelectToggle}
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
              <div class='table-group-select'>
                {this.$t('未分组')}
                <i class='icon-monitor icon-arrow-down' />
              </div>
            )}

            <div
              class='edit-group-manage'
              slot='extension'
              onClick={() => this.handleShowGroupManage(true)}
            >
              <span class='icon-monitor icon-a-1jiahao' />
              <span>{this.$t('新建分组')}</span>
            </div>
          </GroupSelectMultiple>
        );
      },
    };
    const statusSlot = {
      /* 状态 */ default: props => {
        return (
          <span class='status-wrap'>
            {statusPoint(
              statusMap.get(Boolean(props.row?.disabled)).color1,
              statusMap.get(Boolean(props.row?.disabled)).color2
            )}
            <span>{statusMap.get(Boolean(props.row?.disabled)).name}</span>
          </span>
        );
      },
    };
    const enabledSlot = {
      /* 启停 */ default: props => enabledDom(props, 'enabled'),
    };
    const unitSlot = {
      /* 单位 */ default: props => (
        <div
          class='cell-margin'
          onMouseleave={this.handleMouseLeave}
        >
          <bk-select
            v-model={props.row.unit}
            clearable={false}
            popover-width={180}
            searchable
            onToggle={this.handleToggleChange}
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
        </div>
      ),
    };
    const hiddenSlot = {
      /* 显示 */ default: props => enabledDom(props, 'hidden'),
    };
    const aggregateMethodSlot = {
      /* 汇聚方法 */ default: props => (
        <bk-select
          clearable={false}
          value={props.row.name || '--'}
        >
          {[1, 2, 3, 4].map(item => (
            <bk-option
              id={item}
              key={item}
              name={item}
            >
              {item}
            </bk-option>
          ))}
        </bk-select>
      ),
    };
    const funcSlot = {
      /* 函数 */ default: props => props.row.name || '--',
    };
    const intervalSlot = {
      /* 上报周期 */ default: props => props.row.name || '--',
    };
    const setSlot = {
      /* 操作 */ default: props => (
        <div>
          <i
            class='icon-monitor icon-double-up'
            onClick={() => this.handClickRow(props, 'add')}
          />
          <i
            class='icon-monitor icon-double-down'
            onClick={() => this.handClickRow(props, 'del')}
          />
        </div>
      ),
    };
    const { name, enabled, unit, hidden, aggregateMethod, func, status, group, set, interval, description } =
      this.fieldSettingData;
    return (
      <bk-table
        ref='strategyTable'
        class='indicator-table'
        v-bkloading={{ isLoading: this.table.loading }}
        // col-border={true}
        empty-text={this.$t('无数据')}
        max-height={474}
        // on={{
        //   'hook:mounted': this.handleTableMountedOrActivated,
        //   'hook:activated': this.handleTableMountedOrActivated,
        // }}
        // on-header-dragend={this.handleHeaderDragend}
        // on-selection-change={this.handleSelectionChange}
        {...{
          props: {
            data: this.metricTableVal,
          },
        }}
      >
        <div slot='empty'>
          {/* <EmptyStatus
            type={this.emptyType}
            // onOperation={this.handleOperation}
            onOperation={() => { }}
          /> */}
        </div>
        <bk-table-column
          scopedSlots={{
            default: ({ row }) => (
              <bk-checkbox
                v-model={row.selection}
                onChange={this.updateCheckValue}
              />
            ),
          }}
          align='center'
          type='selection'
          value={this.allCheckValue}
          onChange={this.handleCheckChange}
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
        {/* {unit.checked && (
          <bk-table-column
            key='unit'
            width='100'
            label={this.$t('单位')}
            prop='unit'
            scopedSlots={unitSlot}
          />
        )}
        {aggregateMethod.checked && (
          <bk-table-column
            key='aggregateMethod'
            width='100'
            class-name='ahahahah'
            label={this.$t('汇聚方法')}
            prop='aggregateMethod'
            scopedSlots={aggregateMethodSlot}
          />
        )}
        {interval.checked && (
          <bk-table-column
            key='interval'
            width='100'
            label={this.$t('上报周期')}
            prop='interval'
            scopedSlots={intervalSlot}
          />
        )}
        {enabled.checked && (
          <bk-table-column
            key='enabled'
            width='100'
            label={this.$t('启/停')}
            scopedSlots={enabledSlot}
          />
        )}
        {hidden.checked && (
          <bk-table-column
            key='hidden'
            width='100'
            label={this.$t('显示')}
            scopedSlots={hiddenSlot}
          />
        )}
        {set.checked && (
          <bk-table-column
            key='set'
            width='100'
            label={this.$t('操作')}
            scopedSlots={setSlot}
          />
        )} */}
      </bk-table>
    );
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
  getDetailCmp() {
    const renderInfoItem = (props: { label: string; value?: any }, children?: JSX.Element) => {
      return (
        <div class='info-item'>
          <span class='info-label'>{props.label}：</span>
          <div class='info-content'>{children || (props.value ?? '-')}</div>
        </div>
      );
    };

    const metricData: MetricDetail = this.metricTableVal;

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
            {renderInfoItem({ label: '名称', value: metricData.name }, null)}
            {renderInfoItem({ label: '别名', value: metricData.alias }, null)}

            <div class='info-item'>
              <span class='info-label'>分组：</span>
              <div class='info-content group-list'>
                {metricData.labels?.length ? (
                  metricData.labels.map(label => (
                    <div
                      key={label}
                      class='group-item'
                    >
                      {label}
                    </div>
                  ))
                ) : (
                  <span class='empty-placeholder'>-</span>
                )}
              </div>
            </div>

            {/* {renderInfoItem({ label: '状态' }, <StatusTag status={metricData.status} />)} */}

            {renderInfoItem({ label: '单位', value: metricData.unit }, null)}

            {renderInfoItem({ label: '汇聚方法', value: metricData.aggregation }, null)}
            {renderInfoItem({ label: '函数', value: metricData.func }, null)}

            <div class='info-item'>
              <span class='info-label'>关联维度：</span>
              <div class='info-content dimension-list'>
                {metricData.dimensions?.length ? (
                  metricData.dimensions.map(dim => (
                    <span
                      key={dim}
                      class='dimension-tag'
                    >
                      {dim}
                    </span>
                  ))
                ) : (
                  <span class='empty-placeholder'>无</span>
                )}
              </div>
            </div>

            {renderInfoItem({ label: '上报周期', value: metricData.reportInterval }, null)}
            {renderInfoItem({ label: '创建时间', value: metricData.createTime }, null)}
            {renderInfoItem({ label: '更新时间', value: metricData.updateTime }, null)}

            {/* 最近数据示例 */}
            {/* {renderInfoItem(
              { label: '最近数据' },
              metricData.latestData ? (
                <DataPreview
                  time={metricData.latestData.timestamp}
                  value={metricData.latestData.value}
                />
              ) : (
                <span class='empty-placeholder'>无数据</span>
              )
            )} */}
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
              // v-authority={{ active: !this.authority.MANAGE_AUTH }}
              theme='primary'
              onClick={() => this.handleClickSlider}
            >
              {this.$t('编辑')}
            </bk-button>
            <bk-dropdown-menu
              class='header-select'
              disabled={!this.selectionLeng}
              trigger='click'
            // on-hide={() => (this.header.dropdownShow = false)}
            // on-show={() => (this.header.dropdownShow = true)}
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
                {/* 批量操作监控目标需要选择相同类型的监控对象 */}
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
                  // v-model='isShowData'
                  theme='primary'
                  onChange={() => { }}
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
      </div>
    );
  }
}
