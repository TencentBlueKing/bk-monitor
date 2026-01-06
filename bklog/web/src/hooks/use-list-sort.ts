
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

/**
 * 使用文本匹配和完全匹配进行排序
 * @param list 列表
 * @param matchKeys 文本匹配的 key 列表
 * @param hiddenMatchKeys 隐藏匹配的 key 列表
 * @returns 排序后的列表
 */
export default (list: any[], matchKeys: string[] = [], hiddenMatchKeys: string[] = []) => {
  const sortList = ref<any[]>(list);
  const searchText = ref<string>('');

  const updateList = (list: any[]) => {
    sortList.value = list;
  };

  const updateSearchText = (text: string) => {
    searchText.value = text;
  };

  /**
   * 判断搜索文本是否包含数字或字母
   * @param text 搜索文本
   * @returns 是否包含数字或字母
   */
  const containsNumberOrLetter = (text: string): boolean => {
    return /[0-9a-zA-Z]/.test(text);
  };

  /**
   * 计算字符串匹配度分数
   * @param text 待匹配的文本
   * @param searchText 搜索文本
   * @param isPinyinField 是否为拼音字段（py_text）
   * @returns 匹配度分数，分数越高匹配度越高，-1 表示不匹配
   */
  const calculateMatchScore = (
    text: string,
    searchText: string,
    isPinyinField: boolean = false,
  ): number => {
    if (!text || !searchText) return -1;

    const lowerText = text.toLowerCase();
    const lowerSearch = searchText.toLowerCase();
    const isNumberOrLetterMatch = containsNumberOrLetter(searchText);

    // 完全匹配：最高优先级（权重 100000）
    if (lowerText === lowerSearch) {
      return 100000;
    }

    // 开头匹配
    if (lowerText.startsWith(lowerSearch)) {
      if (isPinyinField) {
        // 拼音字段开头匹配：权重 40000
        return 40000;
      }
      // 非拼音字段开头匹配：权重 50000
      // 如果是数字字母匹配，额外加分
      return isNumberOrLetterMatch ? 55000 : 50000;
    }

    // 包含匹配
    const index = lowerText.indexOf(lowerSearch);
    if (index !== -1) {
      // 位置越小权重越高，基础分数根据位置递减
      const positionBonus = 1000 - index; // 位置0得1000分，位置1得999分，以此类推

      if (isPinyinField) {
        // 拼音字段包含匹配：基础权重 20000，位置越小加分越多
        return 20000 + positionBonus;
      }

      // 非拼音字段包含匹配：基础权重 30000，位置越小加分越多
      // 如果是数字字母匹配，额外加分
      const baseScore = 30000 + positionBonus;
      return isNumberOrLetterMatch ? baseScore + 5000 : baseScore;
    }

    return -1;
  };

  /**
   * 完全匹配函数，支持忽略前置负号
   * @param value 待匹配的值（可以是字符串或数字）
   * @param searchText 搜索文本
   * @returns 是否完全匹配（忽略前置负号）
   */
  const fullMatch = (value: any, searchText: string): boolean => {
    if (value === undefined || value === null || value === '') {
      return false;
    }

    // 将值转换为字符串
    const valueStr = String(value);
    // 移除前置负号
    const normalizedValue = valueStr.replace(/^-/, '');
    const normalizedSearch = searchText.replace(/^-/, '');

    // 完全匹配（忽略大小写和前置负号）
    return normalizedValue.toLowerCase() === normalizedSearch.toLowerCase();
  };

  /**
   * 检查 hiddenMatchKeys 是否匹配
   * @param item 列表项
   * @param searchText 搜索文本
   * @param hiddenMatchKeys 隐藏匹配的 key 列表（不作为展示字段，但参与过滤）
   * @returns 是否匹配
   */
  const checkHiddenMatch = (item: any, searchText: string, hiddenMatchKeys: string[]): boolean => {
    if (!searchText || hiddenMatchKeys.length === 0) {
      return false;
    }

    // string[] 类型：直接匹配
    if (typeof item === 'string') {
      return fullMatch(item, searchText);
    }

    // object[] 类型：根据 hiddenMatchKeys 匹配
    if (typeof item === 'object' && item !== null) {
      for (let i = 0; i < hiddenMatchKeys.length; i++) {
        const key = hiddenMatchKeys[i];
        const value = item[key];

        if (fullMatch(value, searchText)) {
          return true;
        }
      }
    }

    return false;
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

    // string[] 类型：直接匹配（非拼音字段）
    if (typeof item === 'string') {
      const score = calculateMatchScore(item, searchText, false);
      return { score, firstMatchKeyIndex: score > 0 ? 0 : -1 };
    }

    // object[] 类型：根据 matchKeys 匹配
    if (typeof item === 'object' && item !== null) {
      let maxScore = -1;
      let firstMatchKeyIndex = -1;
      let bestMatchKeyIndex = -1;

      // 遍历 matchKeys，找到最高分数和第一个匹配的 key
      for (let i = 0; i < matchKeys.length; i++) {
        const key = matchKeys[i];
        const value = item[key];

        // 跳过 undefined、null 和空字符串
        if (value !== undefined && value !== null && value !== '') {
          // 判断是否为拼音字段
          const isPinyinField = key === 'py_text';
          const score = calculateMatchScore(String(value), searchText, isPinyinField);

          // 记录第一个匹配的 key 索引（用于位置权重计算）
          if (score > 0 && firstMatchKeyIndex === -1) {
            firstMatchKeyIndex = i;
          }

          // 记录最高分数的 key 索引
          if (score > maxScore) {
            maxScore = score;
            bestMatchKeyIndex = i;
          }
        }
      }

      // 如果 matchKeys 长度 > 1，根据第一个匹配位置调整权重
      // 规则：位置越靠前的 key 匹配权重越高
      if (maxScore > 0 && matchKeys.length > 1 && firstMatchKeyIndex >= 0) {
        // 第一个 key 匹配权重最高，后续 key 权重递减
        // keyWeight: 第一个key=length, 第二个key=length-1, 以此类推
        const keyWeight = matchKeys.length - firstMatchKeyIndex;
        // 使用乘法确保权重差异明显，但不会过度放大
        maxScore = maxScore * (1 + keyWeight * 0.1);
      }

      // 返回最高分数的 key 索引（如果存在），否则返回第一个匹配的 key 索引
      return { score: maxScore, firstMatchKeyIndex: bestMatchKeyIndex >= 0 ? bestMatchKeyIndex : firstMatchKeyIndex };
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

      // 先检查 matchKeys 是否匹配
      const { score: matchScore } = matchItem(item, search, matchKeys);

      if (matchScore > 0) {
        // matchKeys 匹配：使用 matchKeys 的分数（优先级更高）
        itemsWithScore.push({ item, score: matchScore });
      } else {
        // matchKeys 不匹配时，检查 hiddenMatchKeys
        const isHiddenMatch = checkHiddenMatch(item, search, hiddenMatchKeys);

        if (isHiddenMatch) {
          // hiddenMatchKeys 匹配：给予最低优先级分数（低于所有其他匹配方式）
          itemsWithScore.push({ item, score: 1000 });
        }
        // 如果 matchKeys 和 hiddenMatchKeys 都不匹配，则不包含在结果中
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
