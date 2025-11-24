
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

import { computed, ref } from 'vue';
export default (list: any[], matchKeys: string[] = []) => {
  const sortList = ref<any[]>(list);
  // const matchKeyList = ref<string[]>(matchKeys);
  const searchText = ref<string>('');

  const updateList = (list: any[]) => {
    sortList.value = list;
  };

  const updateSearchText = (text: string) => {
    searchText.value = text;
  };

  /**
   * 计算字符串匹配度分数
   * @param text 待匹配的文本
   * @param searchText 搜索文本
   * @returns 匹配度分数，分数越高匹配度越高，-1 表示不匹配
   */
  const calculateMatchScore = (text: string, searchText: string): number => {
    if (!text || !searchText) return -1;

    const lowerText = text.toLowerCase();
    const lowerSearch = searchText.toLowerCase();

    // 完全匹配：最高优先级
    if (lowerText === lowerSearch) {
      return 10000;
    }

    // 开头匹配：次高优先级
    if (lowerText.startsWith(lowerSearch)) {
      return 5000;
    }

    // 包含匹配：基础优先级
    const index = lowerText.indexOf(lowerSearch);
    if (index !== -1) {
      // 位置越靠前，分数越高（基础分 1000，位置越靠前加分越多）
      return 1000 + (1000 - index);
    }

    return -1;
  };

  /**
   * 对单个项目进行匹配并计算分数
   * @param item 列表项
   * @param searchText 搜索文本
   * @param matchKeys 匹配的 key 列表
   * @returns 匹配度分数和第一个匹配的 key 索引，-1 表示不匹配
   */
  const matchItem = (
    item: any,
    searchText: string,
    matchKeys: string[],
  ): { score: number; firstMatchKeyIndex: number } => {
    if (!searchText) {
      return { score: 0, firstMatchKeyIndex: -1 };
    }

    // string[] 类型：直接匹配
    if (typeof item === 'string') {
      const score = calculateMatchScore(item, searchText);
      return { score, firstMatchKeyIndex: score > 0 ? 0 : -1 };
    }

    // object[] 类型：根据 matchKeys 匹配
    if (typeof item === 'object' && item !== null) {
      let maxScore = -1;
      let firstMatchKeyIndex = -1;

      // 遍历 matchKeys，找到第一个匹配的 key 和最高分数
      for (let i = 0; i < matchKeys.length; i++) {
        const key = matchKeys[i];
        const value = item[key];

        if (value !== undefined && value !== null) {
          const score = calculateMatchScore(String(value), searchText);
          if (score > maxScore) {
            maxScore = score;
            // 记录第一个匹配的 key 索引（用于权重计算）
            if (firstMatchKeyIndex === -1) {
              firstMatchKeyIndex = i;
            }
          }
        }
      }

      // 如果 matchKeys 长度 > 1，根据第一个匹配位置调整权重
      if (maxScore > 0 && matchKeys.length > 1 && firstMatchKeyIndex >= 0) {
        // 第一个 key 匹配权重最高，后续 key 权重递减
        const keyWeight = matchKeys.length - firstMatchKeyIndex;
        maxScore = maxScore * keyWeight;
      }

      return { score: maxScore, firstMatchKeyIndex };
    }

    return { score: -1, firstMatchKeyIndex: -1 };
  };

  // 过滤和排序后的列表
  const filteredList = computed(() => {
    const search = searchText.value.trim();
    const list = sortList.value;

    // 如果没有搜索文本，返回原列表
    if (!search) {
      return list;
    }

    // 一次遍历完成过滤和评分
    const itemsWithScore: Array<{ item: any; score: number }> = [];

    for (let i = 0; i < list.length; i++) {
      const item = list[i];
      const { score } = matchItem(item, search, matchKeys);

      // 只保留匹配的项目
      if (score > 0) {
        itemsWithScore.push({ item, score });
      }
    }

    // 根据分数降序排序（分数越高越靠前）
    itemsWithScore.sort((a, b) => b.score - a.score);

    // 返回排序后的项目列表
    return itemsWithScore.map(({ item }) => item);
  });

  return {
    sortList: filteredList,
    updateList,
    updateSearchText,
  };
};
