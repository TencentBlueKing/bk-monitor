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
import { deepClone } from 'monitor-common/utils/utils';

import type { IBkSeachSelectValue, IQueryDataSearch, IWhere } from '../typings';

/** 视图的设置页面的弹层层级 */
export const SETTINGS_POP_Z_INDEX = 4100;

export type VarReferenceMap = Record<string, string[]>;
export type VarWhereMap = Record<string, IWhere[]>;

/**
 * @description: 有变量的where提取引用关系数据
 * @param {VarWhereMap} sourceData 维度的条件数据
 * @return {VarWhereMap}
 */
export const handleGetVarReferenceMap = (sourceData: VarWhereMap) => {
  const referenceMap: VarReferenceMap = {};
  Object.entries(sourceData).forEach(arr => {
    const [key, value] = arr;
    referenceMap[key] = value.reduce((total, where) => {
      const matchList = [];
      where.value.forEach(varItem => {
        const match = varItem.match(/^\${?([a-zA-Z0-9_]+)}?$/);
        if (match) {
          const varKey = match[1];
          !matchList.includes(varKey) && matchList.push(varKey);
        }
      });
      return total.concat(matchList);
    }, []);
  });
  return referenceMap;
};
/**
 * @description: 检查变量是否存在循环引用
 * @param {VarWhereMap} sourceData 变量数据
 * @return {boolean} true 为出现循环引用
 */
export const handleCheckVarWhere = (sourceData: VarWhereMap): boolean => {
  /** 从where条件获取变量的一层引用 */
  const referenceMap: VarReferenceMap = handleGetVarReferenceMap(sourceData);
  /** 生成变量的每一层的引用关系对象 */
  const keys = Object.keys(referenceMap);
  const keyMap = {};
  /** 标记出现循环引用 */
  let isFaild = false;
  const fn = (keys, firstKey, max) => {
    if (!keys?.length || !max) return {};
    if (!max) {
      isFaild = true;
      return {};
    }
    max -= 1;
    const keysObj = {};
    keys.forEach(item => {
      if (item !== firstKey) {
        keysObj[item] = fn(referenceMap[item], firstKey, max);
      } else {
        keysObj[item] = '';
      }
    });
    return keysObj;
  };
  keys.forEach(firstKey => {
    /** 设置循环引用（递归）的最大限制，避免出现程序卡死 */
    const MAX_LOOP = 100;
    keyMap[firstKey] = { [firstKey]: fn(referenceMap[firstKey], firstKey, MAX_LOOP) };
  });
  /** 判断是否含有循环引用的变量 isClosedLoop = true 为出现循环引用*/
  const isClosedLoop =
    Object.entries(keyMap).some(item => {
      const [key, value] = item;
      const regEx = new RegExp(key, 'g');
      const match = JSON.stringify(value).match(regEx);
      return match.length > 1;
    }) || isFaild;
  return isClosedLoop;
};

/**
 * @description: 转换条件值里的变量
 * @param {IWhere} where 条件
 * @param {Map} dataMap 变量替换的映射表
 */
export const handleReplaceWhereVar = (where: IWhere[], dataMap: Map<string, string | string[]>) => {
  const result = where
    .filter(item => !!item.value.length)
    .map(item => {
      /** 避免重复 */
      const isExitList: string[] = [];
      return {
        ...item,
        value: item.value.reduce((total, val) => {
          const match = val.match(/^\${?([a-zA-Z0-9_]+)}?$/);
          if (match) {
            const mapKey = match[1]; // $xxx 格式的变量
            let options = dataMap.get(mapKey);
            options = Array.isArray(options) ? options : options ? [options] : [];
            if (options && !isExitList.includes(match[1])) {
              // const ids = options.map(item => item.id);
              total.push(...options);
              isExitList.push(mapKey);
            }
          } else {
            total.push(val);
          }
          return total;
        }, []),
      };
    });
  return result;
};

/**
 * @description: 从字符串中提取变量引用的keys数组
 * @param {string} str
 * @return {string[]}
 */
export const handleGetReferenceKeyList = (srcStr: string): string[] => {
  if (!srcStr) return [];
  const match = srcStr.match(/\${?([a-zA-Z0-9_]+)}?/g);
  if (!match) return [];
  const resultList = match.map(key => key.replace('$', ''));
  return resultList;
};

/**
 * @description: 替换变量请求参数中的引用变量
 * @param {Record} srcData
 */

export const handleReplaceVarData = (data: Record<string, any>, map: Map<string, any>): Record<string, any> => {
  const srcData = deepClone(data);
  /** 特殊处理where条件，where的value格式是数组 */
  if (srcData.where) {
    srcData.where = handleReplaceWhereVar(srcData.where, map);
  }
  const srcStr = JSON.stringify(srcData);
  const resultStr = srcStr.replace(/\${?([a-zA-Z0-9_]+)}?/g, (...args) => {
    const [_, key] = args;
    const value = map.get(key);
    return typeof value === 'object' ? JSON.stringify(value) : value;
  });
  const resultObj = JSON.parse(resultStr);
  return resultObj;
};

/**
 * 转换侧栏搜索参数为请求接口的参数格式
 * @param condition search-select组件值
 * @returns 接口参数
 */

export const transformConditionValueParams = (condition: IBkSeachSelectValue[]): IQueryDataSearch =>
  condition.map(item => {
    const key = item.values ? item.id : 'keyword';
    const value = item.values ? (item.multiple ? item.values.map(val => val.id) : item.values[0]?.id) : item.id;
    return {
      [key]: value,
    };
  });
/**
 * 将路由搜索条件转换为search-select组件值
 * @param search 搜索条件
 * @returns search-select组件值
 */

export const transformQueryDataSearch = (search: IQueryDataSearch): IBkSeachSelectValue[] =>
  search.map((item): IBkSeachSelectValue => {
    const key = Object.keys(item)?.[0];
    const value = item[key];
    if (key === 'keyword') {
      return {
        id: value as string,
        name: value as string,
      };
    }
    return {
      id: key,
      name: key,
      multiple: Array.isArray(value) && key !== 'keyword',
      values:
        typeof value === 'string'
          ? [{ id: value, name: value }]
          : value.map(set => ({
              id: set,
              name: set,
            })),
    };
  }) as IBkSeachSelectValue[];

/**
 * 根据可选列表更新search-select组件值得name
 * @param conditionList 可选项
 * @param searchList 需要更新的值
 * @param needFilter 是需要根据列表过滤掉值不存在的数据项
 * @param excludesKeyword 不需要过滤的keyword自定义输入的条件 needFilter = true 生效
 * @returns IBkSeachSelectValue
 */

export const updateBkSearchSelectName = (
  conditionList: IBkSeachSelectValue[],
  searchList: IBkSeachSelectValue[],
  needFilter = false,
  excludesKeyword = false
): IBkSeachSelectValue[] => {
  const localSearchList = deepClone(searchList);
  const res = localSearchList.reduce((total: IBkSeachSelectValue[], item) => {
    const target = conditionList.find(tar => tar.id === item.id);
    if (target) {
      const childList = target.children || [];
      item.name = target.name;
      item.values = item.values.map(val => {
        const childTarget = childList.find(child => child.id === val.id);
        if (childTarget) {
          val.name = childTarget.name;
        }
        return val;
      });
      if (needFilter) total.push(item);
    }
    if (!needFilter) total.push(item);
    if (needFilter && excludesKeyword && !item.values) total.push(item);
    return total;
  }, []) as IBkSeachSelectValue[];
  return res;
};

/**
 * 转换成search-select的数据结构
 * @param conditionList 需要转换的数据
 * @returns search-select组件的数据结构
 */
export const transformConditionSearchList = conditionList => {
  return conditionList.map(item => {
    if (item.children?.length) {
      item.children = transformConditionSearchList(item.children);
    }
    return { ...item, multiple: item.multiable === undefined ? item.multiple : item.multiable };
  });
};

/**
 * 处理视图部分左侧栏搜索组件bk-search-select 过滤已选得条件
 * @param conditionList 可选项
 * @param searchList 已选中的值
 * @returns 可选项
 */
export const filterSelectorPanelSearchList = (conditionList, searchList) =>
  conditionList.reduce((total, item) => {
    let isShow = true;
    if (item.children.length === 1) {
      isShow = !searchList.find(set => set.id === item.id && !!set.values);
    } else if (item.children.length > 1) {
      item.children = item.children.filter(
        child => !searchList.some(set => set.values?.some?.(val => val.id === child.id) ?? true)
      );
      if (!item.children.length) isShow = false;
    }
    if (isShow) total.push(item);
    return total;
  }, []);

/* 匹配规则通过正则匹配 */
export const matchRuleFn = (str: string, matchStr: string) => {
  let isMatch = false;
  try {
    const regex = new RegExp(matchStr);
    isMatch = regex.test(str);
  } catch (err) {
    isMatch = false;
  }
  return isMatch;
};
