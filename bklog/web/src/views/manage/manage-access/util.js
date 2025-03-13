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

import { formatFileSize } from '@/common/util';

import $http from '@/api';
/**
 * 格式化字节大小为可读字符串。
 *
 * @param {number|undefined} size - 需要格式化的字节大小。
 *
 * @returns {string} 格式化后的文件大小字符串，或默认字符串 `'--'`。
 */
export function formatBytes(size) {
  if (size === undefined) {
    return '--';
  }
  if (size === 0) {
    return '0';
  }
  return formatFileSize(size, true);
}
/**
 * 请求存储使用情况并更新数据列表中的相应字段。
 *
 * @param {string} bkBizId - 业务 ID
 * @param {Array} arr - 包含数据项的数组，每个数据项应具有 `index_set_id` 和 `is_active` 属性。
 * @param {boolean} [type=false] - 可选参数，决定筛选数据项的条件。
 * @param {Function} callbackFn - 回调函数，用于处理每个匹配的数据项。
 *
 */
export function requestStorageUsage(bkBizId, arr, type = false, callbackFn) {
  let index_set_ids = [];

  if (type) {
    index_set_ids = arr
      .filter(item => {
        return item.index_set_id && item.is_active && !('total_usage' in item);
      })
      .map(item => item.index_set_id);
  } else {
    index_set_ids = arr
      .filter(item => {
        return item.index_set_id && item.is_active && item.apply_status == 'normal';
      })
      .map(item => item.index_set_id);
  }

  if (!index_set_ids.length) {
    return Promise.resolve();
  }

  return $http
    .request('collect/getStorageUsage', {
      data: {
        bk_biz_id: bkBizId,
        index_set_ids,
      },
    })
    .then(resp => {
      const { data } = resp;
      arr.forEach(item => {
        ['daily_usage', 'total_usage'].forEach(key => {
          const matchedItem = data.find(dataItem => Number(dataItem.index_set_id) === Number(item.index_set_id)) || {};
          if (matchedItem?.[key] !== undefined) {
            callbackFn(item, key, matchedItem);
          }
        });
      });
    })
    .catch(error => {
      throw error;
    });
}
