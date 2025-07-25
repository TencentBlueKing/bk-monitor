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
export enum EShieldCycle {
  day = 'day',
  month = 'month',
  single = 'single',
  week = 'week',
}
export type INoticeDate = {
  [key in EShieldCycle]: {
    list: (number | string)[] | { id: string; name: string }[];
    range: string[];
  };
} & {
  dateRange: string[];
  key?: string;
  shieldCycle: EShieldCycle;
};

export const Ipv6FieldMap = {
  ip: 'host_list',
  node: 'node_list',
  instance: 'service_instance_list',
  dynamic_group: 'dynamic_group_list',
};

export const ShieldDimension2NodeType = {
  ip: 'INSTANCE',
  node: 'TOPO',
  instance: 'SERVICE_INSTANCE',
  dynamic_group: 'DYNAMIC_GROUP',
};
export const ShieldDetailTargetFieldMap = {
  ip: 'bk_target_ip',
  node: 'bk_topo_node',
  instance: 'service_instance_id',
  dynamic_group: 'dynamic_group',
};
