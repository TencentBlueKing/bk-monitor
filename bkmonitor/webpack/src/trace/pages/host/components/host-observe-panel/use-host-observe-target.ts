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
import { shallowRef, watch } from 'vue';

import { getHostInfo } from 'monitor-api/modules/scene_view';
import { isBkHostId } from 'monitor-common/utils/host-monitor-url';

import { getHostInfoPage } from '../../services/host-service';
import { isHostNode } from '../../utils/topo-tree';

import type { IHostBaseInfo } from '../../types/host';
import type { IHostTopoHostNode } from '../../types/topo';

export type HostObserveMode = 'drawer' | 'inline';

const toHostNode = (host: IHostBaseInfo): IHostTopoHostNode => ({
  bk_biz_id: host.bk_biz_id,
  bk_cloud_id: host.bk_cloud_id,
  bk_host_id: host.bk_host_id,
  bk_host_innerip: host.bk_host_innerip,
  bk_host_innerip_v6: '',
  bk_host_name: host.bk_host_name,
  alias_name: host.bk_host_name,
  display_name: host.display_name,
  id: String(host.bk_host_id),
  ip: host.bk_host_innerip,
  name: host.bk_host_name,
  os_type: host.bk_os_type,
});

const resolveBizId = (bizId: string) => {
  const parsed = Number(bizId);
  if (Number.isFinite(parsed) && parsed > 0) return parsed;
  const current = Number(window.cc_biz_id || window.bk_biz_id || 0);
  return Number.isFinite(current) ? current : 0;
};

/**
 * 抽屉按 bk_host_id 或 IPv4+云区域解析主机，并用主机页同一套接口补元数据。
 * 内嵌模式直接使用页面已经准备好的节点，不再请求一次。
 */
export const useHostObserveTarget = (options: {
  bkBizId: () => string;
  bkCloudId: () => string;
  bkHostId: () => string;
  enabled: () => boolean;
  ip: () => string;
  mode: () => HostObserveMode;
  selectedNode: () => IHostTopoHostNode | null;
}) => {
  const host = shallowRef<IHostTopoHostNode | null>(null);
  const loading = shallowRef(false);
  const error = shallowRef(false);
  let version = 0;

  const load = async () => {
    if (options.mode() === 'inline') {
      version += 1;
      const node = options.selectedNode();
      host.value = node && isHostNode(node) ? node : null;
      loading.value = false;
      error.value = false;
      return;
    }
    if (!options.enabled()) return;
    const current = ++version;
    loading.value = true;
    error.value = false;
    host.value = null;
    try {
      const bizId = resolveBizId(options.bkBizId());
      let id = options.bkHostId();
      if (!isBkHostId(id)) {
        const ip = options.ip();
        if (!ip) throw new Error('missing host identity');
        const data = (await getHostInfo({
          ip,
          bk_cloud_id: options.bkCloudId() || '0',
        })) as null | { bk_host_id?: number | string };
        id = data?.bk_host_id == null ? '' : String(data.bk_host_id);
        if (!isBkHostId(id)) throw new Error('unresolved host');
      }
      if (current !== version) return;
      const page = await getHostInfoPage({
        bk_biz_id: bizId,
        bk_host_id: Number(id),
        page: 1,
        page_size: 1,
      });
      if (current !== version) return;
      const found = page.items.find(item => String(item.bk_host_id) === id);
      if (!found) throw new Error('host metadata unavailable');
      host.value = toHostNode(found);
      loading.value = false;
    } catch {
      if (current !== version) return;
      host.value = null;
      loading.value = false;
      error.value = true;
    }
  };

  watch(
    () => [
      options.mode(),
      options.enabled(),
      options.bkHostId(),
      options.ip(),
      options.bkCloudId(),
      options.bkBizId(),
      options.selectedNode()?.bk_host_id,
      options.selectedNode()?.metadataPending,
      options.selectedNode()?.display_name,
      options.selectedNode()?.bk_host_innerip,
    ],
    () => {
      void load();
    },
    { immediate: true }
  );

  return { error, host, loading, reload: load };
};
