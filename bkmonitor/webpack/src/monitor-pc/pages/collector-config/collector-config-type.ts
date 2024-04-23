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
export interface IDrag {
  width: number;
  minWidth: number;
  maxWidth: number;
}

export interface IStatusData {
  success: IStatus;
  failed: IStatus;
  nodata: IStatus;
  all: IStatus;
}

export interface IStatus {
  count: number;
  data: any;
}

export interface ITabList {
  name?: string;
  type: string;
  tips?: string;
}

export interface IDetailInfo {
  bkBizId?: number;
  collectType?: string;
  createTime?: string;
  createUser?: string;
  deploymentId?: number;
  id?: number;
  label?: string;
  labelInfo?: string;
  name?: string;
  params?: any;
  pluginInfo?: any;
  remoteCollectingHost?: any;
  subscriptionId?: number;
  target?: any;
  targetNodeType?: string;
  targetNodes?: any;
  targetObjectType?: string;
  updateTime?: string;
  updateUser?: string;
}

export interface IHostTopoStatus {
  host: boolean;
  topo: boolean;
}

export interface ICustomData {
  list: any;
  page: number;
  limit: number;
  searchKey: string;
  total: number;
}

export interface IVariableData {
  $bk_target_ip?: number | string;
  $bk_target_cloud_id?: number | string;
  $bk_target_service_instance_id?: string[];
  $target?: string;
  $bk_inst_id?: string;
  $bk_obj_id?: string;
  $method?: string;
}

export interface ITargetList {
  id: string;
  name: string;
}
