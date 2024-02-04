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
import { VNode } from 'vue';
import { Component, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';
import { debounce } from 'throttle-debounce';

import { destroyUserGroup, listDutyRule, listUserGroup } from '../../../../monitor-api/modules/model';
import EmptyStatus from '../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import DeleteSubtitle from '../../strategy-config/strategy-config-common/delete-subtitle';
import AlarmGroupDetail from '../alarm-group-detail/alarm-group-detail';
import * as authorityMap from '../authority-map';
import TableStore from '../store';

import './alarm-group.scss';

const { i18n } = window;

type TGroupType = 'monitor' | 'fta';
interface IGroupList {
  type: TGroupType;
  fromRouterName: string;
  needReflesh: boolean;
}

@Component({
  name: 'AlarmGroupList'
})
export default class AlarmGroup extends tsc<IGroupList> {
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @Prop({ default: 'monitor', type: String, validator: (val: TGroupType) => ['monitor', 'fta'].includes(val) })
  type: TGroupType;
  @Prop({ default: '', type: String }) fromRouterName: string;
  @Prop({ default: false, type: Boolean }) needReflesh: boolean; // 新增 编辑 取消操作 是否需要刷新列表数据

  loading = false;
  keyword = '';
  tableInstance: any = null;
  tableData: any[] = [];
  tableSize = 'small';
  detail = {
    show: false,
    id: null
  };
  emptyType: EmptyStatusType = 'empty';
  // 表格列数据
  tableColumnsList = [
    { label: 'ID', prop: 'id', minWidth: null, width: 90, props: {}, formatter: row => `#${row.id}` },
    {
      label: i18n.t('名称'),
      prop: 'name',
      disabled: true,
      checked: true,
      minWidth: 100,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: () => {}
    },
    {
      label: i18n.t('分派规则数'),
      prop: 'rules_count',
      minWidth: null,
      checked: true,
      width: 120,
      props: {},
      formatter: () => {}
    },
    {
      label: i18n.t('应用策略数'),
      prop: 'strategy_count',
      minWidth: null,
      checked: true,
      width: 120,
      props: {},
      formatter: () => {}
    },
    {
      label: i18n.t('轮值规则'),
      prop: 'duty_rules',
      disabled: false,
      checked: true,
      minWidth: 200,
      width: null,
      props: {},
      formatter: row => this.dutyRulesRender(row.dutyRuleNames)
    },
    {
      label: i18n.t('说明'),
      prop: 'desc',
      disabled: false,
      checked: true,
      minWidth: 180,
      width: null,
      props: { 'show-overflow-tooltip': true },
      formatter: row => row.desc || '--'
    },
    {
      label: i18n.t('最近更新人'),
      prop: 'update_user',
      disabled: false,
      checked: true,
      width: 120,
      props: {},
      formatter: row => row.update_user || '--'
    },
    {
      label: i18n.t('最近更新时间'),
      prop: 'update_time',
      disabled: false,
      checked: true,
      width: 220,
      props: {},
      formatter: row => (row.update_time ? dayjs.tz(row.update_time).format('YYYY-MM-DD HH:mm:ss') : '--')
    },
    {
      label: i18n.t('配置来源'),
      prop: 'config_source',
      disabled: false,
      checked: false,
      minWidth: 70,
      width: 170,
      props: {},
      formatter: row => row.config_source || '--'
    },
    {
      label: i18n.t('配置分组'),
      prop: 'app',
      disabled: false,
      checked: false,
      minWidth: 70,
      width: 170,
      props: {},
      formatter: row => row.app || '--'
    },
    {
      label: i18n.t('操作'),
      prop: 'handle',
      disabled: true,
      checked: true,
      minWidth: null,
      width: 130,
      props: {
        fixed: 'right'
      },
      formatter: () => {}
    }
  ];

  settingFields = [];
  selectedFields = [];

  searchCondition = [];

  handleSearch: Function = () => {};

  get isMonitor(): boolean {
    return this.type === 'monitor';
  }

  get selectedColumn() {
    return this.selectedFields.map(item => item.id);
  }

  created() {
    this.handleTableColumnsData();
    this.handleSearch = debounce(300, false, this.handleKeywordChange);
    this.getNoticeGroupList();
  }
  deactivated() {
    this.detail.show = false;
  }

  @Watch('fromRouterName')
  fromRouterNameChange(fromName: string) {
    if (['alarm-group-add', 'alarm-group-edit'].some(item => fromName.includes(item)) && this.needReflesh) {
      this.getNoticeGroupList();
    }
  }

  /**
   * @description: 处理表格cell渲染所需数据
   * @param {*}
   * @return {*}
   */
  handleTableColumnsData() {
    const fnMap = {
      name: this.cellName,
      rules_count: this.cellRulesCount,
      strategy_count: this.cellStrategyCount,
      handle: this.cellHandle,
      update: this.cellUpdate
    };
    this.tableColumnsList.forEach(column => {
      const { prop } = column;
      // eslint-disable-next-line no-param-reassign
      fnMap[prop] && (column.formatter = fnMap[prop]);
    });
    this.settingFields = this.tableColumnsList.map(item => ({
      label: item.label,
      id: item.prop,
      disabled: item.disabled
    }));
    this.selectedFields = this.tableColumnsList
      .filter(item => item.checked)
      .map(item => ({
        label: item.label,
        id: item.prop
      }));
  }
  cellName(row) {
    return (
      <span
        class='notice-group-name'
        onClick={() => this.handleShowDetailsView(row)}
      >
        {row.name}
      </span>
    );
  }
  cellRulesCount(row) {
    return (
      <div class='col-appstrategy'>
        <span
          class={['strategy-num', { 'btn-disabled': !row.rules_count || row.rules_count === 0 }]}
          onClick={() => this.handleToAppDispatch(row)}
        >
          {row.rules_count || 0}
        </span>
      </div>
    );
  }
  cellStrategyCount(row) {
    return (
      <div class='col-appstrategy'>
        <span
          class={['strategy-num', { 'btn-disabled': !row.strategy_count || row.strategy_count === 0 }]}
          v-authority={{ active: !this.authority.STRATEGY_VIEW_AUTH }}
          onClick={() =>
            this.authority.STRATEGY_VIEW_AUTH
              ? this.handleToAppStrategy(row)
              : this.handleShowAuthorityDetail(authorityMap.STRATEGY_VIEW_AUTH)
          }
        >
          {row.strategy_count || 0}
        </span>
      </div>
    );
  }
  cellUpdate(row) {
    return (
      <div class='col-name'>
        <div class='col-name-label'>{row.update_user || '--'}</div>
        <div>{dayjs.tz(row.update_time).format('YYYY-MM-DD HH:mm:ss') || '--'}</div>
      </div>
    );
  }
  cellHandle(row) {
    return [
      <bk-button
        text={true}
        disabled={!row.edit_allowed}
        class='col-btn'
        v-authority={{ active: !this.authority.MANAGE_AUTH }}
        onClick={() =>
          this.authority.MANAGE_AUTH
            ? this.handleShowAddView('edit', row)
            : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH)
        }
      >
        {this.$t('button-编辑')}
      </bk-button>,
      <bk-button
        text={true}
        disabled={!row.delete_allowed}
        class='col-btn'
        v-authority={{ active: !this.authority.MANAGE_AUTH }}
        onClick={() =>
          this.authority.MANAGE_AUTH
            ? this.handleDeleteRow(row.id, row.name)
            : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH)
        }
      >
        {this.$t('删除')}
      </bk-button>
    ];
  }

  // handleSettingChange({ fields, size }) {
  //   this.tableColumnsList.forEach(item => (item.show = fields.some(field => field.prop === item.prop)));
  //   this.tableSize = size;
  // }

  /**
   * @description: 跳转告警组新增编辑
   * @param {*} type
   * @param {string} id
   * @return {*}
   */
  handleShowAddView(type: 'add' | 'edit', row?: any) {
    if (type === 'edit') {
      this.$router.push({
        name: 'alarm-group-edit',
        params: {
          id: row.id,
          title: `${this.$t('编辑')} - #${row.id} ${row.name}`
        }
      });
    } else {
      this.$router.push({ name: 'alarm-group-add' });
    }
  }

  /**
   * @description: 搜索
   * @param {string} val 关键字
   * @return {*}
   */
  handleKeywordChange(val: string) {
    this.emptyType = val ? 'search-empty' : 'empty';
    this.keyword = val;
    this.tableInstance.keyword = val;
    this.tableInstance.page = 1;
    this.tableData = this.tableInstance.getTableData();
  }

  /**
   * @description: 获取告警组数据
   * @param {*}
   * @return {*}
   */
  async getNoticeGroupList() {
    this.loading = true;
    const query = {
      type: this.type
    };
    const ruleMap = new Map();
    const ruleList = await listDutyRule().catch(() => []);
    ruleList.forEach(r => {
      ruleMap.set(r.id, r.name);
    });
    let data = await listUserGroup(query).catch(() => {
      this.emptyType = '500';
      return [];
    });
    data = data.map(item => ({
      ...item,
      dutyRuleNames:
        item.duty_rules?.map(d => {
          const name = ruleMap.get(d) || '';
          return {
            id: d,
            name
          };
        }) || []
    }));
    if (!this.tableInstance) {
      this.tableInstance = new TableStore(data);
    } else {
      this.tableInstance.data = data;
      this.tableInstance.total = data.length;
    }
    this.tableInstance.page = 1;
    if (!!this.$route.query?.dutyRule) {
      const dutyId = this.$route.query.dutyRule;
      const searchCondition = [
        {
          id: 'rule',
          name: window.i18n.t('轮值规则'),
          values: [{ id: dutyId, name: dutyId }]
        }
      ];
      this.handleSearchCondition(searchCondition);
      this.$router.replace({
        query: undefined
      });
    }
    this.tableData = this.tableInstance.getTableData();
    this.loading = false;
  }

  /**
   * @description: 删除告警组
   * @param {number} id
   * @return {*}
   */
  handleDeleteRow(id: number, name: string) {
    this.$bkInfo({
      type: 'warning',
      title: this.$t('确认要删除？'),
      subHeader: () => (
        <DeleteSubtitle
          title={this.$tc('名称')}
          name={name}
        />
      ),
      maskClose: true,
      confirmFn: () => {
        this.loading = true;
        destroyUserGroup(id)
          .then(() => {
            this.getNoticeGroupList();
            this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
          })
          .finally(() => (this.loading = false));
      }
    });
  }

  /**
   * @description: 分页操作
   * @param {*}
   * @return {*}
   */
  handlePageChange(page: number) {
    this.tableInstance.page = page;
    this.tableData = this.tableInstance.getTableData();
  }
  /**
   * @description: 修改limit
   * @param {*}
   * @return {*}
   */
  handleLimitChange(limit: number) {
    this.tableInstance.page = 1;
    this.tableInstance.pageSize = limit;
    this.tableData = this.tableInstance.getTableData();
  }

  /**
   * @description: 展示告警组详情
   * @param {*} param1
   * @return {*}
   */
  handleShowDetailsView({ id }) {
    this.detail.show = true;
    this.detail.id = id;
  }

  // 跳转到告警分派 展示相关联的告警分派规则
  handleToAppDispatch({ rules_count: rulesCount, name }) {
    if (!rulesCount) return;
    this.$router.push({
      name: 'alarm-dispatch',
      query: { groupName: name }
    });
  }

  // 跳转到策略列表  展示相关联告警组的策略
  handleToAppStrategy({ strategy_count: strategyCount, name }) {
    if (!strategyCount) return;
    this.$router.push({
      name: 'strategy-config',
      params: { noticeName: name }
    });
  }

  /** 空状态处理 */
  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.keyword = '';
      this.tableInstance.keyword = '';
      this.tableInstance.page = 1;
      this.tableData = this.tableInstance.getTableData();
      return;
    }

    if (type === 'refresh') {
      this.emptyType = 'empty';
      return;
    }
  }

  /**
   * @description 条件搜索
   * @param value
   */
  handleSearchCondition(value) {
    this.searchCondition = value;
    this.emptyType = value?.length ? 'search-empty' : 'empty';
    this.tableInstance.searchCondition = value;
    this.tableInstance.page = 1;
    this.tableData = this.tableInstance.getTableData();
  }

  handleSettingChange({ fields, size }) {
    this.selectedFields = fields;
    this.tableSize = size;
  }

  dutyRulesRender(rules) {
    return rules?.length ? (
      <div class='col-rules'>
        <div
          class='col-rules-wrap'
          v-bk-tooltips={{
            placements: ['top-start'],
            boundary: 'window',
            content: rules.map(item => item.name).join('、'),
            delay: 200,
            allowHTML: false
          }}
        >
          {rules.map(item => (
            <span class='wrap-label'>
              <span class='text-overflow'>{item.name}</span>
            </span>
          ))}
        </div>
      </div>
    ) : (
      '--'
    );
  }

  render(): VNode {
    return (
      <div class='alarm-group-list-page'>
        <div class='alarm-group-list-page-header'>{this.$t('告警组')}</div>
        <div class='alarm-group-list-page-content'>
          <div
            // class={['alarm-group-list-wrap', { pd0: this.isMonitor }]}
            class='alarm-group-list-wrap'
            v-bkloading={{ isLoading: this.loading }}
          >
            <div class='alarm-group-tool'>
              <bk-button
                class='tool-btn mc-btn-add'
                theme='primary'
                v-authority={{ active: !this.authority.MANAGE_AUTH }}
                onClick={() =>
                  this.authority.MANAGE_AUTH
                    ? this.handleShowAddView('add')
                    : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH)
                }
              >
                <span class='icon-monitor icon-plus-line mr-6'></span>
                {this.$t('新建')}
              </bk-button>
              <bk-search-select
                class='tool-search'
                values={this.searchCondition}
                placeholder={this.$t('ID / 告警组名称')}
                data={[
                  {
                    name: 'ID',
                    id: 'id'
                  },
                  {
                    name: this.$t('告警组名称'),
                    id: 'name'
                  },
                  {
                    name: this.$t('轮值规则'),
                    id: 'rule'
                  }
                ]}
                strink={false}
                show-condition={false}
                onChange={this.handleSearchCondition}
              ></bk-search-select>
              {/* <bk-input
            class='tool-search'
            placeholder={this.$t('ID / 告警组名称')}
            value={this.keyword}
            onChange={this.handleSearch}
            right-icon='bk-icon icon-search'
          ></bk-input> */}
            </div>
            <bk-table
              class='alarm-group-table'
              data={this.tableData}
              outer-border={false}
              header-border={false}
              size={this.tableSize}
            >
              <div slot='empty'>
                <EmptyStatus
                  type={this.emptyType}
                  onOperation={this.handleOperation}
                />
              </div>
              {this.tableColumnsList
                .filter(item => this.selectedColumn.includes(item.prop))
                .map(item => (
                  <bk-table-column
                    key={item.prop}
                    label={item.label}
                    prop={item.prop}
                    {...{ props: item.props }}
                    width={item.width}
                    min-width={item.minWidth}
                    show-overflow-tooltip={item.prop !== 'duty_rules'}
                    formatter={item.formatter}
                  />
                ))}
              <bk-table-column
                type='setting'
                tippy-options={{ zIndex: 999 }}
              >
                <bk-table-setting-content
                  fields={this.settingFields}
                  selected={this.selectedFields}
                  size={this.tableSize}
                  on-setting-change={this.handleSettingChange}
                ></bk-table-setting-content>
              </bk-table-column>
            </bk-table>
            <div class='alarm-group-pagination'>
              {this.tableInstance ? (
                <bk-pagination
                  class='config-pagination list-pagination'
                  align='right'
                  size='small'
                  current={this.tableInstance.page}
                  limit={this.tableInstance.pageSize}
                  count={this.tableInstance.total}
                  limit-list={this.tableInstance.pageList}
                  on-change={this.handlePageChange}
                  on-limit-change={this.handleLimitChange}
                  show-total-count
                ></bk-pagination>
              ) : undefined}
            </div>
          </div>
        </div>
        <AlarmGroupDetail
          id={this.detail.id}
          v-model={this.detail.show}
        ></AlarmGroupDetail>
      </div>
    );
  }
}
