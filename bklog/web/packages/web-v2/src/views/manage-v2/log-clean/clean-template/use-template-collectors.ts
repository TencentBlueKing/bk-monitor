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

import { ref } from 'vue';

import http from '@/api';

export interface RelatedIndexSet {
  index_set_id: number;
  index_set_name: string;
}

export interface CleanTemplateCollector {
  bk_biz_id: number;
  collector_config_id: number;
  collector_config_name: string;
  log_access_type: string;
  related_index_set_list: RelatedIndexSet[];
}

export interface CleanTemplateSyncResult {
  id: number;
  message: string;
  name: string;
  status: 'FAILED' | 'SUCCESS';
}

export default function useTemplateCollectors() {
  const collectors = ref<CleanTemplateCollector[]>([]);
  const isCollectorsLoading = ref(false);
  let requestId = 0;

  const resetCollectors = () => {
    requestId += 1;
    collectors.value = [];
    isCollectorsLoading.value = false;
  };

  const requestCollectors = async (cleanTemplateId?: number) => {
    requestId += 1;
    const currentRequestId = requestId;
    collectors.value = [];
    if (!cleanTemplateId) {
      isCollectorsLoading.value = false;
      return false;
    }

    isCollectorsLoading.value = true;
    try {
      const res = await http.request('clean/cleanTemplateCollectors', {
        params: { clean_template_id: cleanTemplateId },
      });
      if (currentRequestId !== requestId) {
        return false;
      }
      collectors.value = Array.isArray(res.data) ? res.data : [];
      return res.result !== false;
    } catch (error) {
      if (currentRequestId === requestId) {
        collectors.value = [];
      }
      console.warn(error);
      return false;
    } finally {
      if (currentRequestId === requestId) {
        isCollectorsLoading.value = false;
      }
    }
  };

  return {
    collectors,
    isCollectorsLoading,
    requestCollectors,
    resetCollectors,
  };
}
