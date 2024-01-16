/* eslint-disable no-nested-ternary */
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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  addTaskUptimeCheckGroup,
  changeStatusUptimeCheckTask,
  cloneUptimeCheckTask,
  createUptimeCheckGroup,
  destroyUptimeCheckGroup,
  destroyUptimeCheckTask,
  listUptimeCheckTask,
  updateUptimeCheckGroup
} from '../../../monitor-api/modules/model';
import { Debounce } from '../../../monitor-common/utils/utils';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import { UPTIME_CHECK_LIST } from '../monitor-k8s//typings/tools';
import CommonTable from '../monitor-k8s/components/common-table';
import DeleteSubtitle from '../strategy-config/strategy-config-common/delete-subtitle';

import CardsContainer from './components/cards-container';
import GroupCard, { IOptionType as IGroupCardOperate } from './components/group-card';
import HeaderTools, { IClickType } from './components/header-tools';
import OperateOptions from './components/operate-options';
import TaskCard, { IData as ItaskItem, IOptionTypes as ITaskCardOperate } from './components/task-card';
import UploadContent from './components/upload-content';
import UptimeCheckEmpty from './uptime-check-task/uptime-check-empty/uptime-check-empty.vue';
import UptimeCheckImport from './uptime-check-task/uptime-check-import/uptime-check-import.vue';
import { IActive as IUptimeCheckType } from './uptime-check';
import {
  getGroupToTaskData,
  groupDataTaskInit,
  groupDialogDataInit,
  groupNameValidate,
  IDragStatus,
  IGroupDataTask,
  isTaskDisable,
  ITaskData,
  ITaskTableData,
  paginationUtil,
  searchGroupData,
  searchTaskData,
  tableAvailableProcessColor,
  taskCommonTableProps,
  taskDataInit,
  taskDataToTableData,
  taskStatusMap,
  taskStatusTextColor,
  taskSwitch,
  taskSwitchDisabled,
  taskTableDataInit
} from './uptime-check-data';

import './uptime-check-task.scss';

interface IUptimeCheckTaskProps {
  isCard?: boolean;
  nodeName?: string;
  refreshKey?: string;
}

interface IUptimeCheckTaskEvents {
  onLoading?: boolean;
  onRefresh?: IUptimeCheckType;
  onNodeNameChange?: (v: string) => void;
  onGroupStatus?: (v: boolean) => void;
}

@Component({
  name: 'UptimeCheckTask'
})
export default class UptimeCheckTask extends tsc<IUptimeCheckTaskProps, IUptimeCheckTaskEvents> {
  @Prop({ type: Boolean, default: true }) isCard: boolean;
  @Prop({ type: String, default: '' }) nodeName: string;
  @Prop({ type: String, default: '' }) refreshKey: string;
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  data: ITaskData = taskDataInit();
  taskTableData: ITaskTableData = taskTableDataInit([]); // 任务表格数据
  // 拖拽状态管理
  dragStatus: IDragStatus = {
    taskId: 0, // 拖拽中的拨测任务id
    dragging: false // 是否拖拽中
  };

  // 点击任务组展开的任务数据
  groupDataTask: IGroupDataTask = groupDataTaskInit();

  // 任务组弹窗数据
  groupDialogData = groupDialogDataInit();

  // 搜索
  searchValue = '';

  // 导入侧栏显示
  isShowImport = false;

  //
  isTableSort = false;
  sortTableData = [];

  emptyStatusType: EmptyStatusType = 'empty';

  // 搜索数据
  get searchTaskData(): ITaskData['task_data'] {
    return searchTaskData(this.searchValue, this.data.task_data);
  }
  get searchGroupData(): ITaskData['group_data'] {
    return searchGroupData(this.searchValue, this.data.group_data);
  }
  get searchGroupToTaskData(): IGroupDataTask['tasks'] {
    return searchTaskData(this.searchValue, this.groupDataTask.tasks);
  }
  get isShowNodata(): boolean {
    if (this.groupDataTask.show) {
      return !this.searchGroupToTaskData.length;
    }
    return !this.searchTaskData.length && !this.searchGroupData.length;
  }

  @Watch('refreshKey')
  handleRefresh() {
    this.init();
  }

  activated() {
    this.init();
  }
  deactivated() {}
  async init() {
    this.handleLoading(true);
    const data = await listUptimeCheckTask({
      get_available: true,
      get_task_duration: true,
      get_groups: true,
      ordering: '-id'
    });
    this.handleLoading(false);
    this.data = data;
    this.taskTableData = taskTableDataInit(data.task_data);
    this.searchValue = this.nodeName ? `${this.$t('节点:')}${this.nodeName}` : this.searchValue || '';

    setTimeout(() => {
      const { query } = this.$route;
      this.searchValue = this.searchValue || query.queryString?.toString() || '';
      this.handleSearch(this.searchValue, true);
      this.handleNodeNameChange('');
    }, 100);
  }

  @Emit('nodeNameChange')
  handleNodeNameChange(v: string) {
    return v;
  }

  @Emit('groupStatus')
  handleTaskGroupStatus() {
    return this.groupDataTask.show;
  }

  handleMenuSelectChange(v: IGroupCardOperate) {
    this.handleGroupCardOperate(v, this.groupDataTask.groupId);
  }

  /**
   * @description: 拖拽状态切换
   * @param {IDragStatus} v
   * @return {*}
   */
  handleDragStatus(v: IDragStatus) {
    this.dragStatus = JSON.parse(JSON.stringify(v));
  }
  /**
   * @description: 拖入至任务组卡片中触发
   * @param {object} v
   * @return {*}
   */
  async handleDropItem(v: { groupId: number; taskId: number }) {
    const curGroup = this.data.group_data.find(item => item.id === v.groupId);
    const curTask = this.data.task_data.find(item => item.id === v.taskId);
    const noCanAdd = curGroup.all_tasks.map(item => String(item.task_id)).includes(String(curTask.id));
    if (noCanAdd) return;
    this.handleLoading(true);
    const res = await addTaskUptimeCheckGroup(v.groupId, { id: v.groupId, task_id: v.taskId }).catch(() => false);
    this.handleLoading(false);
    if (res) {
      const taskItem = {
        available: curTask.available,
        name: curTask.name,
        status: curTask.status,
        task_id: curTask.id
      };
      curGroup.all_tasks.push(taskItem);
      if (curGroup.top_three_tasks.length < 3) {
        curGroup.top_three_tasks.push(taskItem);
      }
    }
  }

  /**
   * @description: 点击头部选项时
   * @param {*}
   * @return {*}
   */
  handleHeaderCreate(v: IClickType) {
    switch (v) {
      case 'createTask': // 创建拨测
        this.$router.push({
          name: 'uptime-check-task-add',
          params: {
            title: this.$tc('新建拨测任务')
          },
          query: {
            groupId: String(this.groupDataTask.groupId)
          }
        });
        break;
      case 'createGroup': // 创建任务组
        this.groupDialogData.show = true;
        break;
      case 'import': // 导入
        this.isShowImport = true;
        break;
    }
  }

  // loading
  @Emit('loading')
  handleLoading(v: boolean) {
    return v;
  }

  // 新增任务组时的校验
  handleCreateGroupDataValidate() {
    const groupData = this.data.group_data.find(item => item.id === Number(this.groupDialogData.data.groupId));
    const groupNames = this.groupDialogData.isEdit
      ? this.data.group_data.map(item => item.name).filter(item => item !== groupData.name)
      : this.data.group_data.map(item => item.name);
    const validateStatus = groupNameValidate(this.groupDialogData.data.name, groupNames);
    this.groupDialogData.errMsg.name = validateStatus.message;
    return validateStatus.validate;
  }
  // 任务组名称输入框失焦时触发
  @Debounce(300)
  handleGroupDialogBlur() {
    this.groupDialogData.validate = this.handleCreateGroupDataValidate();
  }
  // 获取焦点时
  handleGroupDialogFocus() {
    this.groupDialogData.errMsg.name = '';
  }
  // 关闭新建任务组弹窗
  handleCloseGroupData() {
    this.groupDialogData.show = false;
    this.groupDialogData = groupDialogDataInit();
  }
  // 提交任务组数据
  async handleSubmitGroupData() {
    const params = {
      add: !this.groupDialogData.isEdit,
      bk_biz_id: this.$store.getters.bizId,
      id: '',
      logo: this.groupDialogData.data.img,
      name: this.groupDialogData.data.name,
      task_id_list: this.groupDialogData.data.tasks
    };
    this.handleLoading(true);
    if (this.groupDialogData.isEdit) {
      params.id = this.groupDialogData.data.groupId;
      const res = await updateUptimeCheckGroup(params.id, params, { needRes: true })
        .then(res => res)
        .catch(() => false);
      this.handleCloseGroupData();
      this.handleLoading(false);
      if (res.result) {
        this.$bkMessage({
          message: this.$t('编辑成功'),
          theme: 'success'
        });
        this.handleRefreshData();
        // 分组里编辑当前任务组
        if (this.groupDataTask.show) {
          this.groupDataTask.groupName = res.data.name;
          this.groupDataTask.tasks = res.data.tasks;
        }
      }
      return;
    }
    const res = await createUptimeCheckGroup(params, { needRes: true })
      .then(res => res.result)
      .catch(() => false);
    this.handleCloseGroupData();
    this.handleLoading(false);
    if (res) {
      this.$bkMessage({
        message: this.$t('创建成功'),
        theme: 'success'
      });
      this.handleRefreshData();
    }
  }
  // 任务组卡片操作
  handleGroupCardOperate(v: IGroupCardOperate, groupId: number) {
    const groupData = this.data.group_data.find(item => item.id === groupId);
    switch (v) {
      case 'edit':
        this.groupDialogData = groupDialogDataInit();
        this.groupDialogData.data = {
          img: groupData.logo,
          tasks: groupData.all_tasks.map(item => Number(item.task_id)),
          name: groupData.name,
          groupId: `${groupData.id}`
        };
        this.groupDialogData.validate = false;
        this.groupDialogData.isEdit = true;
        this.groupDialogData.show = true;
        break;
      case 'delete':
        this.$bkInfo({
          title: this.$t('确定解散任务组'),
          subTitle: this.$t('该操作仅删除任务组，不会影响组内拨测任务'),
          confirmFn: async () => {
            this.handleLoading(true);
            const res = await destroyUptimeCheckGroup(groupData.id, {}, { needRes: true })
              .then(res => res.result)
              .catch(() => false);
            this.handleLoading(false);
            this.$bkMessage({
              message: res ? this.$t('解散任务组成功') : this.$t('解散任务组失败'),
              theme: res ? 'success' : 'error'
            });
            // 分组里解散任务组
            if (res && this.groupDataTask.show) {
              this.groupDataTask = groupDataTaskInit();
            }
            this.handleRefreshData();
          }
        });
        break;
    }
  }
  // 任务卡片操作
  async handleTaskCardOperate(v: ITaskCardOperate, taskId: number) {
    const taskData = this.data.task_data.find(item => item.id === taskId);
    const status = isTaskDisable(taskData.status) ? 'running' : 'stoped';
    let statusRes = '';
    let cloneRes = false;
    let delRes = false;
    switch (v) {
      case 'edit':
        this.$router.push({
          name: 'uptime-check-task-edit',
          params: {
            id: String(taskData.id),
            bizId: String(taskData.bk_biz_id)
          }
        });
        break;
      case 'delete':
        this.$bkInfo({
          type: 'warning',
          title: this.$t('确认要删除？'),
          subHeader: this.$createElement(DeleteSubtitle, {
            props: {
              title: this.$tc('任务名'),
              name: taskData.name
            }
          }),
          maskClose: true,
          escClose: true,
          confirmFn: async () => {
            this.handleLoading(true);
            delRes = await destroyUptimeCheckTask(taskData.id, {}, { needRes: true })
              .then(res => res.result)
              .catch(() => false);
            this.handleLoading(false);
            this.$bkMessage({
              theme: delRes ? 'success' : 'error',
              message: delRes ? this.$t('删除任务成功！') : this.$t('删除任务失败！')
            });
            this.handleRefreshData();
          }
        });
        break;
      case 'clone':
        this.handleLoading(true);
        cloneRes = await cloneUptimeCheckTask(taskData.id, {}, { needRes: true })
          .then(res => res.result)
          .catch(() => false);
        this.handleLoading(false);
        this.$bkMessage({
          theme: cloneRes ? 'success' : 'error',
          message: cloneRes ? this.$t('克隆任务成功！') : this.$t('克隆任务失败!')
        });
        this.handleRefreshData();
        break;
      case 'enable':
      case 'stop':
        this.handleLoading(true);
        statusRes = await changeStatusUptimeCheckTask(taskData.id, { status })
          .then(res => res.status)
          .catch(() => false);
        this.handleLoading(false);
        statusRes &&
          this.$bkMessage({
            theme: 'success',
            message: this.$t(statusRes === 'running' ? '任务启动成功' : '任务停止成功')
          });
        this.handleRefreshData();
        break;
    }
  }
  // 点击任务组卡片
  handleGroupCardClick(id: number) {
    const groupData = this.data.group_data.find(item => item.id === id);
    this.groupDataTask.tasks = getGroupToTaskData(groupData.all_tasks, this.data.task_data);
    this.groupDataTask.show = true;
    this.groupDataTask.groupName = groupData.name;
    this.groupDataTask.groupId = groupData.id;
    this.handleTaskGroupStatus();
  }
  // 点击任务卡片
  handleTaskCardClick(id: number) {
    const taskData = this.data.task_data.find(item => item.id === id);
    this.$router.push({
      name: this.groupDataTask.groupId ? 'uptime-check-group-detail' : 'uptime-check-task-detail',
      params: {
        taskId: String(taskData.id),
        groupId: String(this.groupDataTask.groupId)
      }
    });
  }
  // 返回到拨测任务
  handleBackGroup() {
    this.groupDataTask = groupDataTaskInit();
    this.handleTaskGroupStatus();
  }

  // 重新加载数据
  @Emit('refresh')
  handleRefreshData() {
    return UPTIME_CHECK_LIST[0].id;
  }

  // 搜索
  handleSearch(v: string, isInit = false) {
    this.emptyStatusType = v ? 'search-empty' : 'empty';
    this.searchValue = v;
    const pagination = {
      ...this.taskTableData.pagination,
      count: this.searchTaskData.length,
      current: 1
    };
    this.taskTableData.pagination = pagination;
    this.taskTableData.data = taskDataToTableData(paginationUtil(pagination, this.searchTaskData));

    const params = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        queryString: v.trim?.().length ? v : undefined
      }
    };
    if (!isInit) {
      this.$router.replace(params).catch(() => {});
    }
  }
  // 点击任务名称
  handleTaskNameClick(id: number) {
    this.$router.push({
      name: 'uptime-check-task-detail',
      params: {
        taskId: String(id)
      }
    });
  }
  // 点击表格中的启停时
  handleTaskSwitchChange(v: boolean) {
    this.$bkMessage({
      theme: 'success',
      message: v ? this.$t('任务启动成功') : this.$t('任务停止成功')
    });
    this.handleRefreshTableData();
  }

  // 刷新表格数据
  async handleRefreshTableData() {
    const data = await listUptimeCheckTask({
      get_available: true,
      get_task_duration: true,
      get_groups: false,
      ordering: '-id'
    });
    this.data.task_data = data.task_data;
    await this.$nextTick();
    const pagination = {
      count: this.searchTaskData.length,
      current: 1,
      limit: 10
    };
    this.taskTableData.pagination = pagination;
    this.taskTableData.data = taskDataToTableData(paginationUtil(pagination, this.searchTaskData));
  }

  // 启停开关的前置接口调用
  taskSwitchChangePreCheck(id: number, status: string) {
    return new Promise((resolve, reject) => {
      if (!this.authority.MANAGE_AUTH) {
        this.handleShowAuthorityDetail(this.authorityMap?.MANAGE_AUTH);
        reject();
      }
      changeStatusUptimeCheckTask(id, { status: taskSwitch(status) ? 'stoped' : 'running' })
        .then(() => {
          resolve(true);
        })
        .catch(() => {
          reject();
        });
    });
  }
  // 任务列表分页
  handleTaskTablePageChange(v) {
    const pagination = {
      count: this.searchTaskData.length,
      current: v,
      limit: this.taskTableData.pagination.limit
    };
    this.taskTableData.pagination = pagination;
    this.taskTableData.data = taskDataToTableData(
      paginationUtil(pagination, this.isTableSort ? this.sortTableData : this.searchTaskData)
    );
  }
  handleTaskTableLimitChange(v) {
    const pagination = {
      count: this.searchTaskData.length,
      current: 1,
      limit: v
    };
    this.taskTableData.pagination = pagination;
    this.taskTableData.data = taskDataToTableData(
      paginationUtil(pagination, this.isTableSort ? this.sortTableData : this.searchTaskData)
    );
  }

  // 列表排序
  handleSortChange(v: { prop: string; order: 'descending' | 'ascending' | null }) {
    const columnId = v.prop;
    const { order } = v; // ascending: 升序
    let taskData = [];
    const pagination = {
      count: this.searchTaskData.length,
      current: 1,
      limit: 10
    };
    if (order) {
      switch (columnId as 'task_duration_text' | 'available_progress') {
        case 'available_progress': // 可用率
          taskData = [...this.searchTaskData].sort((a, b) => {
            if (order === 'ascending') {
              return a.available - b.available;
            }
            return b.available - a.available;
          });
          break;
        case 'task_duration_text': // 响应时长
          taskData = [...this.searchTaskData].sort((a, b) => {
            if (order === 'ascending') {
              return a.task_duration - b.task_duration;
            }
            return b.task_duration - a.task_duration;
          });
          break;
      }
      this.isTableSort = true;
      this.sortTableData = taskData;
    } else {
      taskData = this.searchTaskData;
      this.isTableSort = false;
      this.sortTableData = [];
    }
    this.taskTableData.pagination = pagination;
    this.taskTableData.data = taskDataToTableData(paginationUtil(pagination, taskData));
  }

  handleEmptyCreate(v: 'create' | 'import' | 'createNode') {
    switch (v) {
      case 'create':
        this.$router.push({
          name: 'uptime-check-task-add',
          params: {
            title: this.$tc('新建拨测任务')
          }
        });
        break;
      case 'createNode':
        this.$router.push({
          name: 'uptime-check-node-add'
        });
        break;
      case 'import':
        this.isShowImport = true;
        break;
    }
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchValue = '';
      this.handleSearch('');
      return;
    }
    this.handleRefreshTableData();
  }

  render() {
    return (
      <div class='uptime-check-task-component'>
        {!this.data.group_data.length && !this.data.task_data.length ? (
          <UptimeCheckEmpty
            is-node={!this.data.has_node}
            on-create={() => this.handleEmptyCreate('create')}
            on-import={() => this.handleEmptyCreate('import')}
            on-create-node={() => this.handleEmptyCreate('createNode')}
          ></UptimeCheckEmpty>
        ) : this.isCard ? (
          this.getCardData()
        ) : (
          this.getTableData()
        )}
        {this.getDialogContent()}
        <UptimeCheckImport
          options={{ isShow: this.isShowImport }}
          on-close={() => (this.isShowImport = false)}
          on-complete={this.handleRefreshData}
        ></UptimeCheckImport>
      </div>
    );
  }

  // 表格容器
  getTableData() {
    return (
      <div class='table-data-content'>
        <HeaderTools
          option={{ showTask: true, showImport: true }}
          search={this.searchValue}
          onCreate={this.handleHeaderCreate}
          onSearch={(v: string) => this.handleSearch(v)}
        ></HeaderTools>
        <CommonTable
          style={{ marginTop: '16px' }}
          {...{ props: taskCommonTableProps }}
          data={this.taskTableData.data}
          pagination={this.taskTableData.pagination}
          scopedSlots={{
            operate: (row: ItaskItem) => (
              <OperateOptions
                options={{
                  outside: [
                    {
                      id: 'edit',
                      name: window.i18n.tc('button-编辑'),
                      authority: this.authority.MANAGE_AUTH,
                      authorityDetail: this.authorityMap.MANAGE_AUTH
                    },
                    {
                      id: 'delete',
                      name: window.i18n.tc('删除'),
                      authority: this.authority.MANAGE_AUTH,
                      authorityDetail: this.authorityMap.MANAGE_AUTH
                    }
                  ],
                  popover: [
                    {
                      id: 'clone',
                      name: window.i18n.tc('克隆'),
                      authority: this.authority.MANAGE_AUTH,
                      authorityDetail: this.authorityMap.MANAGE_AUTH
                    }
                  ]
                }}
                onOptionClick={(v: ITaskCardOperate) => this.handleTaskCardOperate(v, row.id)}
              ></OperateOptions>
            ),
            name: (row: ItaskItem) => (
              <span
                class='task-name'
                onClick={() => this.handleTaskNameClick(row.id)}
              >
                {row.name}
              </span>
            ),
            enable: (row: ItaskItem) => (
              <bk-switcher
                value={taskSwitch(row.status)}
                disabled={taskSwitchDisabled(row.status)}
                size={'small'}
                theme={'primary'}
                preCheck={() => this.taskSwitchChangePreCheck(row.id, row.status)}
                on-change={this.handleTaskSwitchChange}
              ></bk-switcher>
            ),
            statusText: (row: ItaskItem) => (
              <span style={{ color: taskStatusTextColor(row.status) }}>{taskStatusMap[row.status]}</span>
            ),
            progress: (row: ItaskItem) => (
              <div>
                {<div>{row.available !== null ? `${row.available}%` : '--'}</div>}
                <bk-progress
                  color={tableAvailableProcessColor(row.available, row.status)}
                  showText={false}
                  percent={Number((row.available * 0.01).toFixed(2)) || 0}
                ></bk-progress>
              </div>
            )
          }}
          onPageChange={this.handleTaskTablePageChange}
          onLimitChange={this.handleTaskTableLimitChange}
          onSortChange={this.handleSortChange}
        >
          <EmptyStatus
            type={this.emptyStatusType}
            slot='empty'
            onOperation={this.handleOperation}
          />
        </CommonTable>
      </div>
    );
  }
  // 卡片容器
  getCardData() {
    return (
      <div class='card-data-content'>
        <HeaderTools
          search={this.searchValue}
          onCreate={this.handleHeaderCreate}
          onSearch={(v: string) => this.handleSearch(v)}
        ></HeaderTools>
        {this.groupDataTask.show ? (
          this.searchGroupToTaskData.length ? (
            <CardsContainer style={{ marginTop: '20px' }}>
              <span
                slot='title'
                class='card-container-header'
              >
                <span
                  class='header-btn'
                  onClick={this.handleBackGroup}
                >
                  {this.$t('拨测任务')}
                </span>
                <span class='header-arrow'>{'>'}</span>
                <span class='header-name'>{this.groupDataTask.groupName}</span>
              </span>
              {this.searchGroupToTaskData.map(item => (
                <TaskCard
                  data={item}
                  onCardClick={(id: number) => this.handleTaskCardClick(id)}
                  onOperate={(v: ITaskCardOperate) => this.handleTaskCardOperate(v, item.id)}
                ></TaskCard>
              ))}
            </CardsContainer>
          ) : undefined
        ) : (
          [
            this.searchGroupData.length ? (
              <CardsContainer
                title={this.$tc('拨测任务组')}
                style={{ marginTop: '20px' }}
                showSeeAll
              >
                {this.searchGroupData.map(item => (
                  <GroupCard
                    data={item}
                    dragStatus={this.dragStatus}
                    onDropItem={v => this.handleDropItem(v)}
                    onOperate={(v: IGroupCardOperate) => this.handleGroupCardOperate(v, item.id)}
                    onCardClick={(id: number) => this.handleGroupCardClick(id)}
                  ></GroupCard>
                ))}
              </CardsContainer>
            ) : undefined,
            this.searchTaskData.length ? (
              <CardsContainer
                title={this.$tc('拨测任务')}
                style={{ marginTop: '12px' }}
              >
                {this.searchTaskData.map(item => (
                  <TaskCard
                    data={item}
                    onDragStatus={(v: IDragStatus) => this.handleDragStatus(v)}
                    onCardClick={(id: number) => this.handleTaskCardClick(id)}
                    onOperate={(v: ITaskCardOperate) => this.handleTaskCardOperate(v, item.id)}
                  ></TaskCard>
                ))}
              </CardsContainer>
            ) : undefined
          ]
        )}
        {this.isShowNodata ? (
          <EmptyStatus
            type={this.emptyStatusType}
            onOperation={this.handleOperation}
          />
        ) : undefined}
      </div>
    );
  }
  // 弹窗容器
  getDialogContent() {
    return (
      <bk-dialog
        class='uptime-check-small-dialog'
        value={this.groupDialogData.show}
        title={this.$t('新建拨测任务组')}
        headerPosition={'left'}
        width={480}
        on-cancel={this.handleCloseGroupData}
      >
        <div class='dialog-form-content'>
          <bk-form
            formType={'vertical'}
            class='form-content'
          >
            <bk-form-item
              label={this.$t('任务组名称')}
              required={true}
            >
              <bk-input
                v-model={this.groupDialogData.data.name}
                placeholder={this.$t('输入拨测任务组名称')}
                on-blur={this.handleGroupDialogBlur}
                on-focus={this.handleGroupDialogFocus}
                on-change={this.handleGroupDialogBlur}
              ></bk-input>
              {this.groupDialogData.errMsg.name ? (
                <span class='errmsg'>{this.groupDialogData.errMsg.name}</span>
              ) : undefined}
            </bk-form-item>
            <bk-form-item label={this.$t('选择拨测任务')}>
              <bk-select
                v-model={this.groupDialogData.data.tasks}
                style={{ width: '320px' }}
                placeholder={this.$t('选择拨测任务')}
                multiple
              >
                {this.data.task_data.map(item => (
                  <bk-option
                    id={item.id}
                    name={item.name}
                    key={item.id}
                  ></bk-option>
                ))}
              </bk-select>
            </bk-form-item>
          </bk-form>
          <div class='upload-content'>
            <UploadContent
              imgSrc={this.groupDialogData.data.img}
              onChangeImg={(img: string) => (this.groupDialogData.data.img = img)}
            ></UploadContent>
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            style={{ marginRight: '5px' }}
            disabled={this.groupDialogData.validate}
            on-click={this.handleSubmitGroupData}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button on-click={this.handleCloseGroupData}>{this.$t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  }
}
