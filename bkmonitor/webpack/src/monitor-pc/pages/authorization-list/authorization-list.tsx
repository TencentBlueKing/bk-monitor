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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import {
  createOrUpdateAuthorizer,
  deleteExternalPermission,
  getApplyRecordList,
  getAuthorizerByBiz,
  getAuthorizerList,
  getByAction,
  getExternalPermissionList
} from '../../../monitor-api/modules/iam';
import { Debounce } from '../../../monitor-common/utils';
import BizSelect from '../../components/biz-select/biz-select';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import { ISpaceItem } from '../../types';
import CommonNavBar from '../monitor-k8s/components/common-nav-bar';

import AuthorizationDialog from './authorization-dialog';

import './authorization-list.scss';

const { i18n } = window;

export type AngleType = 'user' | 'resource' | 'approval';
type StatusType = 'all' | 'invalid' | 'available' | 'approval' | 'expired' | 'success' | 'failed';
enum TableColumnEnum {
  authorized_user = 'authorized_user',
  action_id = 'action_id',
  resources = 'resources',
  authorizer = 'authorizer',
  space_name = 'space_name',
  expire_time = 'expire_time',
  status = 'status',
  resource_id = 'resource_id',
  authorized_users = 'authorized_users'
}

interface ColumnItem {
  prop: TableColumnEnum;
  name: string;
  hidden?: boolean;
  authHidden?: boolean;
  props?: any;
}

interface UserListItem {
  authorized_user: string;
  authorizer: string;
  space_name: string;
  action_id: string;
  bk_biz_id: number;
  expire_time: string;
  resources: string[];
  status: Exclude<StatusType, 'all'>;
}
interface ResourceListItem {
  action_id: string;
  authorized_users: string[];
  authorizer: string;
  space_name: string;
  resource_id: string;
  status: Exclude<StatusType, 'all'>;
  expire_time?: string;
}

export interface EditModel {
  action_id: String;
  authorized_users: string[];
  resources: number[];
  expire_time?: string;
}

export const STATUS_LIST = [
  { id: 'all', name: i18n.tc('全部'), show: ['user', 'resource', 'approval'] },
  {
    id: 'available',
    name: i18n.tc('生效'),
    color1: '#3FC06D',
    color2: '#3FC06D29',
    show: ['user', 'resource']
  },
  { id: 'success', name: i18n.tc('审批成功'), color1: '#3FC06D', color2: '#3FC06D29', show: ['approval'] },
  { id: 'approval', name: i18n.tc('审批中'), color1: '#FF9C01', color2: '#FF9C0129', show: ['approval'] },
  { id: 'expired', name: i18n.tc('过期'), color1: '#979BA5', color2: '#979BA529', show: ['user', 'resource'] },
  { id: 'invalid', name: i18n.tc('失效'), color1: '#EA3636', color2: '#EA363629', show: ['user', 'resource'] },
  { id: 'failed', name: i18n.tc('审批失败'), color1: '#EA3636', color2: '#EA363629', show: ['approval'] }
];

export const ACTION_MAP = {
  view_grafana: '仪表盘查看'
};
@Component
// export default class AuthorizationList extends Mixins(authorityMixinCreate(ruleAuth)) {
export default class AuthorizationList extends tsc<{}, {}> {
  bizId = window.cc_biz_id;
  bizCMDBRoleList: string[] = []; // 该业务下的cmdb运维角色列表
  memberSelect = ''; // 展示的授权人
  memberValue = ''; // 编辑授权人输入框的值
  isEditMember = false; // 是否编辑授权人
  searchValue = ''; // 搜索关键字
  angleType: AngleType = 'user'; // 视角类型
  statusActive: StatusType = 'all'; // 状态类型
  totalListData: (UserListItem | ResourceListItem)[] = []; // 总列表数据
  // 列表Columns管理
  tableColumns: { [key in AngleType]: ColumnItem[] } = {
    user: [
      {
        prop: TableColumnEnum.authorized_user,
        name: i18n.tc('被授权人'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.action_id,
        name: i18n.tc('操作权限'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod, width: 200, formatter: this.actionFormatter }
      },
      {
        prop: TableColumnEnum.resources,
        name: i18n.tc('操作实例'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.authorizer,
        name: i18n.tc('授权人'),
        authHidden: true,
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.space_name,
        name: i18n.tc('所属空间'),
        authHidden: true,
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.expire_time,
        name: i18n.tc('截止时间'),
        hidden: false,
        props: { sortable: true, width: 200, formatter: this.timeFormatter }
      },
      {
        prop: TableColumnEnum.status,
        name: i18n.tc('状态'),
        hidden: false,
        props: { width: 140, formatter: this.statusFormatter }
      }
    ],
    resource: [
      {
        prop: TableColumnEnum.resource_id,
        name: i18n.tc('操作实例'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.action_id,
        name: i18n.tc('操作权限'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod, width: 200, formatter: this.actionFormatter }
      },
      {
        prop: TableColumnEnum.authorized_users,
        name: i18n.tc('被授权人'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.authorizer,
        name: i18n.tc('授权人'),
        authHidden: true,
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.space_name,
        name: i18n.tc('所属空间'),
        authHidden: true,
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.expire_time,
        name: i18n.tc('截止时间'),
        hidden: true,
        props: { sortable: true, width: 200, formatter: this.timeFormatter }
      },
      {
        prop: TableColumnEnum.status,
        name: i18n.tc('状态'),
        hidden: false,
        props: { width: 140, formatter: this.statusFormatter }
      }
    ],
    approval: [
      {
        prop: TableColumnEnum.authorized_users,
        name: i18n.tc('被授权人'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.action_id,
        name: i18n.tc('操作权限'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod, width: 200, formatter: this.actionFormatter }
      },
      {
        prop: TableColumnEnum.resources,
        name: i18n.tc('操作实例'),
        hidden: false,
        props: { filters: [], 'filter-method': this.filterMethod }
      },
      {
        prop: TableColumnEnum.expire_time,
        name: i18n.tc('截止时间'),
        hidden: false,
        props: { sortable: true, width: 200, formatter: this.timeFormatter }
      },
      {
        prop: TableColumnEnum.status,
        name: i18n.tc('状态'),
        hidden: false,
        props: { width: 140, formatter: this.statusFormatter }
      }
    ]
  };
  // 分页
  pagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  loading = false;
  resourcesLoading = true; // 操作实例loading
  resourceList = []; // 操作实例可选列表
  rowData: EditModel | null = null; // 编辑行数据
  emptyStatusType: EmptyStatusType = 'empty';
  visible = false;

  get bizIdList(): ISpaceItem[] {
    const { bizList } = this.$store.getters;
    return [
      ...(this.isSuperUser
        ? [
            {
              space_name: this.$t('全部'),
              py_text: 'all',
              id: 0,
              space_id: 0,
              bk_biz_id: 0,
              space_type_id: 'bkcc',
              space_uid: 'all',
              is_hidden_tag: true
            }
          ]
        : []),
      ...bizList
    ];
  }

  // 是否是admin用户
  get isSuperUser(): boolean {
    return this.$store.state.app.isSuperUser;
  }

  // 当前操作人是否有cmdb运维角色
  get hasCMDBRole(): boolean {
    const username = window.user_name || window.username;
    return this.bizCMDBRoleList.includes(username);
  }

  // 实际展示列表列
  get currentColumns() {
    return this.tableColumns[this.angleType].filter(item => !item.hidden && !item.authHidden);
  }

  // 实际展示的状态选项
  get currentStatus() {
    return STATUS_LIST.filter(item => item.show.includes(this.angleType));
  }

  // 经过筛选，分页后实际展示的列表数据
  get listData() {
    const filterList = this.totalListData.filter(item => {
      // 状态匹配
      const statusPick = this.statusActive === 'all' || item.status === this.statusActive;
      if (!this.searchValue || !statusPick) return statusPick;
      // 关键字匹配
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { status, expire_time, ...searchKey } = TableColumnEnum;
      // 可以匹配的字段
      return Object.keys(searchKey).some(key => {
        if (!item[key]) return false;
        const val = Array.isArray(item[key]) ? item[key] : [item[key]];
        if (key === TableColumnEnum.resources || key === TableColumnEnum.resource_id) {
          return val.some(id => {
            const { text } = this.resourceList.find(item => item.uid === id);
            return text.includes(this.searchValue);
          });
        }
        if (key === TableColumnEnum.action_id) {
          return val.some(key => ACTION_MAP[key].includes(this.searchValue));
        }
        return val.some(val => val.toString().includes(this.searchValue));
      });
    });
    const { current, limit } = this.pagination;
    return filterList.slice((current - 1) * limit, current * limit);
  }

  created() {
    this.bizId = this.$store.getters.bizId;
    this.getBizRoleList();
    this.getListData();
    this.getAuthUser();
  }

  /**
   *
   * @param v 业务id
   * @description 业务选择器选择业务时触发
   */
  handleBizChange(v: number) {
    this.bizId = v;
    this.getListData();
    this.getAuthUser();
    this.getBizRoleList();

    // 业务选择器选择全部选项时，才有权限展示该列
    Object.values(this.tableColumns).forEach(columns => {
      columns.forEach(column => {
        if (column.authHidden !== undefined) {
          column.authHidden = v !== 0;
        }
      });
    });
  }

  // 获取业务运维角色列表
  async getBizRoleList() {
    this.bizCMDBRoleList = await getAuthorizerList({ bk_biz_id: this.bizId });
  }

  // 获取授权人
  async getAuthUser() {
    this.memberSelect = await getAuthorizerByBiz({ bk_biz_id: this.bizId });
  }

  // 展示编辑授权人
  showMemberSelect() {
    this.memberValue = this.memberSelect;
    this.isEditMember = true;
  }

  // 创建、修改授权人
  async createOrUpdateAuthUser() {
    if (!this.memberValue) {
      this.$bkMessage({
        message: this.$t('不能为空'),
        theme: 'error'
      });
      return;
    }
    try {
      await createOrUpdateAuthorizer({ bk_biz_id: this.bizId, authorizer: this.memberValue });
      this.memberSelect = this.memberValue;
      this.isEditMember = false;
    } catch (err) {
      console.log(err);
    }
  }

  // 视角切换
  handleAngleTabChange(type: AngleType) {
    // 从用户或者资源视图切换到审批视图，状态变更为全部
    if ((this.angleType === 'resource' || this.angleType === 'user') && type === 'approval') {
      this.statusActive = 'all';
    }
    // 从审批视图切换到用户或者资源视图，状态同样变更为全部
    if (this.angleType === 'approval' && (type === 'user' || type === 'resource')) {
      this.statusActive = 'all';
    }
    this.angleType = type;
    this.getListData();
  }

  // 状态筛选切换
  handleStatusChange(statusType) {
    this.statusActive = statusType;
    this.changeEmptyStatusType();
  }

  // 关键字搜索
  @Debounce(300)
  handleSearchBlur(val) {
    this.searchValue = val;
    this.changeEmptyStatusType();
  }

  async getListData() {
    this.loading = true;
    this.pagination.current = 1;
    let res: [boolean, any];
    if (this.angleType === 'approval') {
      res = await this.getApprovalListData();
    } else {
      res = await this.getAuthListData();
    }
    const [isSuccess, data] = res;
    if (isSuccess) {
      this.totalListData = data;
      this.pagination.count = this.totalListData.length;
      this.getResources();
      this.emptyStatusType = 'empty';
      this.changeEmptyStatusType();
    } else {
      this.emptyStatusType = '500';
      this.totalListData = [];
      this.pagination.count = 0;
    }

    this.loading = false;
  }

  // 获取被授权人，操作实例tab栏的列表数据
  async getAuthListData(): Promise<[boolean, any]> {
    try {
      const res = await getExternalPermissionList({
        bk_biz_id: this.bizId,
        view_type: this.angleType
      });
      return [true, res];
    } catch (error) {
      return [false, []];
    }
  }

  // 获取审批记录tab栏的列表数据
  async getApprovalListData(): Promise<[boolean, any]> {
    try {
      const res = await getApplyRecordList({
        bk_biz_id: this.bizId
      });
      return [true, res];
    } catch (error) {
      return [false, []];
    }
  }

  async getResources() {
    this.resourcesLoading = true;
    try {
      // 目前后端只支持view_grafana， 也没有确定后续多个时，action_id的传值格式
      const res = await getByAction({ bk_biz_id: this.bizId, action_id: 'view_grafana' });
      this.resourceList = res;
      this.columnFilter();
    } catch (error) {
      this.resourceList = [];
    }
    this.resourcesLoading = false;
  }

  // 表格空状态操作
  changeEmptyStatusType() {
    if (this.emptyStatusType !== '500') {
      this.emptyStatusType = this.statusActive === 'all' && !this.searchValue ? 'empty' : 'search-empty';
    }
  }

  //  分页
  handlePageChange(page: number) {
    this.pagination.current = page;
  }
  handlePageLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
  }

  // 列表各字段的筛选项
  columnFilter() {
    this.tableColumns[this.angleType].forEach(item => {
      if (item.props.filters) {
        const set = new Set();
        const { prop } = item;
        this.totalListData.forEach(item => {
          const data = Array.isArray(item[prop]) ? item[prop] : [item[prop]];
          data.forEach(val => set.add(val));
        });
        // 操作实例列需要通过ID在resourceList找到匹配的text
        if (prop === TableColumnEnum.resource_id || prop === TableColumnEnum.resources) {
          item.props.filters = Array.from(set).map(id => ({
            text: this.resourceList.find(item => item.uid === id)?.text,
            value: id
          }));
        } else if (prop === TableColumnEnum.action_id) {
          item.props.filters = Array.from(set).map((id: string) => ({
            text: ACTION_MAP[id],
            value: id
          }));
        } else {
          item.props.filters = Array.from(set).map(item => ({ text: item, value: item }));
        }
      }
    });
  }

  // 列表表头筛选
  filterMethod(value, row, column) {
    const { property } = column;
    return Array.isArray(row[property]) ? row[property].includes(value) : row[property] === value;
  }

  handleSettingChange({ fields }) {
    this.tableColumns[this.angleType].forEach(item => {
      item.hidden = !fields.some(field => item.prop === field.prop);
    });
  }

  // 自定义列渲染
  renderColumn(column: ColumnItem) {
    if (column.prop === TableColumnEnum.authorized_users) {
      return (
        <bk-table-column
          key={column.prop}
          label={column.name}
          prop={column.prop}
          {...{
            props: column.props
          }}
          scopedSlots={{
            default: ({ row }) => (
              <div v-bk-overflow-tips={{ content: row.authorized_users?.join(',') }}>
                {row.authorized_users?.map(item => <bk-tag>{item}</bk-tag>)}
              </div>
            )
          }}
        />
      );
    }
    if (column.prop === TableColumnEnum.resources || column.prop === TableColumnEnum.resource_id) {
      return (
        <bk-table-column
          key={column.prop}
          label={column.name}
          prop={column.prop}
          {...{
            props: column.props
          }}
          scopedSlots={{
            default: ({ row }) => {
              if (column.prop === 'resources') {
                return (
                  <div v-bkloading={{ isLoading: this.resourcesLoading }}>
                    {row.resources?.map((id, ind) =>
                      ind < 3 || row.isExpand ? (
                        <div class='resource-item'>{this.resourceList.find(item => item.uid === id)?.text}</div>
                      ) : undefined
                    )}
                    {row.resources?.length > 3 && (
                      <p
                        class='expand-btn'
                        onClick={() => {
                          this.$set(row, 'isExpand', !row.isExpand);
                        }}
                      >
                        {row.isExpand ? this.$t('收起') : this.$t('展开')}
                      </p>
                    )}
                  </div>
                );
              }
              return (
                <div v-bkloading={{ isLoading: this.resourcesLoading }}>
                  <div>{this.resourceList.find(item => item.uid === row.resource_id)?.text}</div>
                </div>
              );
            }
          }}
        />
      );
    }

    return (
      <bk-table-column
        key={column.prop}
        label={column.name}
        prop={column.prop}
        {...{
          props: column.props
        }}
      />
    );
  }

  // 操作权限列格式化
  actionFormatter(row, column, cellValue) {
    return ACTION_MAP[cellValue];
  }
  /**
   *
   * @param color1 状态点颜色
   * @param color2 状态文字颜色
   * @returns 状态点
   */
  statusPoint(color1: string, color2) {
    return (
      <div
        class='status-point'
        style={{ background: color2 }}
      >
        <div
          class='point'
          style={{ background: color1 }}
        ></div>
      </div>
    );
  }

  // 状态列格式化
  statusFormatter(row, column, cellValue) {
    const item = STATUS_LIST.find(item => item.id === cellValue);
    return (
      <div class='status-wrap'>
        {this.statusPoint(item.color1, item.color2)}
        <span>{item.name}</span>
      </div>
    );
  }

  // 截止时间列格式化
  timeFormatter(row, column, cellValue) {
    return cellValue ? dayjs.tz(cellValue).format('YYYY-MM-DD HH:mm:ss') : '-';
  }
  /**
   *
   * @param row 行数据
   */
  async handleDelete(row) {
    try {
      await deleteExternalPermission({
        bk_biz_id: this.bizId,
        action_id: row.action_id,
        authorized_users: row.authorized_users || [row.authorized_user],
        resources: row.resources || [row.resource_id],
        view_type: this.angleType
      });
      this.getListData();
    } catch (error) {}
  }

  showDialog(row = null) {
    this.rowData = row && {
      action_id: row.action_id,
      authorized_users: row.authorized_users || [row.authorized_user],
      resources: row.resources || [row.resource_id],
      expire_time: row.expire_time || ''
    };
    this.visible = true;
  }

  emptyOperation(type: EmptyStatusOperationType) {
    if (type === 'refresh') {
      this.getListData();
      return;
    }
    if (type === 'clear-filter') {
      this.searchValue = '';
      this.statusActive = 'all';
    }
  }

  // 创建，修改成功跳转到审批记录tab栏
  handleSuccess(needApproval: boolean) {
    if (needApproval) this.angleType = 'approval';
    this.getListData();
  }

  render() {
    return (
      <div class='authorization-list-page'>
        <CommonNavBar>
          <div
            class='page-header'
            slot='custom'
          >
            <p class='page-title'>{this.$t('route-外部授权列表')}</p>
            <BizSelect
              value={+this.bizId}
              bizList={this.bizIdList}
              theme='light'
              isShowCommon={false}
              minWidth={310}
              onChange={this.handleBizChange}
            />
          </div>
        </CommonNavBar>

        <div class='page-content'>
          <bk-alert
            type='error'
            title={this.$t(
              '需遵循公司规范，禁止对外暴露用户或公司内部敏感信息（用户PII信息、账号密码、云AKSK、内部系统鉴权/Token、保密文档等），若因授权不当造成数据泄露须承担相应责任; '
            )}
          />

          <div class='authorization-header'>
            <span class='label'>{this.$t('授权人')}：</span>
            {this.isEditMember ? (
              <div class='member-select edit'>
                <bk-select
                  class='member-input'
                  v-model={this.memberValue}
                >
                  {this.bizCMDBRoleList.map(item => (
                    <bk-option
                      id={item}
                      name={item}
                    ></bk-option>
                  ))}
                </bk-select>
                <bk-button
                  class='member-btn'
                  text
                  title='primary'
                  onClick={this.createOrUpdateAuthUser}
                >
                  {this.$t('确定')}
                </bk-button>
                <bk-button
                  class='member-btn'
                  text
                  title='primary'
                  onClick={() => (this.isEditMember = false)}
                >
                  {this.$t('取消')}
                </bk-button>
              </div>
            ) : (
              <div class='member-select'>
                <p class='member'>{this.memberSelect}</p>
                {this.hasCMDBRole && (
                  <i
                    class='icon-monitor icon-bianji'
                    v-bk-tooltips={{
                      content: this.$t('变更授权人'),
                      placements: ['top']
                    }}
                    onClick={this.showMemberSelect}
                  />
                )}
              </div>
            )}
            <p class='hint'>
              <i class='icon-monitor icon-tixing'></i>
              <span>
                {this.$t('授权人的空间权限会影响被授权人，被授权人的权限范围<=授权人的权限范围，请谨慎变更。')}
              </span>
            </p>
          </div>

          <div class='authorization-table'>
            <div class='tools'>
              <div class='tool-left'>
                {
                  <bk-button
                    class='auth-btn'
                    theme='primary'
                    type='submit'
                    icon='plus'
                    disabled={!this.memberSelect}
                    onClick={() => this.showDialog()}
                  >
                    {this.$t('添加授权')}
                  </bk-button>
                }
                <div class='angle-tab'>
                  <div
                    class={['angle-tab-item', this.angleType === 'user' && 'active']}
                    onClick={() => this.handleAngleTabChange('user')}
                  >
                    {this.$t('被授权人')}
                  </div>
                  <div
                    class={['angle-tab-item', this.angleType === 'resource' && 'active']}
                    onClick={() => this.handleAngleTabChange('resource')}
                  >
                    {this.$t('操作实例')}
                  </div>
                  <div
                    class={['angle-tab-item', this.angleType === 'approval' && 'active']}
                    onClick={() => this.handleAngleTabChange('approval')}
                  >
                    {this.$t('审批记录')}
                  </div>
                </div>
              </div>

              <div class='tool-right'>
                <div class='status-list'>
                  {this.currentStatus.map((item, index) => (
                    <div
                      class={[
                        'status-list-item',
                        { active: this.statusActive === item.id },
                        {
                          'not-border':
                            this.statusActive === item.id || this.currentStatus[index + 1]?.id === this.statusActive
                        }
                      ]}
                      key={item.id}
                      onClick={() => this.handleStatusChange(item.id)}
                    >
                      {index !== 0 && this.statusPoint(item.color1, item.color2)}
                      <span>{item.name}</span>
                    </div>
                  ))}
                </div>

                <bk-input
                  value={this.searchValue}
                  onInput={this.handleSearchBlur}
                  class='search-input'
                  right-icon='bk-icon icon-search'
                ></bk-input>
              </div>
            </div>

            <div class='table-wrapper'>
              <bk-table
                v-bkloading={{ isLoading: this.loading }}
                row-auto-height
                data={this.listData}
                pagination={this.pagination}
                key={this.angleType}
                on-page-change={this.handlePageChange}
                on-page-limit-change={this.handlePageLimitChange}
                size='large'
              >
                <bk-table-column
                  label='ID'
                  width={105}
                  scopedSlots={{
                    default: ({ $index }) => (
                      <div>{(this.pagination.current - 1) * this.pagination.limit + $index + 1}</div>
                    )
                  }}
                />
                {this.currentColumns.map(column => this.renderColumn(column))}
                <bk-table-column
                  label={this.$t('操作')}
                  width={140}
                  scopedSlots={{
                    default: ({ row }) => (
                      <div>
                        {this.angleType === 'approval' ? (
                          <bk-button
                            text
                            onClick={() => window.open(row.approval_url)}
                          >
                            {this.$t('查看详情')}
                          </bk-button>
                        ) : (
                          [
                            <bk-button
                              text
                              style='margin-right: 16px'
                              onClick={() => this.showDialog(row)}
                            >
                              {this.$t('编辑')}
                            </bk-button>,
                            <bk-button
                              text
                              onClick={() => this.handleDelete(row)}
                            >
                              {this.$t('删除')}
                            </bk-button>
                          ]
                        )}
                      </div>
                    )
                  }}
                />
                <bk-table-column type='setting'>
                  <bk-table-setting-content
                    fields={this.tableColumns[this.angleType].filter(item => !item.authHidden)}
                    value-key='prop'
                    label-key='name'
                    selected={this.currentColumns}
                    on-setting-change={this.handleSettingChange}
                  ></bk-table-setting-content>
                </bk-table-column>

                <EmptyStatus
                  slot='empty'
                  type={this.emptyStatusType}
                  onOperation={this.emptyOperation}
                ></EmptyStatus>
              </bk-table>
            </div>
          </div>
        </div>

        <AuthorizationDialog
          v-model={this.visible}
          rowData={this.rowData}
          authorizer={this.memberSelect}
          viewType={this.angleType}
          bizId={this.bizId}
          onSuccess={this.handleSuccess}
        />
      </div>
    );
  }
}
