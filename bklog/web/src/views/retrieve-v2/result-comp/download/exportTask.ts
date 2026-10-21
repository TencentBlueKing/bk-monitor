/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { cloneDeep } from 'lodash-es';

interface ExportTask {
  id: number | string;
  engine?: string;
  export_type?: string;
  export_pkg_name?: string | null;
  index_set_type: 'single' | 'union' | 'scene';
  log_index_set_id?: number | string;
  log_index_set_ids?: (number | string)[];
  search_dict: Record<string, any>;
}

export const EXPORT_SUBMITTED_MESSAGE = '任务提交成功，下载完成将会收到邮件通知。可前往下载历史查看下载状态';

interface ExportSubmitContext {
  $http: { request: (url: string, config: Record<string, any>) => Promise<any> };
  $t: (key: string, values?: Record<string, string>) => string;
  $bkInfo: (options: Record<string, any>) => void;
}

/** 后端预检排序，确认前不创建任务；始终提交独立快照，不能修改页面或历史记录的排序。 */
export async function submitExportWithSortConfirmation(
  context: ExportSubmitContext,
  url: string,
  config: Record<string, any>,
) {
  const request = cloneDeep(config);
  request.data.supports_sort_confirmation = true;
  const response = await context.$http.request(url, request);
  if (!response.result || !response.data?.requires_sort_confirmation) return response;

  const sortList: string[][] = response.data.sort_list;
  const sortDescription = sortList
    .map(([field, direction]) => `${field} ${context.$t(direction === 'desc' ? '降序' : '升序')}`)
    .join(' → ');
  const confirmed = await new Promise<boolean>(resolve => {
    context.$bkInfo({
      type: 'warning',
      title: context.$t('确认调整导出排序'),
      subTitle: context.$t(
        '为支持分片并行导出，将优先按日志时间降序排列，同一时间内保留其他字段的排序规则。筛选条件、导出字段和数据范围不变。实际导出排序：{sort}',
        { sort: sortDescription },
      ),
      okText: context.$t('按此排序导出'),
      maskClose: false,
      confirmFn: () => resolve(true),
      cancelFn: () => resolve(false),
      closeFn: () => resolve(false),
      afterLeaveFn: () => resolve(false),
    });
  });
  if (!confirmed) return null;

  request.data.sort_list = cloneDeep(sortList);
  const result = await context.$http.request(url, request);
  // 不循环确认或静默创建：路由配置变化时应重新打开导出流程。
  if (result.data?.requires_sort_confirmation) throw new Error(context.$t('导出排序已变化，请重新提交并确认'));
  return result;
}

export function getExportTaskKey(task: ExportTask) {
  return `${task.engine || 'legacy'}:${task.id}`;
}

/** 同步历史可能没有文件名，按原任务生成前端兜底名称。 */
export function getExportDownloadFileName(
  task: ExportTask,
  indexSetList: { index_set_id: number | string; lightenName?: string }[] = [],
) {
  if (task.export_pkg_name?.trim()) return task.export_pkg_name;

  if (task.index_set_type === 'scene') return 'bk_log_search_scene.log';

  if (task.index_set_type === 'union') {
    const indexSetIds = task.log_index_set_ids?.length
      ? task.log_index_set_ids
      : task.search_dict.index_set_ids?.length
        ? task.search_dict.index_set_ids
        : task.search_dict.union_configs?.map(item => item.index_set_id) || [];
    return indexSetIds.length ? `bk_log_union_search_${indexSetIds.join('_')}.log` : 'bk_log_union_search.log';
  }

  const indexSetId = task.log_index_set_id ?? task.search_dict.index_set_id ?? task.search_dict.index_set_ids?.[0];
  const lightName = indexSetList.find(item => String(item.index_set_id) === String(indexSetId))?.lightenName;
  const name = lightName?.substring(2, lightName.length - 1);
  return name ? `bk_log_search_${name}.log` : 'bk_log_search.log';
}

/** 重试只使用任务保存的参数；复制后补齐旧记录的索引集信息。 */
export function buildExportRetryRequest(task: ExportTask) {
  const data = cloneDeep(task.search_dict);
  const type = task.index_set_type;
  const isSync = task.engine !== 'sharded' && task.export_type === 'sync';
  const config: { data: Record<string, any>; params?: { index_set_id: number | string } } = { data };
  let url: string;

  if (type === 'scene') {
    url = isSync ? '/search/scene/export/sample/' : 'retrieve/getSceneAsyncExport';
  } else if (type === 'union') {
    if (isSync) {
      if (!data.index_set_ids?.length) {
        data.index_set_ids = task.log_index_set_ids?.length
          ? cloneDeep(task.log_index_set_ids)
          : data.union_configs?.map(item => item.index_set_id);
      }
      url = '/search/index_set/union_search/export/';
    } else {
      if (!data.union_configs?.length) {
        const ids = task.log_index_set_ids?.length ? task.log_index_set_ids : data.index_set_ids;
        data.union_configs = ids?.map(indexSetId => ({ begin: 0, index_set_id: indexSetId }));
      }
      data.is_quick_export = false;
      url = 'retrieve/unionExportAsync';
    }
  } else {
    const indexSetId = task.log_index_set_id ?? data.index_set_id ?? data.index_set_ids?.[0];
    config.params = { index_set_id: indexSetId };
    url = isSync ? `/search/index_set/${indexSetId}/export/` : 'retrieve/exportAsync';
  }

  return { url, config, isSync };
}
