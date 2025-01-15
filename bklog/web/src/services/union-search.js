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

/** 联合检索 */
const unionSearch = {
  url: '/search/index_set/union_search/',
  method: 'post',
};

/** 联合查询Mapping操作符 */
const unionMapping = {
  url: '/search/index_set/union_search/fields/',
  method: 'post',
};

/** 联合查询图表 */
const unionDateHistogram = {
  url: '/search/index_set/aggs/union_search/date_histogram/',
  method: 'post',
};

/** 联合查询导出日志 */
const unionExport = {
  url: '/search/index_set/union_search/export/',
  method: 'get',
};

/** 联合查询导出历史 */
const unionExportHistory = {
  url: '/search/index_set/union_search/export_history/?bk_biz_id=:bk_biz_id&page=:page&pagesize=:pagesize&show_all=:show_all&index_set_ids=:index_set_ids',
  method: 'get',
};

/** 联合查询检索历史 */
const unionSearchHistory = {
  url: '/search/index_set/union_search/history/?index_set_ids=:index_set_ids',
  method: 'get',
};

/** 联合查询标签列表 */
const unionLabelList = {
  url: '/index_set/tag/list/',
  method: 'get',
};

/** 联合查询创造标签 */
const unionCreateLabel = {
  url: '/index_set/tag/',
  method: 'post',
};

/** 索引集添加标签 */
const unionAddLabel = {
  url: '/index_set/:index_set_id/tag/add/',
  method: 'post',
};

/** 索引集删除标签 */
const unionDeleteLabel = {
  url: '/index_set/:index_set_id/tag/delete/',
  method: 'post',
};

/** 创建联合查询收藏组合 */
const unionCreateFavorite = {
  url: '/search/favorite_union/',
  method: 'post',
};

/** 删除联合查询收藏组合 */
const unionDeleteFavorite = {
  url: '/search/favorite_union/:favorite_union_id/',
  method: 'delete',
};

/** 联合查询收藏组合列表 */
const unionFavoriteList = {
  url: '/search/favorite_union/?space_uid=:space_uid',
  method: 'get',
};

/** 联合查询历史记录列表 */
const unionHistoryList = {
  url: '/search/index_set/option/history/',
  method: 'post',
};

/** 联合查询删除历史记录 */
const unionDeleteHistory = {
  url: '/search/index_set/option/history/delete/',
  method: 'post',
};

/** 联合查询删除历史记录 */
const unionTerms = {
  url: '/search/index_set/aggs/union_search/terms/',
  method: 'post',
};

export {
  unionSearch,
  unionMapping,
  unionDateHistogram,
  unionExport,
  unionExportHistory,
  unionSearchHistory,
  unionLabelList,
  unionCreateLabel,
  unionAddLabel,
  unionDeleteLabel,
  unionCreateFavorite,
  unionDeleteFavorite,
  unionFavoriteList,
  unionHistoryList,
  unionDeleteHistory,
  unionTerms,
};
