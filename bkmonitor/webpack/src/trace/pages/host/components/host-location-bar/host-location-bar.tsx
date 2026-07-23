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

import { type PropType, computed, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import TemporaryShare from '../temporary-share/temporary-share';
import { getNodeDisplayName, isHostNode } from '../../utils/topo-tree';
import { storeToRefs } from 'pinia';
import type { IHostTopoTreeNode } from '../../types';

import { useHostStore } from '../../../../store/modules/host';

import './host-location-bar.scss';

export default defineComponent({
  name: 'HostLocationBar',
  props: {
    /** 当前选中的节点 / 主机 */
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const route = useRoute();
    const { activeTab } = storeToRefs(useHostStore());

    /** 当前定位文案：节点：xxx / 主机：xxx */
    const locationText = computed(() => {
      const node = props.selectedNode;
      if (!node) {
        return '';
      }
      const prefix = isHostNode(node) ? t('主机') : t('节点');
      return `${prefix}：${getNodeDisplayName(node)}`;
    });

    const formatShareTokenParams = (params: Record<string, unknown>) => {
      const data = (params.data || {}) as Record<string, unknown>;
      data.name = 'host';
      data.path = '/trace/host/:id?';
      data.params = {
        id: props.selectedNode?.id,
      };
      data.query = {
        ...route.query,
        activeTab: activeTab.value,
        from: params.default_time_range[0],
        to: params.default_time_range[1],
        shareLink: true,
        lockSearch: params.lock_search,
      };
      params.data = data;
      return params;
    };

    return () => {
      if (!props.selectedNode) {
        return null;
      }
      return (
        <div class='host-location-bar'>
          <i class='icon-monitor icon-dingwei' />
          <span class='host-location-bar-text'>{locationText.value}</span>
          <TemporaryShare
            formatTokenParams={formatShareTokenParams}
            type='host'
          />
        </div>
      );
    };
  },
});
