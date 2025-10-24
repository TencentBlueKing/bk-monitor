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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, random } from 'monitor-common/utils';
import AcrossPageSelection from 'monitor-pc/components/across-page-selection/across-page-selection';
import { type SelectTypeEnum, SelectType } from 'monitor-pc/components/across-page-selection/typing';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import {
  type VariableModelType,
  getCreateVariableParams,
  getVariableModel,
} from 'monitor-pc/pages/query-template/variables';
import VariableValueDetail from 'monitor-pc/pages/query-template/variables/components/variable-panel/variable-value-detail';

import DetectionAlgorithmsGroup from '../components/detection-algorithms-group/detection-algorithms-group';

import type { TemplateDetail } from '../components/template-form/typing';
import type { IRelationService, TCompareData } from './typings';
import type { EmptyStatusOperationType } from 'monitor-pc/components/empty-status/types';
import type { MetricDetailV2 } from 'monitor-pc/pages/query-template/typings/metric';

import './relation-service-table.scss';

interface IProps {
  loading?: boolean;
  metricFunctions?: any[];
  relationService: IRelationService[];
  getCompareData?: (params: { service_name: string; strategy_template_id: number }) => Promise<TCompareData>;
  // getStrategyDetails?: (ids: (number | string)[]) => Promise<Map<number | string, TemplateDetail>>;
  onChangeCheckKeys?: (selectKeys: string[]) => void;
  onGoStrategy?: (id: number) => void;
  onShowDetails?: (id: number) => void;
}

const Columns = {
  service_name: 'service_name',
  relation: 'relation',
} as const;

const RelationStatus = {
  relation: 'relation',
  unRelation: 'unRelation',
} as const;

@Component
export default class RelationServiceTable extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) relationService: IRelationService[];
  @Prop({ type: Function, default: () => Promise.resolve({ diff: [] }) }) getCompareData: (params: {
    service_name: string;
    strategy_template_id: number;
  }) => Promise<TCompareData>;
  @Prop({ default: () => [] }) metricFunctions: any[];
  @Prop({ default: false }) loading: boolean;

  /* 搜索值 */
  searchValue = '';
  /* tab列表 */
  tabList = [
    {
      name: RelationStatus.relation,
      label: window.i18n.t('已关联的服务'),
      count: 0,
    },
    {
      name: RelationStatus.unRelation,
      label: window.i18n.t('未关联的服务'),
      count: 0,
    },
  ];
  // 选中tab
  activeTab: string = RelationStatus.relation;
  relationServiceObj = {
    list: [],
    selectKeys: new Set(),
    searchTableData: [],
    pagination: {
      current: 1,
      limit: 10,
      count: 0,
    },
  };
  unRelationServiceObj = {
    list: [],
    selectKeys: new Set(),
    searchTableData: [],
    pagination: {
      current: 1,
      limit: 10,
      count: 0,
    },
  };
  /* 表格数据 */
  tableData: IRelationService[] = [];
  tableColumns = [
    {
      label: window.i18n.t('服务名称'),
      prop: Columns.service_name,
      minWidth: 230,
      width: 230,
      props: { 'show-overflow-tooltip': true },
      formatter: (row: IRelationService) => {
        return this.tableFormatter(row, Columns.service_name);
      },
    },
    {
      label: window.i18n.t('当前已关联其他模版'),
      prop: Columns.relation,
      minWidth: 150,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: (row: IRelationService) => {
        return this.tableFormatter(row, Columns.relation);
      },
      renderHeader: () => {
        return this.tableRenderHeader(Columns.relation);
      },
    },
  ];
  /* 标头跨页多选 */
  pageSelection: SelectTypeEnum = SelectType.UN_SELECTED;
  /* 展开行 */
  expandRowKeys = [];
  /* 下发对象预览 */
  previewData: {
    expand?: boolean;
    list: IRelationService[];
    type: (typeof RelationStatus)[keyof typeof RelationStatus];
  }[] = [
    {
      list: [],
      type: RelationStatus.relation,
      expand: false,
    },
    {
      list: [],
      type: RelationStatus.unRelation,
      expand: false,
    },
  ];
  /* 展开差异对比数据 */
  expandContent: {
    algorithms: TemplateDetail['algorithms'][];
    detect: TemplateDetail['detect'];
    type: 'current' | 'relation';
    userGroupList: { id: number; name: string }[];
    variablesList: VariableModelType[];
  }[] = [];
  expandContentLoading = false;
  tableKey = random(8);
  showTips = true;

  // 差异对比的变量展示需要此数据
  metricsDetailList: MetricDetailV2[] = [];

  get isRelation() {
    return this.activeTab === RelationStatus.relation;
  }

  @Watch('relationService', { immediate: true })
  handleWatchRelationService(newVal: IRelationService[]) {
    if (newVal.length) {
      this.relationServiceObj.list = newVal.filter(item => item.has_been_applied);
      this.unRelationServiceObj.list = newVal.filter(item => !item.has_been_applied);
      this.tabList = [
        {
          name: RelationStatus.relation,
          label: this.$t('已关联的服务'),
          count: this.relationServiceObj.list.length,
        },
        {
          name: RelationStatus.unRelation,
          label: this.$t('未关联的服务'),
          count: this.unRelationServiceObj.list.length,
        },
      ];
      this.getTableData();
    }
  }

  getTableData() {
    let tableData: IRelationService[] = [];
    tableData = [...this.getCurServiceObj().list];
    this.getCurServiceObj().pagination.count = tableData.length;
    if (this.searchValue) {
      const searchLower = this.searchValue.toLocaleLowerCase();
      tableData = tableData.filter(item => {
        const serviceNameLower = item.service_name.toLocaleLowerCase();
        return serviceNameLower.includes(searchLower);
      });
    }
    this.getCurServiceObj().searchTableData = [...tableData];
    this.getCurServiceObj().pagination.count = this.getCurServiceObj().searchTableData.length;
    tableData = tableData.slice(
      this.getCurServiceObj().pagination.current * this.getCurServiceObj().pagination.limit -
        this.getCurServiceObj().pagination.limit,
      this.getCurServiceObj().pagination.current * this.getCurServiceObj().pagination.limit
    );
    this.tableData = tableData;
    this.setAcrossPageSelection();
  }

  @Debounce(300)
  handleSearchChange() {
    this.resetPageCurrent();
    this.getTableData();
  }

  handlePageChange(v: number) {
    this.getCurServiceObj().pagination.current = v;
    this.getTableData();
  }
  handleLimitChange(v: number) {
    this.getCurServiceObj().pagination.current = 1;
    this.getCurServiceObj().pagination.limit = v;
    this.getTableData();
  }

  /**
   * @description 标头跨页多选
   * @param v
   */
  handlePageSelectionChange(v: SelectTypeEnum) {
    this.pageSelection = v;
    switch (v) {
      case SelectType.ALL_SELECTED: {
        this.getCurServiceObj().selectKeys = new Set(this.getCurServiceObj().searchTableData.map(item => item.key));
        break;
      }
      case SelectType.SELECTED: {
        this.getCurServiceObj().selectKeys = new Set(this.tableData.map(item => item.key));
        break;
      }
      case SelectType.UN_SELECTED: {
        this.getCurServiceObj().selectKeys.clear();
        break;
      }
    }
    this.getCheckedPreviewData();
    this.handleChangeCheck();
    this.tableKey = random(8);
  }

  /**
   * @description 展开对比数据
   * @param row
   */
  handleExpandClick(row: IRelationService) {
    if (this.expandRowKeys.includes(row.key)) {
      this.expandRowKeys = [];
    } else {
      this.expandRowKeys = [row.key];
      this.getDiffData(row);
    }
  }

  /**
   * @description 复选框选择服务
   * @param v
   * @param row
   */
  handleCheckRow(v: boolean, row: IRelationService) {
    if (v) {
      this.getCurServiceObj().selectKeys.add(row.key);
    } else {
      this.getCurServiceObj().selectKeys.delete(row.key);
    }
    this.setAcrossPageSelection();
  }

  getCurServiceObj() {
    if (this.activeTab === RelationStatus.relation) {
      return this.relationServiceObj;
    } else {
      return this.unRelationServiceObj;
    }
  }

  /**
   * @description 切换tab
   * @param v
   */
  handleChangeTab(v: string) {
    this.activeTab = v;
    this.resetPageCurrent();
    this.getTableData();
    this.tableKey = random(8);
  }

  /**
   * @description 重置为第一页
   */
  resetPageCurrent() {
    this.getCurServiceObj().pagination.current = 1;
  }

  /**
   * @description 表头跨页多选
   */
  setAcrossPageSelection() {
    if (this.getCurServiceObj().selectKeys.size) {
      const len = this.getCurServiceObj().searchTableData.length;
      const allPage = len / this.getCurServiceObj().pagination.limit;
      if (this.getCurServiceObj().selectKeys.size === len && allPage > 1) {
        this.pageSelection = SelectType.ALL_SELECTED;
      } else if (this.tableData.every(item => this.getCurServiceObj().selectKeys.has(item.key))) {
        this.pageSelection = SelectType.SELECTED;
      } else {
        this.pageSelection = SelectType.HALF_SELECTED;
      }
    } else {
      this.pageSelection = SelectType.UN_SELECTED;
    }
    this.getCheckedPreviewData();
    this.handleChangeCheck();
    this.tableKey = random(8);
  }

  /**
   * @description 获取选中的服务对象预览数据
   */
  getCheckedPreviewData() {
    const relationChecked = [];
    const unRelationChecked = [];
    for (const item of this.relationServiceObj.list) {
      if (this.relationServiceObj.selectKeys.has(item.key)) {
        relationChecked.push(item);
      }
    }
    for (const item of this.unRelationServiceObj.list) {
      if (this.unRelationServiceObj.selectKeys.has(item.key)) {
        unRelationChecked.push(item);
      }
    }
    for (const item of this.previewData) {
      if (item.type === RelationStatus.relation) {
        item.list = relationChecked;
      }
      if (item.type === RelationStatus.unRelation) {
        item.list = unRelationChecked;
      }
    }
  }

  /**
   * @description 获取差异对比数据
   * @param current
   * @param relation
   */
  async getDiffData(row: IRelationService) {
    this.expandContentLoading = true;
    const setMetricsDetailListFn = list => {
      const metricsDetailList = [];
      const sets = new Set(this.metricsDetailList.map(item => item.metric_id));
      for (const item of list) {
        if (item?.metric_id && !sets.has(item.metric_id)) {
          metricsDetailList.push(item);
          sets.add(item.metric_id);
        }
      }
      this.metricsDetailList.push(...metricsDetailList);
    };
    const data = await this.getCompareData({
      service_name: row.service_name,
      strategy_template_id: row.strategy_template_id as number,
    }).catch(() => ({ diff: [] }));
    if (data) {
      const diffData = data?.diff || [];
      const detectData = diffData.find(d => d.field === 'detect');
      const algorithms = diffData.find(d => d.field === 'algorithms');
      const variablesList = diffData.find(d => d.field === 'variables');
      const userGroupList = diffData.find(d => d.field === 'user_group_list');
      const currentVariablesList = await getCreateVariableParams(variablesList?.current || [], this.metricsDetailList);
      const currentVariables = currentVariablesList.map(v => getVariableModel(v));
      setMetricsDetailListFn(currentVariables.map(v => v?.metric).filter(Boolean));
      const appliedVariablesList = await getCreateVariableParams(variablesList?.applied || [], this.metricsDetailList);
      const appliedVariables = appliedVariablesList.map(v => getVariableModel(v));
      setMetricsDetailListFn(appliedVariables.map(v => v?.metric).filter(Boolean));
      this.expandContent = [
        {
          type: 'current',
          algorithms: algorithms ? algorithms?.current || [] : null,
          detect: detectData ? detectData?.current || {} : null,
          variablesList: currentVariables,
          userGroupList: userGroupList ? userGroupList?.current || [] : null,
        },
        {
          type: 'relation',
          algorithms: algorithms ? algorithms?.applied || [] : null,
          detect: detectData ? detectData?.applied || {} : null,
          variablesList: appliedVariables,
          userGroupList: userGroupList ? userGroupList?.applied || [] : null,
        },
      ];
    } else {
      this.expandContent = [];
    }

    this.expandContentLoading = false;
  }

  /**
   * @description 预览部分删除单个服务
   * @param row
   */
  handlePreviewClose(row: IRelationService) {
    this.getCurServiceObj().selectKeys.delete(row.key);
    this.setAcrossPageSelection();
  }

  /**
   * @description 预览部分删除所有服务
   * @param type
   */
  handlePreviewClear(type) {
    if (type === RelationStatus.relation) {
      this.relationServiceObj.selectKeys.clear();
    } else {
      this.unRelationServiceObj.selectKeys.clear();
    }
    this.setAcrossPageSelection();
  }

  handleChangeCheck() {
    this.$emit('changeCheckKeys', [
      ...Array.from(this.relationServiceObj.selectKeys),
      ...Array.from(this.unRelationServiceObj.selectKeys),
    ]);
  }

  handleGoStrategy(id: number) {
    this.$emit('goStrategy', id);
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchValue = '';
      this.resetPageCurrent();
      this.getTableData();
    }
  }

  handleShowDetails(row: IRelationService) {
    this.$emit('showDetails', row.same_origin_strategy_template.id);
  }

  tableFormatter(row: IRelationService, prop: string) {
    const diffBtn = () => {
      return (
        <span
          key={'03'}
          class='diff-btn'
          onClick={() => this.handleExpandClick(row)}
        >
          <span>{this.$t('差异对比')}</span>
          <span
            class={['icon-monitor', this.expandRowKeys.includes(row.key) ? 'icon-double-up' : 'icon-double-down']}
          />
        </span>
      );
    };
    switch (prop) {
      case Columns.service_name:
        return this.isRelation ? (
          <span class='service-name'>
            <span class='service-name-text'>{row.service_name}</span>
            {row?.strategy?.id ? (
              <span
                class='strategy-link-relation'
                onClick={() => this.handleGoStrategy(row.strategy.id as number)}
              >
                {this.$t('查看策略')}
              </span>
            ) : (
              <span class='strategy-link-relation' />
            )}
            {row.has_diff ? diffBtn() : <span class='no-diff'>{this.$t('暂无差异')}</span>}
          </span>
        ) : (
          <span>{row.service_name}</span>
        );
      case Columns.relation:
        return (
          <span class='relation-strategy-content'>
            {[
              row.same_origin_strategy_template ? (
                <span
                  key={'01'}
                  class='strategy-name'
                >
                  <span onClick={() => this.handleShowDetails(row)}>{row.same_origin_strategy_template?.name}</span>
                </span>
              ) : (
                <span
                  key={'01'}
                  class='no-data'
                >
                  {this.$t('暂无关联')}
                </span>
              ),
              row?.strategy?.id ? (
                <span
                  key={'02'}
                  class='strategy-link'
                  onClick={() => this.handleGoStrategy(row.strategy.id as number)}
                >
                  {this.$t('查看策略')}
                </span>
              ) : undefined,
              row.has_diff ? diffBtn() : undefined,
            ]}
          </span>
        );
      default:
        return '';
    }
  }
  tableRenderHeader(prop: string) {
    switch (prop) {
      case Columns.service_name:
        return <span>{this.$t('服务名称')}</span>;
      case Columns.relation:
        return (
          <span class='table-relation-header'>
            {this.$t('当前已关联其他模版')}
            <span class='icon-monitor icon-hint' />
            <span class='tips'>{this.$t('下发将被覆盖')}</span>
          </span>
        );
      default:
        return '';
    }
  }

  expandContentFormatter() {
    return (
      <div class='table-expand-content'>
        {this.expandContentLoading ? (
          <div class='skeleton-element expand-content-skeleton' />
        ) : (
          this.expandContent.map(item => (
            <div
              key={item.type}
              class={item.type === 'current' ? 'left-content' : 'right-content'}
            >
              <div class='content-header'>{item.type === 'current' ? this.$t('当前策略') : this.$t('已关联策略')}</div>
              <div class='content-content'>
                {item?.algorithms
                  ? [
                      <div
                        key={'algorithm-01'}
                        class='title'
                      >
                        {this.$t('检测算法')}
                      </div>,
                      <div
                        key={'algorithm-02'}
                        class='content'
                      >
                        <DetectionAlgorithmsGroup
                          algorithms={item?.algorithms?.map(a => ({
                            ...a,
                            ...(a?.config || {}),
                          }))}
                        />
                      </div>,
                    ]
                  : undefined}
                {item.detect
                  ? [
                      <div
                        key={'detect-01'}
                        class='title'
                      >
                        {this.$t('判断条件')}
                      </div>,
                      <div
                        key={'detect-02'}
                        class='content'
                      >
                        <i18n path='{0}个周期内累积满足{1}次检测算法'>
                          <span class='light mr-2'>{item.detect?.config?.trigger_check_window}</span>
                          <span class='light mr-2 ml-2'>{item.detect?.config?.trigger_count}</span>
                        </i18n>
                      </div>,
                    ]
                  : undefined}
                {item.userGroupList
                  ? [
                      <div
                        key={'user-group-01'}
                        class='title'
                      >
                        {this.$t('告警组')}
                      </div>,
                      <div
                        key={'user-group-02'}
                        class='content flex-wrap'
                      >
                        {item.userGroupList.length ? (
                          item.userGroupList.map(u => (
                            <div
                              key={`${u.id}`}
                              class='user-tag-item'
                              v-bk-overflow-tips
                            >
                              {u.name}
                            </div>
                          ))
                        ) : (
                          <span>--</span>
                        )}
                      </div>,
                    ]
                  : undefined}
                {item.variablesList.map((v, index) => [
                  <div
                    key={`${index}-01`}
                    class='title tips'
                    v-bk-tooltips={{
                      width: 320,
                      content: `${this.$tc('变量名')}: ${v.variableName}<br />${this.$tc('变量别名')}: ${v.alias}<br />${this.$tc('变量描述')}: ${v.description}`,
                      allowHTML: true,
                    }}
                  >
                    {v.alias || v.name}
                  </div>,
                  <div
                    key={`${index}-02`}
                    class='content'
                  >
                    <VariableValueDetail
                      key={v.id}
                      metricFunctions={this.metricFunctions}
                      variable={v}
                    />
                  </div>,
                ])}
              </div>
            </div>
          ))
        )}
      </div>
    );
  }

  render() {
    return (
      <div class='template-details-relation-service-table'>
        <div class='left-table'>
          <bk-tab
            class='relation-service-tab'
            active={this.activeTab}
            on-tab-change={this.handleChangeTab}
          >
            {this.tabList.map(item => (
              <bk-tab-panel
                key={item.name}
                render-label={h => {
                  return h('span', { class: 'tab-label' }, [
                    item.label,
                    h('span', { class: 'tab-count' }, `(${item.count})`),
                  ]);
                }}
                name={item.name}
              />
            ))}
          </bk-tab>
          <div class='left-table-content'>
            {this.isRelation && this.showTips && (
              <div class='info-tips mt-12'>
                <span class='icon-monitor icon-hint' />
                <span>{this.$t('再次下发已关联的服务，相当于“同步”操作。')}</span>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={() => {
                    this.showTips = false;
                  }}
                />
              </div>
            )}
            <bk-input
              class={['search-input', this.isRelation ? 'mt-12' : 'mt-16']}
              v-model={this.searchValue}
              placeholder={`${this.$t('搜索')} ${this.$t('服务名称')}`}
              right-icon='bk-icon icon-search'
              clearable
              onChange={this.handleSearchChange}
            />
            {this.loading ? (
              <TableSkeleton type={4} />
            ) : (
              <bk-table
                key={this.tableKey}
                data={this.tableData}
                expand-row-keys={this.expandRowKeys}
                header-border={false}
                outer-border={false}
                row-key={row => row.key}
              >
                <div slot='empty'>
                  <EmptyStatus
                    type={this.searchValue ? 'search-empty' : 'empty'}
                    onOperation={this.handleOperation}
                  />
                </div>
                <bk-table-column
                  width={50}
                  formatter={row => {
                    return (
                      <span
                        onClick={e => {
                          e.stopPropagation();
                        }}
                      >
                        <bk-checkbox
                          value={this.getCurServiceObj().selectKeys.has(row.key)}
                          onChange={v => this.handleCheckRow(v, row)}
                        />
                      </span>
                    );
                  }}
                  render-header={() => {
                    return (
                      <AcrossPageSelection
                        value={this.pageSelection}
                        onChange={this.handlePageSelectionChange}
                      />
                    );
                  }}
                />
                <bk-table-column
                  width={0}
                  scopedSlots={{
                    default: () => {
                      return this.expandContentFormatter();
                    },
                  }}
                  type='expand'
                />
                {this.tableColumns
                  .filter(item => (item.prop === Columns.relation ? !this.isRelation : true))
                  .map(item => (
                    <bk-table-column
                      key={item.prop}
                      label={item.label}
                      prop={item.prop}
                      {...{ props: item.props }}
                      width={item.width}
                      formatter={item.formatter}
                      min-width={item.minWidth}
                      render-header={item?.renderHeader}
                    />
                  ))}
              </bk-table>
            )}
            {this.loading ? undefined : (
              <bk-pagination
                class='mt-14'
                align='right'
                count={this.getCurServiceObj().pagination.count}
                current={this.getCurServiceObj().pagination.current}
                limit={this.getCurServiceObj().pagination.limit}
                size={'small'}
                show-total-count
                on-change={this.handlePageChange}
                on-limit-change={this.handleLimitChange}
              />
            )}
          </div>
        </div>
        <div class='right-preview'>
          <div class='right-preview-header'>{this.$t('下发对象预览')}</div>
          {this.previewData.map(item => (
            <div
              key={item.type}
              class='preview-expand-wrap'
            >
              <div
                class='expand-wrap-header'
                onClick={() => {
                  item.expand = !item.expand;
                }}
              >
                <span class={['icon-monitor icon-arrow-right', { expand: item.expand }]} />
                <span class='head-title'>
                  {item.type === RelationStatus.relation
                    ? `${this.$t('已关联')}(${this.$t('同步')})`
                    : this.$t('新关联')}
                </span>
                -
                <span class='head-count'>
                  <i18n path='共{0}个'>
                    <span class='count-light'>{item.list.length}</span>
                  </i18n>
                </span>
                <span
                  class='clear-btn'
                  v-bk-tooltips={{
                    content: this.$t('清空'),
                    placements: ['bottom'],
                  }}
                  onClick={e => {
                    e.stopPropagation();
                    this.handlePreviewClear(item.type);
                  }}
                >
                  <span class='icon-monitor icon-a-Clearqingkong clear-btn-icon' />
                </span>
              </div>
              {item.expand && (
                <div class='expand-wrap-content'>
                  {item.list.map(row => (
                    <div
                      key={row.key}
                      class='preview-item'
                      v-bk-tooltips={{
                        content: row.service_name,
                        placements: ['right'],
                      }}
                    >
                      <span class='preview-item-name'>{row.service_name}</span>
                      <span
                        class='icon-monitor icon-mc-close'
                        onClick={() => this.handlePreviewClose(row)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }
}
