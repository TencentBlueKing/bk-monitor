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

export enum EStatus {
  ALL = 'ALL',
  FAILED = 'FAILED',
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  STOPPED = 'STOPPED',
  SUCCESS = 'SUCCESS',
  WARNING = 'WARNING',
}

export const FILTER_TYPE_LIST = [
  { id: EStatus.ALL, name: window.i18n.t('全部') },
  { id: EStatus.SUCCESS, color: ['#3fc06d29', '#3FC06D'], name: window.i18n.t('正常') },
  { id: EStatus.FAILED, color: ['#ea363629', '#EA3636'], name: window.i18n.t('异常') },
  { id: EStatus.RUNNING, name: window.i18n.t('执行中') },
];

export const colorMap = {
  FAILED: ['#ea363629', '#EA3636'],
  SUCCESS: ['#3fc06d29', '#3FC06D'],
  PENDING: ['#3fc06d29', '#3FC06D'],
  RUNNING: ['#3fc06d29', '#3FC06D'],
  DEPLOYING: ['#3fc06d29', '#3FC06D'],
  STARTING: ['#3fc06d29', '#3FC06D'],
  STOPPING: ['#ea363629', '#EA3636'],
};

export const labelMap = {
  ADD: {
    color: '#3A84FF',
    name: window.i18n.t('新增'),
  },
  REMOVE: {
    color: '#6C3AFF',
    name: window.i18n.t('删除'),
  },
  UPDATE: {
    color: '#FF9C01',
    name: window.i18n.t('变更'),
  },
  RETRY: {
    color: '#414871',
    name: window.i18n.t('重试'),
  },
};

export const statusMap = {
  SUCCESS: {
    color: '#94F5A4',
    border: '#2DCB56',
    name: window.i18n.t('正常'),
  },
  FAILED: {
    color: '#FD9C9C',
    border: '#EA3636',
    name: window.i18n.t('异常'),
  },
  PENDING: {
    color: '#3A84FF',
    name: window.i18n.t('等待中'),
  },
  RUNNING: {
    color: '#3A84FF',
    name: window.i18n.t('执行中'),
  },
  DEPLOYING: {
    color: '#3A84FF',
    name: window.i18n.t('部署中'),
  },
  STARTING: {
    color: '#3A84FF',
    name: window.i18n.t('启用中'),
  },
  STOPPING: {
    color: '#F0F1F5',
    border: '#C4C6CC',
    name: window.i18n.t('停用中'),
  },
};

export interface IContentsItem {
  child: any[];
  failedNum: number;
  is_label: boolean;
  isExpand: boolean;
  label_name: string;
  pendingNum: number;
  showAlertHistogram?: boolean;
  successNum: number;
  table: any[];
}

export const STATUS_LIST = ['PENDING', 'RUNNING', 'DEPLOYING', 'STARTING', 'STOPPING'];

export const operatorMap = {
  ROLLBACK: window.i18n.t('回滚'),
  UPGRADE: window.i18n.t('升级'),
  CREATE: window.i18n.t('新增'),
  EDIT: window.i18n.t('编辑'),
  ADD_DEL: window.i18n.t('增删目标'),
  START: window.i18n.t('启用'),
  STOP: window.i18n.t('停用'),
  AUTO_DEPLOYING: window.i18n.t('自动执行'),
};
