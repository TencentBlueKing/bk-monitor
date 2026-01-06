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

// 固定的内置字段 - 内部存储数组
const _builtInInitHiddenList = [
  'gseIndex',
  'gseindex',
  'iterationIndex',
  'iterationindex',
  '_iteration_idx',
  '__dist_01',
  '__dist_03',
  '__dist_05',
  '__dist_07',
  '__dist_09',
  '__ipv6__',
  '__parse_failure',
  'time',
  '__module__',
  '__set__',
  '__ipv6__',
  '__shard_key__',
  '__unique_key__',
  '__bcs_cluster_name__',
];

/**
 * 获取内置隐藏字段列表（动态获取最新值）
 * @returns {string[]} 内置隐藏字段列表
 */
export const getBuiltInInitHiddenList = () => {
  return _builtInInitHiddenList;
};

/**
 * 更新内置隐藏字段列表
 * @param {string[]} newList - 新的字段列表
 */
export const updateBuiltInInitHiddenList = (newList) => {
  if (Array.isArray(newList) && newList.length > 0) {
    _builtInInitHiddenList.splice(0, _builtInInitHiddenList.length);
    newList.forEach(item => {
      if (!_builtInInitHiddenList.includes(item)) {
        _builtInInitHiddenList.push(item);
      }
    });
  }
};

/**
 * 内置隐藏字段列表（兼容旧代码，返回响应式数组引用）
 * 注意：为了保持响应式，请使用 getBuiltInInitHiddenList() 获取最新值
 * 或者直接使用此数组引用（因为数组引用本身是响应式的）
 */
export const builtInInitHiddenList = _builtInInitHiddenList;
