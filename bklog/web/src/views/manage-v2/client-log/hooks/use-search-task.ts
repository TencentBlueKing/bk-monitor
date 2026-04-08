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

import { updateLastSelectedIndexId } from '@/common/util';
import { BK_LOG_STORAGE } from '@/store/store.type';
import useStore from '@/hooks/use-store';
import useRouter from '@/hooks/use-router';

export interface SearchCondition {
  field: string;
  operator: string;
  value: any;
}

interface UseSearchTaskOptions {
  indexSetId: string;
}

/**
 * 检索任务 Hook
 * 用于统一处理表格中的检索跳转逻辑
 */
export const useSearchTask = ({ indexSetId }: UseSearchTaskOptions) => {
  const store = useStore();
  const router = useRouter();

  /**
   * 执行检索任务
   * @param conditions 查询条件数组
   * @param timeRange 时间范围 [开始时间, 结束时间]
   */
  const searchTask = (conditions: SearchCondition[], timeRange?: [string, string]) => {
    // 更新最后选择的索引集ID
    updateLastSelectedIndexId(store.state.spaceUid, indexSetId);

    // 设置搜索类型为UI模式
    store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: 0 });

    // 构建查询参数
    const queryParams: any = {
      spaceUid: store.state.spaceUid,
      search_mode: 'ui',
      addition: JSON.stringify(conditions),
    };

    // 如果提供了时间范围，则添加 start_time 和 end_time
    if (timeRange && timeRange.length === 2) {
      queryParams.start_time = timeRange[0];
      queryParams.end_time = timeRange[1];
    }

    // 跳转到检索页面
    router.push({
      name: 'retrieve',
      params: {
        indexId: indexSetId,
      },
      query: queryParams,
    });
  };

  return {
    searchTask,
  };
};
