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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { Alert as Alert, Tag as Tag } from 'tdesign-vue-next';

import { MessagePlugin as TDesignMessage, Button as TButton, Button as Button } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import BizMenuSelect from '@/shared/global/bk-space-choice/index';
import { Checkbox, CheckboxGroup, Select, Option, Input, Popup, Skeleton, Table } from 'tdesign-vue-next';
import { SearchIcon, SettingIcon } from 'tdesign-icons-vue-next';
import { allocateOverlayZIndex } from '@/shared/global/overlay/use-overlay-z-index';
import type { CheckboxGroupValue, FilterValue, PageInfo, PrimaryTableCol, SortInfo, TableSort } from 'tdesign-vue-next';
import dayjs from 'dayjs';

import * as authorityMap from '../../shared/lib/authority-map';
import EmptyStatus from '../../shared/ui/empty-status/index.vue';
import ManagementListLoading from '@/shared/ui/loading/management-list-loading';
import AuthorizationDialog from './authorization-dialog';

import './authorization-list.scss';

const { $i18n } = window.mainComponent;

// 空状态类型枚举
export type EmptyStatusType = '403' | '500' | 'empty' | 'search-empty';
// 空状态操作枚举
export type EmptyStatusOperationType = 'clear-filter' | 'refresh';
export type AngleType = 'approval' | 'resource' | 'user';
type StatusType = 'all' | 'approval' | 'available' | 'expired' | 'failed' | 'invalid' | 'success';
enum TableColumnEnum {
  action_id = 'action_id',
  authorized_user = 'authorized_user',
  authorized_users = 'authorized_users',
  authorizer = 'authorizer',
  created_at = 'created_at',
  expire_time = 'expire_time',
  resource_id = 'resource_id',
  resources = 'resources',
  space_name = 'space_name',
  status = 'status',
}

interface ColumnItem {
  prop: TableColumnEnum;
  name: string;
  hidden?: boolean;
  authHidden?: boolean;
  props?: any;
  minWidth?: number;
}

export type ResourceId = string | number;
export interface ResourceOption { id: ResourceId; uid: ResourceId; text: string; }
interface AuthorizationFields {
  authorized_user?: string;
  authorized_users?: string[];
  resources?: ResourceId[];
  resource_id?: ResourceId;
  approval_url?: string;
  created_at?: string;
}
export interface UserListItem extends AuthorizationFields {
  authorized_user: string;
  authorizer: string;
  space_name: string;
  action_id: string;
  bk_biz_id: number;
  expire_time: string;
  resources: ResourceId[];
  status: Exclude<StatusType, 'all'>;
}
export interface ResourceListItem extends AuthorizationFields {
  action_id: string;
  authorized_users: string[];
  authorizer: string;
  space_name: string;
  resource_id: string;
  status: Exclude<StatusType, 'all'>;
  expire_time?: string;
}

type AuthorizationRow = (ResourceListItem | UserListItem) & { rowKey: string; isExpand?: boolean };

export interface EditModel {
  action_id: string;
  authorized_users: string[];
  resources: ResourceId[];
  expire_time?: string;
  action_multiple?: string[];
  actionShowList?: any[];
}

export const STATUS_LIST = [
  { id: 'all', name: $i18n.t('全部'), show: ['user', 'resource', 'approval'] },
  {
    id: 'available',
    name: $i18n.t('生效'),
    color1: 'var(--bklog-status-success)',
    color2: 'var(--bklog-status-success-ring)',
    show: ['user', 'resource'],
  },
  { id: 'success', name: $i18n.t('审批成功'), color1: 'var(--bklog-status-success)', color2: 'var(--bklog-status-success-ring)', show: ['approval'] },
  { id: 'approval', name: $i18n.t('审批中'), color1: 'var(--bklog-status-warning-accent)', color2: 'var(--bklog-status-warning-ring)', show: ['approval'] },
  { id: 'expired', name: $i18n.t('过期'), color1: 'var(--bklog-standard-control-border)', color2: 'var(--bklog-standard-control-border)', show: ['user', 'resource'] },
  { id: 'invalid', name: $i18n.t('失效'), color1: 'var(--bklog-status-error)', color2: 'var(--bklog-status-error-ring)', show: ['user', 'resource'] },
  { id: 'failed', name: $i18n.t('审批失败'), color1: 'var(--bklog-status-error)', color2: 'var(--bklog-status-error-ring)', show: ['approval'] },
];

export const ACTION_MAP = {
  view_grafana: '仪表盘查看',
};

@Component
export default class AuthorizationList extends tsc<object> {
  spaceUid = '';
  actionList: (({ id: string; name: string; }))[] = [];
  bizCMDBRoleList: string[] = []; // 该业务下的cmdb运维角色列表
  memberSelect = ''; // 展示的授权人
  memberValue = ''; // 编辑授权人输入框的值
  isEditMember = false; // 是否编辑授权人
  searchInputValue = ''; // 输入框即时值
  searchValue = ''; // 防抖后的列表搜索关键字
  searchTimer: ReturnType<typeof window.setTimeout> | null = null;
  columnFilters: Record<string, (number | string)[]> = {}; // 表头列筛选条件（key 为列 prop）
  angleType: AngleType = 'user'; // 视角类型
  statusActive: StatusType = 'all'; // 状态类型
  totalListData: AuthorizationRow[] = []; // 总列表数据
  sortInfo: SortInfo | null = null; // 不能初始化为 undefined：类组件会丢弃 undefined 字段，导致排序状态失去响应式
  // 列表Columns管理
  tableColumns: { [key in AngleType]: ColumnItem[] } = {
    user: [
      {
        prop: TableColumnEnum.authorized_user,
        name: $i18n.t('被授权人'),
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.action_id,
        name: $i18n.t('操作权限'),
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.resources,
        name: $i18n.t('操作实例'),
        hidden: false,
        props: { width: 200, minWidth: 200, filters: [] },
      },
      {
        prop: TableColumnEnum.authorizer,
        name: $i18n.t('授权人'),
        authHidden: true,
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.space_name,
        name: $i18n.t('所属空间'),
        authHidden: true,
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.expire_time,
        name: $i18n.t('截止时间'),
        hidden: false,
        props: { sortable: true, width: 200, formatter: this.timeFormatter },
      },
      {
        prop: TableColumnEnum.status,
        name: $i18n.t('状态'),
        hidden: false,
        props: { width: 140, formatter: this.statusFormatter },
      },
    ],
    resource: [
      {
        prop: TableColumnEnum.resource_id,
        name: $i18n.t('操作实例'),
        hidden: false,
        props: { width: 200, minWidth: 200, filters: [] },
      },
      {
        prop: TableColumnEnum.action_id,
        name: $i18n.t('操作权限'),
        hidden: false,
        props: { filters: [], width: 200, minWidth: 120 },
      },
      {
        prop: TableColumnEnum.authorized_users,
        name: $i18n.t('被授权人'),
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.authorizer,
        name: $i18n.t('授权人'),
        authHidden: true,
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.space_name,
        name: $i18n.t('所属空间'),
        authHidden: true,
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.expire_time,
        name: $i18n.t('截止时间'),
        hidden: true,
        props: { sortable: true, width: 200, formatter: this.timeFormatter },
      },
      {
        prop: TableColumnEnum.status,
        name: $i18n.t('状态'),
        hidden: false,
        props: { width: 140, formatter: this.statusFormatter },
      },
    ],
    approval: [
      {
        prop: TableColumnEnum.authorized_users,
        name: $i18n.t('被授权人'),
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.action_id,
        name: $i18n.t('操作权限'),
        hidden: false,
        props: { width: 120, minWidth: 120, filters: [] },
      },
      {
        prop: TableColumnEnum.resources,
        name: $i18n.t('操作实例'),
        hidden: false,
        props: { filters: [], width: 200, minWidth: 200 },
      },
      {
        prop: TableColumnEnum.created_at,
        name: $i18n.t('创建时间'),
        hidden: false,
        props: { sortable: true, width: 200, formatter: this.timeFormatter },
      },
      {
        prop: TableColumnEnum.expire_time,
        name: $i18n.t('截止时间'),
        hidden: false,
        props: { sortable: true, width: 200, formatter: this.timeFormatter },
      },
      {
        prop: TableColumnEnum.status,
        name: $i18n.t('状态'),
        hidden: false,
        props: { width: 140, formatter: this.statusFormatter },
      },
    ],
  };
  // 分页
  pagination = {
    current: 1,
    pageSize: 10,
  };
  loading = false;
  resourcesLoading = true; // 操作实例loading
  resourceList: ResourceOption[] = []; // 操作实例可选列表
  resourceMaps: Record<string, ResourceOption[]> = {}; // 多个操作实例映射列表
  rowData: EditModel | null = null; // 编辑行数据
  emptyStatusType: EmptyStatusType = 'empty';
  visible = false;
  columnSettingVisible = false;
  columnSettingDraft: CheckboxGroupValue = [];
  columnSettingZIndex: number | undefined = undefined;
  abortController: AbortController | undefined = undefined;

  // // 是否是admin用户
  // get isSuperUser(): boolean {
  //   return this.$store.state.app.isSuperUser;
  // }

  // 当前操作人是否有cmdb运维角色
  get hasCMDBRole(): boolean {
    const username = useApplicationStore().userMeta?.username ?? '';
    return this.bizCMDBRoleList.includes(username);
  }

  // 实际展示列表列
  get currentColumns() {
    return this.tableColumns[this.angleType].filter(item => !(item.hidden || item.authHidden));
  }

  get settingColumns() {
    return this.tableColumns[this.angleType].filter(column => !column.authHidden);
  }

  get isAllColumnsChecked() {
    return this.settingColumns.every(column => this.columnSettingDraft.includes(column.prop));
  }

  get displayColumns() {
    return ['serial', ...this.currentColumns.map(column => column.prop), 'operation', 'setting'];
  }

  get nativeColumns(): PrimaryTableCol[] {
    return [
      {
        colKey: 'serial',
        title: 'ID',
        width: 105,
        cell: (_h, { rowIndex }) => String((this.pagination.current - 1) * this.pagination.pageSize + rowIndex + 1),
      },
      ...this.tableColumns[this.angleType].filter(column => !column.authHidden).map(column => this.renderColumn(column)),
      {
        colKey: 'operation',
        title: this.$t('操作'),
        width: 140,
        cell: (_h, { row }) => this.renderOperation(row as AuthorizationRow),
      },
      {
        colKey: 'setting',
        title: () => this.renderColumnSetting(),
        width: 40,
        align: 'center',
        cell: () => '',
      },
    ];
  }

  // 实际展示的状态选项
  get currentStatus() {
    return STATUS_LIST.filter(item => item.show.includes(this.angleType));
  }

  // 经过表头列筛选、状态和关键字筛选后的列表
  get filteredListData() {
    return this.totalListData.filter(item => {
      // 表头列筛选匹配（如操作权限、操作实例），作用于全量数据
      const columnPick = Object.entries(this.columnFilters).every(([prop, values]) => {
        if (!values?.length) {
          return true;
        }
        const cell = (item as Record<string, any>)[prop];
        return values.some(value => (Array.isArray(cell) ? cell.includes(value) : cell === value));
      });
      if (!columnPick) {
        return false;
      }
      // 状态匹配
      const statusPick = this.statusActive === 'all' || item.status === this.statusActive;
      if (!(this.searchValue && statusPick)) {
        return statusPick;
      }
      // 关键字匹配
      const { status: _status, expire_time: _expireTime, created_at: _createdAt, ...searchKey } = TableColumnEnum;
      return Object.keys(searchKey).some(rawKey => {
        const key = rawKey as keyof typeof searchKey;
        if (!item[key]) {
          return false;
        }
        const val = Array.isArray(item[key]) ? item[key] : [item[key]];
        if (key === TableColumnEnum.resources || key === TableColumnEnum.resource_id) {
          return val.some(id => {
            const resourceList = this.resourceMaps[item[TableColumnEnum.action_id]] || [];
            const rItem = resourceList.find((r: { id: any; }) => r.id === id);
            return rItem?.text?.includes(this.searchValue) ?? false;
          });
        }
        if (key === TableColumnEnum.action_id) {
          return val.some(id => {
            const aItem = this.actionList.find(aItem => aItem.id === id);
            return aItem?.name?.includes(this.searchValue) ?? false;
          });
        }
        return val.some(newVal => newVal.toString().includes(this.searchValue));
      });
    });
  }

  // 经过筛选、排序，分页后实际展示的列表数据
  get listData() {
    const { current, pageSize } = this.pagination;
    const data = [...this.filteredListData];
    if (this.sortInfo) {
      const { sortBy, descending } = this.sortInfo;
      const key = sortBy as 'created_at' | 'expire_time';
      data.sort((left, right) => {
        const leftTime = left[key] ? dayjs(left[key]).valueOf() : 0;
        const rightTime = right[key] ? dayjs(right[key]).valueOf() : 0;
        return (leftTime - rightTime) * (descending ? -1 : 1);
      });
    }
    return data.slice((current - 1) * pageSize, current * pageSize);
  }

  get tablePagination() {
    return {
      ...this.pagination,
      total: this.filteredListData.length,
    };
  }

  async created() {
    this.spaceUid = useApplicationStore().spaceUid;
    const hasManageAuth = await this.checkBizAllow();
    if (hasManageAuth) {
      this.angleType = (this.$route.query?.activeNav as AngleType) || 'user';
      this.getBizRoleList();
      await this.getActionList();
      this.getListData();
      this.getAuthUser();
    }
  }

  beforeDestroy() {
    this.clearSearchTimer();
  }

  async checkBizAllow() {
    try {
      const res = await useApplicationStore().checkAndGetData({
        action_ids: [authorityMap.VIEW_BUSINESS],
        resources: [
          {
            type: 'space',
            id: this.spaceUid,
          },
        ],
      });
      if (res.isAllowed === false) {
        useApplicationStore().updateState({ authDialogData: res.data });
        return false;
      }
      return true;
    } catch (e) {
      console.warn(e);
      return false;
    }
  }

  async getActionList() {
    const res = await ServicesInstance.authorization.getActionList();
    this.actionList = res?.data || [];
    this.getResources();
  }

  /**
   *
   * @param v 空间uid
   * @description 业务选择器选择业务时触发
   */
  async handleSpaceChange(v: string) {
    this.spaceUid = v;
    // this.$store.commit('updateSpace', v);
    const hasManageAuth = await this.checkBizAllow();
    // 空间切换后数据整体变化，清空原有列筛选
    this.resetColumnFilters();
    this.getResources();
    if (hasManageAuth) {
      this.getListData();
      this.getAuthUser();
      this.getBizRoleList();
    }

    // 业务选择器选择全部选项时，才有权限展示该列
    // Object.values(this.tableColumns).forEach((columns) => {
    //   columns.forEach((column) => {
    //     if (column.authHidden !== undefined) {
    //       column.authHidden = v !== 0;
    //     }
    //   });
    // });
  }

  // 获取业务运维角色列表
  async getBizRoleList() {
    const res = await ServicesInstance.authorization.getAuthorizerList({
      query: {
        space_uid: this.spaceUid,
      },
    });
    this.bizCMDBRoleList = res.data || [];
  }

  // 获取授权人
  async getAuthUser() {
    const res = await ServicesInstance.authorization.getAuthorizer({
      query: {
        space_uid: this.spaceUid,
      },
    });
    this.memberSelect = res.data || '';
  }

  // 展示编辑授权人
  showMemberSelect() {
    this.memberValue = this.memberSelect;
    this.isEditMember = true;
  }

  // 创建、修改授权人
  async createOrUpdateAuthUser() {
    if (!this.memberValue) {
      TDesignMessage("error", { content: this.$t('不能为空') });
      return;
    }
    try {
      await ServicesInstance.authorization.createOrUpdateAuthorizer({
        data: {
          space_uid: this.spaceUid,
          maintainer: this.memberValue,
        },
      });
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
    this.sortInfo = null;
    // 切换视角后表格重建，清空上一视角的列筛选条件
    this.columnFilters = {};
    this.$router.replace({
      query: {
        activeNav: type,
      },
    });
    this.getListData();
  }

  // 状态筛选切换
  handleStatusChange(statusType: StatusType) {
    this.statusActive = statusType;
    this.pagination.current = 1;
    this.changeEmptyStatusType();
  }

  clearSearchTimer() {
    if (this.searchTimer !== null) {
      window.clearTimeout(this.searchTimer);
      this.searchTimer = null;
    }
  }

  // 受控输入值立即回写，仅延迟列表筛选。
  handleSearchChange(val: string) {
    this.searchInputValue = val;
    this.clearSearchTimer();
    this.searchTimer = window.setTimeout(() => {
      this.searchTimer = null;
      this.searchValue = val;
      this.pagination.current = 1;
      this.changeEmptyStatusType();
    }, 300);
  }

  async handleListDataAsync() {
    this.loading = true;
    this.pagination.current = 1;
    let res: [boolean, any];
    this.abortController = new AbortController();

    if (this.angleType === 'approval') {
      res = await this.getApprovalListData(this.abortController.signal);
    } else {
      res = await this.getAuthListData(this.abortController.signal);
    }
    const [isSuccess, data] = res;
    if (isSuccess) {
      this.totalListData = data.map((row: ResourceListItem | UserListItem, index: number) => ({
        ...row,
        rowKey: `${this.angleType}-${index}`,
      }));
      // 数据就绪后重建表头筛选项（created 阶段首次构建时列表为空，会导致筛选下拉无选项）
      this.columnFilter();
      this.emptyStatusType = 'empty';
      this.changeEmptyStatusType();
    } else {
      this.emptyStatusType = '500';
      this.totalListData = [];
    }

    this.loading = false;
  }
  getListData() {
    this.abortController?.abort();

    setTimeout(() => {
      this.handleListDataAsync();
    });
  }

  // 获取被授权人，操作实例tab栏的列表数据
  async getAuthListData(signal: AbortSignal): Promise<[boolean, any]> {
    try {
      const res = await ServicesInstance.authorization.getExternalPermissionList(
        {
          query: {
            space_uid: this.spaceUid,
            view_type: this.angleType,
          },
        },
        { signal },
      );
      return [true, res?.data ?? []];
    } catch (error) {
      if (error && typeof error === 'object' && 'code' in error && error.code === 'ERR_CANCELED') {
        console.warn('请求已取消');
        return [true, []];
      }
      return [false, []];
    }
  }

  // 获取审批记录tab栏的列表数据
  async getApprovalListData(signal: AbortSignal): Promise<[boolean, any]> {
    try {
      const res = await ServicesInstance.authorization.getApplyRecordList(
        {
          query: {
            space_uid: this.spaceUid,
          },
        },
        { signal },
      );
      return [true, res?.data ?? []];
    } catch (error) {
      if (error && typeof error === 'object' && 'code' in error && error.code === 'ERR_CANCELED') {
        console.warn('请求已取消');
        return [true, []];
      }
      return [false, []];
    }
  }

  async getResources() {
    this.resourcesLoading = true;
    try {
      await Promise.all(
        this.actionList.map(async item => {
          const res = await ServicesInstance.authorization.getByAction({
            query: {
              space_uid: this.spaceUid,
              action_id: item.id,
            },
          });
          this.$set(this.resourceMaps, item.id, res?.data || []);
        }),
      );
    } catch {
      this.resourceMaps = {};
    } finally {
      this.resourcesLoading = false;
    }
    // 操作实例列筛选项的文本依赖 resourceMaps，全部就绪后重建一次筛选项
    this.columnFilter();
  }

  // 表格空状态操作
  changeEmptyStatusType() {
    if (this.emptyStatusType !== '500') {
      const hasColumnFilter = Object.values(this.columnFilters).some(values => values.length);
      this.emptyStatusType =
        this.statusActive === 'all' && !this.searchValue && !hasColumnFilter ? 'empty' : 'search-empty';
    }
  }

  handlePageChange({ current, pageSize }: PageInfo) {
    this.pagination.current = pageSize === this.pagination.pageSize ? current : 1;
    this.pagination.pageSize = pageSize;
  }

  handleSortChange(sort: TableSort) {
    // 取消排序时 TDesign 会回传 undefined，这里统一收敛为 null，避免响应式字段再次变回 undefined
    this.sortInfo = (Array.isArray(sort) ? sort[0] : sort) ?? null;
    this.pagination.current = 1;
  }

  getFilterConfig(prop: TableColumnEnum, set: Set<any>) {
    for (const newItem of this.totalListData) {
      const data = Array.isArray(newItem[prop]) ? newItem[prop] : [newItem[prop]];
      for (const val of data) {
        if (prop === TableColumnEnum.resource_id || prop === TableColumnEnum.resources) {
          // set.add(`${item[TableColumnEnum.action_id]}-${val}`);
          set.add({ id: val, action: newItem[TableColumnEnum.action_id] });
        } else {
          set.add(val);
        }
      }
    }
  }
  updateFilter(prop: string, valSet: any[]) {
    if (prop === TableColumnEnum.resource_id || prop === TableColumnEnum.resources) {
      // 按「操作-实例」去重；resourceMaps 未就绪时用 id 兜底，避免对 undefined 取 find 报错
      const existKeys = new Set<string>();
      return valSet
        .filter((obj: { id: ResourceId; action: string }) => {
          const key = `${obj.action}-${obj.id}`;
          if (existKeys.has(key)) {
            return false;
          }
          existKeys.add(key);
          return true;
        })
        .map((obj: { id: ResourceId; action: string }) => ({
          text: this.resourceMaps[obj.action]?.find(rItem => rItem.id === obj.id || rItem.uid === obj.id)?.text ?? String(obj.id),
          value: obj.id,
        }));
    }
    if (prop === TableColumnEnum.action_id) {
      return valSet.map((id: string) => ({
        text: this.actionList.find(aItem => aItem.id === id)?.name ?? id,
        value: id,
      }));
    }
    return valSet.map(fItem => ({ text: fItem, value: fItem }));
  }
  // 列表各字段的筛选项
  columnFilter() {
    for (const item of this.tableColumns[this.angleType]) {
      if (item.props.filters) {
        const set = new Set();
        const { prop } = item;
        this.getFilterConfig(prop, set);
        // 操作实例列需要通过ID在resourceList找到匹配的text
        item.props.filters = this.updateFilter(prop, Array.from(set));
      }
    }
  }

  handleFilterChange(filters: FilterValue) {
    this.columnFilters = Object.fromEntries(
      Object.entries(filters).filter(([, values]) => Array.isArray(values) && values.length),
    );
    this.pagination.current = 1;
    this.changeEmptyStatusType();
  }

  resetColumnFilters() {
    this.columnFilters = {};
  }

  @Watch('angleType')
  closeColumnSetting() {
    this.columnSettingVisible = false;
  }

  handleColumnSettingVisibleChange(visible: boolean) {
    if (visible) {
      this.columnSettingDraft = this.currentColumns.map(column => column.prop);
      this.columnSettingZIndex = allocateOverlayZIndex('DROPDOWN');
    }
    this.columnSettingVisible = visible;
  }

  handleColumnSettingSelectAll(checked: boolean) {
    this.columnSettingDraft = checked ? this.settingColumns.map(column => column.prop) : [];
  }

  confirmColumnSetting() {
    for (const column of this.settingColumns) {
      column.hidden = !this.columnSettingDraft.includes(column.prop);
    }
    this.closeColumnSetting();
  }

  renderColumnSetting() {
    return (
      <Popup
        key={this.angleType}
        visible={this.columnSettingVisible}
        trigger='click'
        placement='bottom-right'
        showArrow
        zIndex={this.columnSettingZIndex}
        overlayInnerClassName='authorization-column-setting-popup'
        onVisibleChange={this.handleColumnSettingVisibleChange}
        content={() => (
          <div class='authorization-column-setting'>
            <div class='authorization-column-setting__content'>
              <div class='authorization-column-setting__title'>{this.$t('表格设置')}</div>
              <div class='authorization-column-setting__heading'>
                <span>{this.$t('字段显示设置')}</span>
                <Checkbox
                  checked={this.isAllColumnsChecked}
                  indeterminate={this.columnSettingDraft.length > 0 && !this.isAllColumnsChecked}
                  onChange={this.handleColumnSettingSelectAll}
                >
                  {this.$t('全选')}
                </Checkbox>
              </div>
              <CheckboxGroup
                class='authorization-column-setting__fields'
                value={this.columnSettingDraft}
                onChange={value => { this.columnSettingDraft = value; }}
              >
                {this.settingColumns.map(column => (
                  <Checkbox key={column.prop} value={column.prop}>{column.name}</Checkbox>
                ))}
              </CheckboxGroup>
            </div>
            <div class='authorization-column-setting__actions'>
              <TButton theme='primary' size='small' onClick={this.confirmColumnSetting}>
                {this.$t('确认')}
              </TButton>
              <TButton variant='outline' size='small' onClick={this.closeColumnSetting}>
                {this.$t('取消')}
              </TButton>
            </div>
          </div>
        )}
      >
        <button type='button' class='authorization-column-setting-trigger' aria-label={this.$t('表格设置')}>
          <SettingIcon />
        </button>
      </Popup>
    );
  }

  renderColumn(column: ColumnItem): PrimaryTableCol {
    const { filters, sortable, width, minWidth } = column.props;
    return {
      colKey: column.prop,
      title: column.name,
      width,
      minWidth,
      sorter: sortable,
      filter: filters ? {
        type: 'multiple',
        showConfirmAndReset: true,
        style: {
          maxHeight: '250px',
          overflowY: 'auto',
        },
        list: filters.map(({ text, value }: { text: string; value: ResourceId }) => ({ label: text, value })),
      } : undefined,
      cell: (_h, { row }) => this.renderCell(row as AuthorizationRow, column.prop),
    };
  }

  renderCell(row: AuthorizationRow, prop: TableColumnEnum) {
    if (prop === TableColumnEnum.authorized_users) {
      return (
        <div v-log-overflow-tips={{ content: row.authorized_users?.join(',') }}>
          {row.authorized_users?.map(item => (
            <Tag key={item} class='user-tag' variant='light' data-v2-display='tag'>
              {item}
            </Tag>
          ))}
        </div>
      );
    }
    if (prop === TableColumnEnum.resources || prop === TableColumnEnum.resource_id) {
      if (this.resourcesLoading) {
        return <Skeleton animation='gradient' rowCol={[{ type: 'text', width: '70%' }]} />;
      }
      const resourceList = this.resourceMaps[row.action_id] || [];
      const resourceName = (id: ResourceId | undefined) => resourceList.find(item => item.id === id || item.uid === id)?.text;
      if (prop === TableColumnEnum.resources) {
        const resources = row.resources;
        return (
          <div>
            {resources?.map((id, index) => index < 3 || row.isExpand ? (
              <div key={id} class='resource-item'>{resourceName(id)}</div>
            ) : undefined)}
            {resources && resources.length > 3 && (
              <p class='expand-btn' onClick={() => { row.isExpand = !row.isExpand; }}>
                {row.isExpand ? this.$t('收起') : this.$t('展开')}
              </p>
            )}
          </div>
        );
      }
      return (
        <div>{resourceName(row.resource_id)}</div>
      );
    }
    if (prop === TableColumnEnum.action_id) {
      return <div>{this.actionList.find(item => item.id === row.action_id)?.name}</div>;
    }
    if (prop === TableColumnEnum.status) {
      return this.statusFormatter(row, undefined, row.status);
    }
    if (prop === TableColumnEnum.expire_time || prop === TableColumnEnum.created_at) {
      return this.timeFormatter(row, undefined, row[prop]);
    }
    return row[prop];
  }

  renderOperation(row: AuthorizationRow) {
    return (
      <div class='authorization-row-actions'>
        {this.angleType === 'approval' ? (
          <TButton theme='primary' variant='text' onClick={() => window.open(row.approval_url)}>
            {this.$t('查看详情')}
          </TButton>
        ) : (
          <>
            <TButton
              theme='primary'
              variant='text'
              disabled={row.status === 'expired' || row.status === 'invalid'}
              onClick={() => this.showDialog(row)}
            >
              {this.$t('编辑')}
            </TButton>
            <TButton theme='primary' variant='text' onClick={() => this.handleDelete(row)}>
              {this.$t('删除')}
            </TButton>
          </>
        )}
      </div>
    );
  }

  /**
   *
   * @param color1 状态点颜色
   * @param color2 状态点外圈颜色
   * @returns 状态点
   */
  statusPoint(color1: string | undefined, color2: string | undefined) {
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

  // 状态列格式化
  statusFormatter(_row: unknown, _column: unknown, cellValue: string) {
    const item = STATUS_LIST.find(sItem => sItem.id === cellValue)!;
    return (
      <div class='status-wrap'>
        {this.statusPoint(item?.color1, item?.color2)}
        <span>{item.name}</span>
      </div>
    );
  }

  // 截止时间列格式化
  timeFormatter(_row: unknown, _column: unknown, cellValue: string|number|Date|dayjs.Dayjs|null|undefined) {
    return cellValue ? dayjs(cellValue).format('YYYY-MM-DD HH:mm:ss') : '-';
  }
  /**
   *
   * @param row 行数据
   */
  async handleDelete(row: UserListItem | ResourceListItem) {
    try {
      await ServicesInstance.authorization.deleteExternalPermission({
        data: {
          space_uid: this.spaceUid,
          action_id: row.action_id,
          authorized_users: row.authorized_users || [row.authorized_user!],
          resources: row.resources || [row.resource_id!],
          view_type: this.angleType,
        },
      });
      this.getListData();
    } catch {
      // 删除失败时保留当前列表，错误由请求层统一处理
    }
  }

  showDialog(row: UserListItem | ResourceListItem | null = null) {
    this.rowData = row && {
      action_id: row.action_id,
      authorized_users: row.authorized_users || [row.authorized_user!],
      resources: row.resources || [row.resource_id!],
      expire_time: row.expire_time || '',
    };

    this.visible = true;
  }

  emptyOperation(type: EmptyStatusOperationType) {
    if (type === 'refresh') {
      this.getListData();
      return;
    }
    if (type === 'clear-filter') {
      this.clearSearchTimer();
      this.searchInputValue = '';
      this.searchValue = '';
      this.statusActive = 'all';
      this.pagination.current = 1;
      this.resetColumnFilters();
      this.changeEmptyStatusType();
    }
  }

  // 创建，修改成功跳转到审批记录tab栏
  handleSuccess(needApproval: boolean) {
    if (needApproval) {
      this.angleType = 'approval';
    }
    this.getListData();
  }

  render() {
    return (
      <div class='authorization-list-page'>
        <div class='nav-bar'>
          <p class='page-title'>{this.$t('外部授权列表')}</p>
          <BizMenuSelect
            theme='light'
            isExternalAuth
            onSpaceChange={this.handleSpaceChange}
          />
        </div>

        <div class='page-content'>
          <Alert
            message={this.$t(
              '需遵循公司规范，禁止对外暴露用户或公司内部敏感信息（用户PII信息、账号密码、云AKSK、内部系统鉴权/Token、保密文档等），若因授权不当造成数据泄露须承担相应责任; ',
            )}
            theme={'error'} data-v2-display='alert'
          />

          <div class='authorization-header'>
            <span class='label'>{this.$t('授权人')}：</span>
            {this.isEditMember ? (
              <div class='member-select edit'>
                <Select
                  class='member-input'
                  v-model={this.memberValue}
                  searchable
                >
                  {this.bizCMDBRoleList.map(item => (
                    <Option
                      id={item}
                      key={item}
                      name={item}
                    />
                  ))}
                </Select>
                <Button
                  class='member-btn'
                  {...({ title: 'primary' } satisfies import('vue').HTMLAttributes)}

                  onClick={this.createOrUpdateAuthUser} variant={(true) ? 'text' : ('base')}
                >
                  {this.$t('确定')}
                </Button>
                <Button theme="default"
                  class='member-btn'
                  {...({ title: 'primary' } satisfies import('vue').HTMLAttributes)}

                  onClick={() => (this.isEditMember = false)} variant={(true) ? 'text' : ('base')}
                >
                  {this.$t('取消')}
                </Button>
              </div>
            ) : (
              <div class='member-select'>
                <p class='member'>{this.memberSelect}</p>
                {this.hasCMDBRole && (
                  <i
                    class='bk-icon icon-edit-line'
                    v-log-tooltip={{
                      content: this.$t('变更授权人'),
                      placements: ['top'],
                    }}
                    onClick={this.showMemberSelect}
                  />
                )}
              </div>
            )}
            <p class='hint'>
              <i class='icon-monitor icon-tixing' />
              <span>
                {this.$t('授权人的空间权限会影响被授权人，被授权人的权限范围<=授权人的权限范围，请谨慎变更。')}
              </span>
            </p>
          </div>

          <div class='authorization-table'>
            <div class='tools'>
              <div class='tool-left'>
                {
                  <Button
                    class='auth-btn'
                    disabled={!this.memberSelect}
                    icon={() => <span class={`bk-icon icon-${'plus'}`} />}
                    theme='primary'
                    type='submit'
                    onClick={() => this.showDialog()}
                  >
                    {this.$t('添加授权')}
                  </Button>
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
                      key={item.id}
                      class={[
                        'status-list-item',
                        { active: this.statusActive === item.id },
                        {
                          'not-border':
                            this.statusActive === item.id || this.currentStatus[index + 1]?.id === this.statusActive,
                        },
                      ]}
                      onClick={() => this.handleStatusChange(item.id)}
                    >
                      {index !== 0 && this.statusPoint(item?.color1, item?.color2)}
                      <span>{item.name}</span>
                    </div>
                  ))}
                </div>

                <Input
                  class='search-input'
                  suffixIcon={() => <SearchIcon />}
                  value={this.searchInputValue}
                  onChange={value => this.handleSearchChange(String(value))}
                />
              </div>
            </div>

            <ManagementListLoading class='table-wrapper' loading={this.loading}>
              <Table
                v-slots={{
                  empty: () => (
                    <div class='bklog-table-empty-region'>
                      {!this.loading && (
                        <EmptyStatus emptyType={this.emptyStatusType} onOperation={this.emptyOperation} />
                      )}
                    </div>
                  ),
                }}
                key={this.angleType}
                rowKey='rowKey'
                columns={this.nativeColumns}
                displayColumns={this.displayColumns}
                data={this.listData}
                disableDataPage
                filterValue={this.columnFilters}
                filterRow={() => ''}
                sort={this.sortInfo ?? undefined}
                maxHeight={600}
                pagination={this.tablePagination}
                size='large'
                onFilterChange={this.handleFilterChange}
                onPageChange={this.handlePageChange}
                onSortChange={this.handleSortChange}
              />
            </ManagementListLoading>
          </div>
        </div>

        <AuthorizationDialog
          v-model={this.visible}
          actionList={this.actionList}
          authorizer={this.memberSelect}
          rowData={this.rowData}
          spaceUid={this.spaceUid}
          viewType={this.angleType}
          onSuccess={this.handleSuccess}
        />
      </div>
    );
  }
}
