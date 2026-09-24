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

import type { IHostTopoTreeNode } from '../types';

export type HostScopeParams = {
  bk_biz_id?: number | string;
  bk_host_id?: number;
  bk_inst_id?: number;
  bk_obj_id?: string;
};

type HostScopeNode = HostScopeParams | null;

const parseInteger = (value: unknown) => {
  if (value === null || value === undefined || value === '' || Array.isArray(value)) {
    return null;
  }
  if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+$/.test(value))) return null;
  const result = Number(value);
  return Number.isSafeInteger(result) && result > 0 ? result : null;
};

export const parseHostShareScope = (query: Record<string, unknown>): HostScopeParams => {
  if (query.shareTargetType === 'host') {
    const bkHostId = parseInteger(query.shareBkHostId);
    return bkHostId === null ? {} : { bk_host_id: bkHostId };
  }
  if (query.shareTargetType === 'topo') {
    const bkInstId = parseInteger(query.shareBkInstId);
    const bkObjId = typeof query.shareBkObjId === 'string' ? query.shareBkObjId : '';
    return bkInstId === null || !bkObjId ? {} : { bk_inst_id: bkInstId, bk_obj_id: bkObjId };
  }
  return {};
};

export const resolveHostRequestScope = (
  readonly: boolean,
  query: Record<string, unknown>,
  selectedNode: HostScopeNode
): HostScopeParams => {
  if (!readonly) {
    return {};
  }
  if (query.shareTargetType !== undefined) {
    return parseHostShareScope(query);
  }
  if (!selectedNode) {
    return {};
  }
  if (selectedNode.bk_host_id !== undefined) {
    return { bk_host_id: selectedNode.bk_host_id };
  }
  if (selectedNode.bk_obj_id && selectedNode.bk_inst_id !== undefined) {
    return { bk_inst_id: selectedNode.bk_inst_id, bk_obj_id: selectedNode.bk_obj_id };
  }
  return {};
};

/** Resolve a request target before the topology is available. Unknown share scopes never widen to the business. */
export const resolveInitialHostScope = (
  readonly: boolean,
  query: Record<string, unknown>,
  nodeId: string,
  bizId: number
): HostScopeParams | null => {
  if (readonly && query.shareTargetType !== undefined) {
    const scope = parseHostShareScope(query);
    if (scope.bk_obj_id === 'biz' && scope.bk_inst_id !== bizId) return null;
    return Object.keys(scope).length ? scope : null;
  }
  if (!nodeId) return readonly ? null : { bk_obj_id: 'biz', bk_inst_id: bizId };
  const hostId = /^\d+$/.test(nodeId) ? parseInteger(nodeId) : null;
  if (hostId !== null) return { bk_host_id: hostId };
  const match = /^([a-zA-Z][\w-]*)\|(\d+)$/.exec(nodeId);
  const instId = match ? parseInteger(match[2]) : null;
  if (!match || instId === null || (match[1] === 'biz' && instId !== bizId)) return null;
  return { bk_obj_id: match[1], bk_inst_id: instId };
};

export const hostTargetKey = (node: HostScopeNode) =>
  node?.bk_host_id !== undefined ? `host|${node.bk_host_id}` : `${node?.bk_obj_id || ''}|${node?.bk_inst_id ?? ''}`;

/** Minimal target metadata; request identity is available before the tree labels arrive. */
export const createHostTarget = (
  scope: null | { bk_host_id?: number; bk_inst_id?: number; bk_obj_id?: string },
  bizId: number
): IHostTopoTreeNode | null => {
  if (!scope) return null;
  if (scope.bk_host_id !== undefined)
    return {
      bk_biz_id: bizId,
      bk_host_id: scope.bk_host_id,
      id: String(scope.bk_host_id),
      alias_name: '',
      bk_cloud_id: 0,
      bk_host_innerip: '',
      bk_host_innerip_v6: '',
      bk_host_name: '',
      display_name: '',
      ip: '',
      metadataPending: true,
      name: '',
      os_type: '',
    };
  return {
    bk_biz_id: bizId,
    bk_inst_id: scope.bk_inst_id,
    bk_obj_id: scope.bk_obj_id,
    id: `${scope.bk_obj_id}|${scope.bk_inst_id}`,
    bk_inst_name: '',
    bk_obj_name: '',
    name: '',
    children: [],
  };
};
