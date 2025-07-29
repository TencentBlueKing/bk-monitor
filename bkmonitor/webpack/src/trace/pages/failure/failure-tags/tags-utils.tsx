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

import { ref, watch } from 'vue';

interface TagsOverflowOptions {
  collapseTagRef: any;
  isOverflow: any;
  targetRef: any;
}

function useTagsOverflow(options: TagsOverflowOptions) {
  const { targetRef, isOverflow, collapseTagRef } = options;
  const overflowTagIndex = ref<null | number>(null);

  const getTagDOM = (index?: number) => {
    const tagDomList = targetRef.value.map(item => item?.$el).filter(item => !!item);
    return typeof index === 'number' ? tagDomList[index] : tagDomList;
  };

  const calcOverflow = () => {
    if (!isOverflow.value) return;

    overflowTagIndex.value = null;
    setTimeout(() => {
      const tags = getTagDOM();
      // 出现换行的Index位置
      const tagIndexInSecondRow = tags.findIndex((currentTag, index) => {
        if (!index) {
          return false;
        }
        const previousTag = tags[index - 1];
        return previousTag.offsetTop !== currentTag.offsetTop;
      });
      overflowTagIndex.value = tagIndexInSecondRow > 0 ? tagIndexInSecondRow : null;
      // 剩余位置能否放下数字tag
      if (tags[overflowTagIndex.value]?.offsetTop !== collapseTagRef.value?.offsetTop && overflowTagIndex.value > 1) {
        overflowTagIndex.value -= 1;
      }
    });
  };

  watch(
    isOverflow,
    () => {
      calcOverflow();
    },
    { immediate: true }
  );

  // 监听Dom元素变化
  return {
    canShowIndex: overflowTagIndex,
    calcOverflow: calcOverflow,
  };
}

export { useTagsOverflow };
