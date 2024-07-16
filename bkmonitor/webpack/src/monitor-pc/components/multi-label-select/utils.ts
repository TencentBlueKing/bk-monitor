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
import type { IList, ITreeItem } from './types';

/**
 * 标签数组转树形结构
 * @param list 标签接口数据
 */
export const labelListToTreeData = (list: IList[]): ITreeItem[] => {
  const localList = [];
  const infoMap = list.reduce((map, node) => {
    const parentKey = getParentKey(node.labelName);
    const item = {
      name: getNodeName(node.labelName),
      id: node.id,
      key: node.labelName,
      parentKey,
    };
    localList.push(item);
    map[item.key] = item;
    return map;
  }, {});
  return localList.filter(node => {
    const { parentKey } = node;
    if (infoMap[parentKey]) {
      const temp = infoMap[parentKey];
      temp.children ? temp.children.push(node) : (temp.children = [node]);
    }
    return !parentKey;
  });
};

/**
 * @param str a/b
 * @param leng
 */
const getNodeName = (str: string, leng = 1) => {
  const res = str.split('/').filter(item => item);
  return res ? res[res.length - leng] : str;
};

/**
 * @param str a/b
 */
const getParentKey = (str: string) => {
  const res = str.split('/').filter(item => item);
  return res?.length > 1 ? res.slice(0, res.length - 1).join('/') : null;
};
