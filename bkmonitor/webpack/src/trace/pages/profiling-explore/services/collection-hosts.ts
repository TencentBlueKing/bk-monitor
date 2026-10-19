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
import {
  agentStatisticsIpChooserTopo,
  batchGetIpChooserConfig,
  checkIpChooserHost,
  detailsIpChooserHost,
  globalConfigIpChooserConfig,
  queryHostIdInfosIpChooserTopo,
  queryHostsIpChooserTopo,
  queryPathIpChooserTopo,
  treesIpChooserTopo,
  updateConfigIpChooserConfig,
} from 'monitor-api/modules/model';

import type { CollectionHost } from '../types/collection';

export function createCollectionHostServices(bizId: number, signal: AbortSignal) {
  const scope = { scope_list: [{ scope_type: 'biz', scope_id: String(bizId) }] };
  const options = { signal };
  const params = (value: Record<string, unknown> = {}) => {
    const { search_content, ...rest } = value;
    return { ...rest, ...(search_content ? { search_content } : {}), ...scope };
  };
  return {
    fetchTopologyHostCount: () => treesIpChooserTopo(scope, options),
    fetchTopologyHostsNodes: value => queryHostsIpChooserTopo(params(value), options),
    fetchTopologyHostIdsNodes: async value => {
      const result = await queryHostIdInfosIpChooserTopo(params(value), options);
      return {
        ...result,
        data: result.data.map(host => ({ ...host, cloud_area: host.cloud_area || { id: host.cloud_id } })),
      };
    },
    fetchHostsDetails: (value): Promise<CollectionHost[]> =>
      detailsIpChooserHost(params(value), { ...options, needMessage: false }),
    fetchHostCheck: value => checkIpChooserHost(params(value), options),
    fetchNodesQueryPath: value => queryPathIpChooserTopo(params(value), options),
    fetchHostAgentStatisticsNodes: value => agentStatisticsIpChooserTopo(params(value), options),
    fetchCustomSettings: value => batchGetIpChooserConfig(value, options),
    updateCustomSettings: value => updateConfigIpChooserConfig(value, options),
    fetchConfig: async () => {
      const config = await globalConfigIpChooserConfig({}, options);
      return { bk_cmdb_static_topo_url: `${config.CC_ROOT_URL}/#/business/${bizId}/index` };
    },
  };
}
