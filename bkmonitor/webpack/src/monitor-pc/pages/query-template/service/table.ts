/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { destroyQueryTemplate, relationsQueryTemplate, searchQueryTemplate } from 'monitor-api/modules/model';
import { bkMessage, makeMessage } from 'monitor-api/utils';

import type {
  QueryListRequestParams,
  QueryTemplateListItem,
  QueryTemplateRelationItem,
  QueryTemplateRelationsRequestParams,
} from '../typings';

/**
 *
 * @description
 * 处理查询模板列表接口返回数据
 * 由于查询模板接口直接返回的数据是没有 relation_config_count 关联场景字段的，需要另外请求接口异步获取
 * 兼容 vue2 响应式需要在数据结构中先定义 relation_config_count 字段
 * 同时由于该逻辑是全量遍历，同时将异步获取关联场景接口的参数 query_template_ids 拼接成数组
 * @param templateList
 * @returns 需要请求关联场景接口的 query_template_ids 数组
 */
const formatTemplateList = (
  templateList: QueryTemplateListItem[],
  relationsMap?: Record<
    QueryTemplateRelationItem['query_template_id'],
    QueryTemplateRelationItem['relation_config_count']
  >
) => {
  const defaultValue = relationsMap ? 0 : null;
  return templateList.reduce((prev, curr) => {
    curr.relation_config_count = relationsMap?.[curr.id] ?? defaultValue;
    prev.push(curr.id);
    return prev;
  }, []);
};

/**
 * @description 请求错误时消息提示处理逻辑（ cancel 类型报错不进行提示）
 * @param err
 *
 */
const requestErrorMessage = err => {
  const message = makeMessage(err.error_details || err.message);
  let isAborted = false;
  if (message && err?.message !== 'canceled' && err?.message !== 'aborted') {
    bkMessage(message);
  } else {
    isAborted = true;
  }
  return isAborted;
};

/**
 * @description 获取查询模板列表
 * @param {QueryListRequestParams} 查询参数
 * @returns {QueryTemplateListItem[]} 查询模板列表数据
 */
export const fetchQueryTemplateList = async (param: QueryListRequestParams, requestConfig = {}) => {
  const config = { needMessage: false, ...requestConfig };
  let isAborted = false;
  const { total, list: templateList } = await searchQueryTemplate<{ list: QueryTemplateListItem[]; total: number }>(
    param,
    config
  ).catch(err => {
    isAborted = requestErrorMessage(err);
    return {
      total: 0,
      list: [] as QueryTemplateListItem[],
    };
  });
  const ids = formatTemplateList(templateList);
  if (ids?.length && !isAborted) {
    fetchQueryTemplateRelationsCount({ query_template_ids: ids }, requestConfig).then(res => {
      if (res.isAborted) return;
      const countByIdMap = res?.list?.reduce?.((prev, curr) => {
        prev[curr.query_template_id] = curr.relation_config_count;
        return prev;
      }, {});
      formatTemplateList(templateList, countByIdMap);
    });
  }
  return { total, templateList, isAborted };
};

/**
 * @description 获取查询模板关联数量
 * @param {QueryListRequestParams} 查询参数
 * @returns {number} 关联数量
 */
export const fetchQueryTemplateRelationsCount = async (
  param: QueryTemplateRelationsRequestParams,
  requestConfig = {}
) => {
  const config = { needMessage: false, ...requestConfig };
  let isAborted = false;
  const relationList = await relationsQueryTemplate<QueryTemplateRelationItem[]>(param, config).catch(err => {
    isAborted = requestErrorMessage(err);
    return [] as QueryTemplateRelationItem[];
  });
  return { list: relationList, isAborted };
};

/**
 * @description 删除查询模板
 * @param {string} id 查询模板 id
 */
export const destroyQueryTemplateById = async (id: QueryTemplateListItem['id']) => {
  return destroyQueryTemplate(id);
};
