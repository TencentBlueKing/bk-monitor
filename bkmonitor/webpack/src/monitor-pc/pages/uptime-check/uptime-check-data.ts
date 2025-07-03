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
import { commonPageSizeGet } from 'monitor-common/utils';
import { padIPv6 } from 'monitor-common/utils/ip-utils';
import { deepClone } from 'monitor-common/utils/utils';

import { allSpaceRegex, emojiRegex } from '../../utils/index';

import type { ICommonTableProps } from '../monitor-k8s/components/common-table';
import type { IData as IGroupData, ITaskItem as IGroupDataTaskItem } from './components/group-card';
import type { IData as ITaskCardData } from './components/task-card';

export interface ITaskData {
  group_data: IGroupData[]; // 任务组数据
  has_node: boolean;
  task_data: ITaskCardData[]; // 任务数据
}
// 初始化数据
export const taskDataInit = (): ITaskData => ({
  group_data: [],
  has_node: false,
  task_data: [],
});

// 拖拽时的状态
export interface IDragStatus {
  taskId: number;
  dragging: boolean;
}

// 任务组命名校验
export const groupNameValidate = (
  targetStr: string,
  allName: string[]
): {
  validate: boolean;
  message: string;
} => {
  const validateStatus = {
    validate: false,
    message: '',
  };
  // 字符长度校验
  if (!targetStr.length || allSpaceRegex(targetStr)) {
    validateStatus.validate = true;
    validateStatus.message = window.i18n.tc('输入拨测任务组名称');
  }
  // 特殊字符校验
  if (/["/[\]':;|=,+*?<>{}.\\]+/g.test(targetStr)) {
    validateStatus.validate = true;
    validateStatus.message = `${window.i18n.t(
      '不允许包含如下特殊字符：'
    )} " / \\ [ ]' : ; | = , + * ? < > { } ${window.i18n.t('空格')}`;
    return validateStatus;
  }
  // 不能重名
  if (allName.map(item => item.toLowerCase()).indexOf(targetStr.toLowerCase(), 0) > -1) {
    validateStatus.validate = true;
    validateStatus.message = window.i18n.tc('注意: 名字冲突');
    return validateStatus;
  }
  if (emojiRegex(targetStr)) {
    validateStatus.validate = true;
    validateStatus.message = window.i18n.tc('不能输入emoji表情');
    return validateStatus;
  }
  return validateStatus;
};

export interface IGroupDialogData {
  show: boolean; // 是否展示弹窗
  data: { name: string; tasks: number[]; img: string; groupId?: string }; // 表单数据
  errMsg: { [propName: string]: string }; // 校验提示
  validate: boolean; // 校验是否通过
  isEdit?: boolean; // 是否为编辑
}
// 新建任务组弹窗数据初始化
export const groupDialogDataInit = (): IGroupDialogData => ({
  show: false,
  data: { name: '', tasks: [], img: '', groupId: '' },
  errMsg: {
    name: '',
  },
  validate: true,
  isEdit: false,
});

// 点击任务组拿出任务详细数据组
export const getGroupToTaskData = (groupTasks: IGroupDataTaskItem[], taskData: ITaskCardData[]) => {
  const resultTasks = [];
  const taskDataObj = {};
  taskData.forEach(item => {
    taskDataObj[item.id] = item;
  });
  groupTasks.forEach(item => {
    resultTasks.push(deepClone(taskDataObj[item.task_id]));
  });
  return resultTasks;
};

// 单个任务组下所有任务数据
export interface IGroupDataTask {
  show: boolean;
  tasks: ITaskCardData[];
  groupName: string;
  groupId: number;
}
export const groupDataTaskInit = (): IGroupDataTask => ({
  show: false,
  tasks: [],
  groupName: '',
  groupId: 0,
});

// 搜索task
export const searchTaskData = (searchValue: string, tasks: ITaskCardData[]): ITaskCardData[] => {
  if (searchValue.includes('节点:')) {
    const searchData = [];
    const [, keyword] = searchValue.trim().split('节点:');
    tasks.forEach(item => {
      const node = item.nodes.find(node => node.name === keyword);
      node && searchData.push(item);
    });
    return searchData;
  }
  const searchData = searchValue === '' ? tasks : tasks.filter(item => ~item.name.indexOf(searchValue));
  return searchData;
};
// 搜索group
export const searchGroupData = (searchValue: string, groups: IGroupData[]): IGroupData[] => {
  if (searchValue.includes('节点:')) return [];
  const searchData = searchValue === '' ? groups : groups.filter(item => ~item.name.indexOf(searchValue));
  return searchData;
};

// 拨测任务组卡片进度条颜色
export const processColor = (num: number) => {
  if (num >= 99) {
    return 'rgb(45, 203, 86)'; // 绿色
  }
  if (num >= 95 && num < 99) {
    return 'rgb(255, 235, 0)'; // 黄色
  }
  if (num >= 80 && num < 95) {
    return 'rgb(255, 156, 1)'; // 橙色
  }
  return 'rgb(234, 54, 54)'; // 红色
};

// 任务表格可用率进度条颜色
export const tableAvailableProcessColor = (available: number, status: string) => {
  if (available === null && status === 'stoped') {
    return '#C4C6CC';
  }
  if (available <= 100 && available >= 99) {
    return '#2dcb56';
  }
  if (available < 99 && available >= 95) {
    return '#ffeb00';
  }
  if (available < 95 && available >= 90) {
    return '#ff9c01';
  }
  return '#ea3436';
};

// 任务卡片平均响应时长及可用率数字颜色
export const filterTaskAlarmColor = (num: null | number, isAlarm: boolean) => {
  if (isAlarm) {
    return '#ea3436';
  }
  if (num === null) {
    return '#C4C6CC';
  }
  return '#313238';
};

// 任务状态对应颜色及文案
export const taskStatusMap = {
  running: window.i18n.tc('运行中'),
  stoped: window.i18n.tc('未启用'),
  start_failed: window.i18n.tc('启动失败'),
  stop_failed: window.i18n.tc('停止失败'),
  starting: window.i18n.tc('启动中'),
  stoping: window.i18n.tc('停止中'),
  new_draft: window.i18n.tc('未保存'),
};
// 格式化任务状态过滤列表
export const formatTaskStatusMapFilter = () => {
  const filter = [];
  Object.keys(taskStatusMap).map(key =>
    filter.push({
      text: taskStatusMap[key],
      value: key,
    })
  );
  return filter;
};

export const taskStatusTextColor = (taskStatus: string) => {
  if (taskStatus === 'stoped') {
    return '#c7c7c7';
  }
  if (['start_failed', 'stop_failed'].includes(taskStatus)) {
    return '#EA3636';
  }
  return '#63656E';
};

// 判断拨测任务是否为停用状态
export const isTaskDisable = (status: string) => !['running', 'stop_failed'].includes(status);

// 拨测任务启停状态
export const taskSwitch = (status: string) => ['running', 'stop_failed'].includes(status);
// 是否可点击启停开关
export const taskSwitchDisabled = (status: string) => ['starting', 'new_draft', 'stoping'].includes(status);

export interface ITaskTableData extends ICommonTableProps {
  pagination: {
    count: number;
    current: number;
    limit: number;
  };
}

export const taskCommonTableProps: ICommonTableProps = {
  checkable: false,
  defaultSize: 'small',
  hasColumnSetting: true,
  paginationType: 'normal',
  columns: [
    { id: 'name_button', name: window.i18n.tc('任务名称'), type: 'scoped_slots', props: { minWidth: 150 } },
    { id: 'protocol', name: window.i18n.tc('协议'), type: 'string' },
    { id: 'url', name: window.i18n.tc('目标地址'), type: 'string', props: { minWidth: 314 } },
    {
      id: 'task_duration_text',
      name: window.i18n.tc('响应时长'),
      type: 'string',
      props: { minWidth: 113 },
      sortable: 'custom',
    },
    { id: 'available_progress', name: window.i18n.tc('可用率'), type: 'scoped_slots', header_pre_icon: 'icon-avg' },
    { id: 'groups_str', name: window.i18n.tc('所属分组'), type: 'string' },
    { id: 'create_user', name: window.i18n.tc('创建人'), type: 'scoped_slots' },
    {
      id: 'status_text',
      name: window.i18n.tc('状态'),
      type: 'scoped_slots',
      filterable: true,
      filter_list: formatTaskStatusMapFilter(),
    },
    { id: 'enable', name: window.i18n.tc('启/停'), type: 'scoped_slots' },
    { id: 'operate', name: window.i18n.tc('操作'), type: 'scoped_slots', props: { maxWidth: 80 } },
  ],
};
// 任务表格数据初始化
export const taskTableDataInit = (
  tasks: ITaskCardData[] = [],
  pagination = {
    count: tasks.length,
    current: 1,
    limit: commonPageSizeGet(),
  }
): ITaskTableData => ({
  ...taskCommonTableProps,
  data: taskDataToTableData(
    tasks.slice((pagination.current - 1) * pagination.limit, pagination.current * pagination.limit)
  ),
  pagination,
});
// 任务列表数据转为通用表格数据
export const taskDataToTableData = (tasks: ITaskCardData[]): ICommonTableProps['data'] => {
  const data = [];
  tasks.forEach(item => {
    data.push({
      ...item,
      name_button: {
        slotId: 'name',
      },
      task_duration_text: `${item.task_duration}ms`,
      available_progress: {
        slotId: 'progress',
      },
      groups_str: item.groups?.length ? item.groups.map(group => group.name).join(',') : '--',
      status_text: {
        slotId: 'statusText',
      },
      enable: {
        slotId: 'enable',
      },
      operate: {
        slotId: 'operate',
      },
    });
  });
  return data as ICommonTableProps['data'];
};

// 以下为节点数据转换
export interface INodesTableData extends ICommonTableProps {
  pagination: {
    count: number;
    current: number;
    limit: number;
  };
}
export interface INodeData {
  bk_biz_id?: number;
  carrieroperator?: string;
  country?: string;
  gse_status?: string;
  id?: number;
  ip?: string;
  ip_type?: number;
  is_common?: boolean;
  name: string;
  plat_id: number;
  province: string;
  status: string;
  task_num: number;
  version: string;
  bk_host_id: string;
}
export const nodesCommonTableProps: ICommonTableProps = {
  checkable: false,
  defaultSize: 'small',
  hasColumnSetting: true,
  paginationType: 'normal',
  columns: [
    { id: 'name', name: window.i18n.tc('节点名称'), type: 'string' },
    { id: 'ip', name: window.i18n.tc('拨测节点'), type: 'link' },
    { id: 'ip_type', name: window.i18n.tc('IP类型'), type: 'string' },
    { id: 'type', name: window.i18n.tc('类型'), type: 'string' },
    { id: 'country', name: window.i18n.tc('国家/地区'), type: 'string' },
    { id: 'province', name: window.i18n.tc('省份'), type: 'string' },
    { id: 'task_num_text', name: window.i18n.tc('关联任务数'), type: 'scoped_slots', sortable: 'custom' },
    { id: 'carrieroperator', name: window.i18n.tc('运营商'), type: 'string' },
    { id: 'status_text', name: window.i18n.tc('状态'), type: 'scoped_slots' },
    { id: 'version', name: window.i18n.tc('版本'), type: 'string' },
    { id: 'opreate', name: window.i18n.tc('操作'), type: 'scoped_slots' },
  ],
};
export const nodesToTableDataInit = (
  nodes: INodeData[] = [],
  pagination = {
    count: nodes.length,
    current: 1,
    limit: commonPageSizeGet(),
  }
): INodesTableData => ({
  ...nodesCommonTableProps,
  data: nodesToTableData(
    nodes.slice((pagination.current - 1) * pagination.limit, pagination.current * pagination.limit)
  ),
  pagination,
});
export const transformIpTypeToText = (ipType: number) => {
  if (ipType === 0) return ['IPv4', 'IPv6'];
  if (ipType === 6) return ['IPv6'];
  return ['IPv4'];
};
// 节点数据转为通用表格数据
export const nodesToTableData = (nodes: INodeData[]): ICommonTableProps['data'] => {
  const data = [];
  nodes.forEach(item => {
    data.push({
      ...item,
      ip_type: transformIpTypeToText(item.ip_type),
      ip: {
        value: item.ip,
        url: `${location.origin}${location.pathname}?bizId=${item.bk_biz_id}#/performance/detail/${item.bk_host_id}`,
      },
      type: item.is_common ? window.i18n.tc('自建节点(公共)') : window.i18n.tc('自建节点(私有)'),
      task_num_text: {
        slotId: 'taskNum',
      },
      status_text: {
        slotId: 'statusText',
      },
      opreate: {
        slotId: 'opreate',
      },
    });
  });
  return data as ICommonTableProps['data'];
};

// 搜索nodes
export const searchNodesData = (searchValue: string, nodes: INodeData[]): INodeData[] => {
  const searchData =
    searchValue === ''
      ? nodes
      : nodes.filter(item => {
          if (~item.name.indexOf(searchValue)) return true;
          if (~item.ip.indexOf(searchValue)) return true;
          return item.ip === padIPv6(searchValue);
        });
  return searchData;
};

export const nodeStatusMap = {
  0: {
    color: '#2dcb56',
    text: window.i18n.tc('正常'),
  },
  1: {
    color: '#63656e',
    text: window.i18n.tc('初始化中...'),
  },
  '-1': {
    color: '#ea3636',
    text: window.i18n.tc('异常'),
  },
  2: {
    color: '#ffeb00',
    text: window.i18n.tc('升级'),
  },
  '-2': {
    color: '#ea3636',
    text: window.i18n.tc('失效'),
  },
};

export const paginationUtil = (pagination, arr) =>
  arr.slice((pagination.current - 1) * pagination.limit, pagination.current * pagination.limit);
