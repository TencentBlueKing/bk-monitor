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
import { computed, type ComputedRef } from 'vue';

export default (props, { emit }) => {
  /**
   * 索引集列表过滤标签
   */
  const indexSetTagList: ComputedRef<
    { tag_id: number; name: string; color: string }[]
  > = computed(() => {
    const listMap: Map<
      number,
      { tag_id: number; name: string; color: string }
    > = props.list.reduce((acc, item) => {
      for (const tag of item.tags) {
        if (!acc.has(tag.tag_id) && tag.tag_id !== 4) {
          acc.set(tag.tag_id, tag);
        }
      }

      return acc;
    }, new Map<number, { tag_id: number; name: string; color: string }>());

    return Array.from(listMap.values());
  });

  const clearAllValue = () => {
    emit('value-change', []);
  };

  /**
   * 多选：选中操作
   * @param item
   * @param value
   * @param storeList: 如果是选中状态，storeList中的值会被忽略，不会作为选中结果抛出，如果是非选中，storeList 中的值会被作为选中结果抛出
   *
   */

  // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
  const handleIndexSetItemCheck = (item, isChecked, storeList = []) => {
    const targetValue: any[] = [];

    // 如果是选中
    if (isChecked) {
      for (const v of props.value) {
        if (!storeList.includes(v)) {
          targetValue.push(v.unique_id);
        }
      }
      targetValue.push(item.unique_id);
      emit('value-change', targetValue);
      return;
    }

    // 如果是取消选中
    for (const v of props.value) {
      const uniqueId = v?.unique_id ?? v;
      if (uniqueId !== item.unique_id) {
        targetValue.push(v);
      }
    }

    for (const v of storeList ?? []) {
      if (!targetValue.includes(v)) {
        targetValue.push(v);
      }
    }

    emit('value-change', targetValue);
  };

  return {
    clearAllValue,
    handleIndexSetItemCheck,
    indexSetTagList,
  };
};
