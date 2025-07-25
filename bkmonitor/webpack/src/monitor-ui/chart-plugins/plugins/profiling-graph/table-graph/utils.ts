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

/**
 * @desc 表格字段排序
 * @param { Array } list
 * @param { String } sortKey 排序字段
 * @param { String } sortType 排序类型 升序、降序、不排序
 * @returns { Array }
 */
export const sortTableGraph = (list, sortKey, sortType) => {
  const comparator = (prev, next) => {
    // 排序
    if (sortKey) {
      // 升序
      if (sortType === 'asc') {
        // 函数名称按 字符串 升序排序
        if (sortKey === 'name') return prev.name.toLowerCase().localeCompare(next.name.toLowerCase());

        // 如果是对比模式的 diff 列排序 则要考虑 added 和 removed 在两端的情况
        if (sortKey === 'diff') {
          // 先检查标签mark，added 排在最前 removed 排在最后
          if (prev.mark === 'added' && next.mark !== 'added') return -1;
          else if (next.mark === 'added' && prev.mark !== 'added') return 1;
          else if (prev.mark === 'removed' && next.mark !== 'removed') return 1;
          else if (next.mark === 'removed' && prev.mark !== 'removed') return -1;
          else return prev[sortKey] - next[sortKey];
        }

        return prev[sortKey] - next[sortKey];
      } else if (sortType === 'desc') {
        // 降序
        // 函数名称按 字符串 降序排序
        if (sortKey === 'name') return next.name.toLowerCase().localeCompare(prev.name.toLowerCase());

        // 如果是对比模式的 diff 列排序 则要考虑 added 和 removed 在两端的情况
        if (sortKey === 'diff') {
          // 先检查标签mark，removed 排在最前 added 排在最后
          if (prev.mark === 'added' && next.mark !== 'added') return 1;
          else if (next.mark === 'added' && prev.mark !== 'added') return -1;
          else if (prev.mark === 'removed' && next.mark !== 'removed') return -1;
          else if (next.mark === 'removed' && prev.mark !== 'removed') return 1;
          else return next[sortKey] - prev[sortKey];
        }

        return next[sortKey] - prev[sortKey];
      }

      // 默认不排序
      return 0;
    }

    // 不排序
    return 0;
  };

  return list.sort(comparator);
};
