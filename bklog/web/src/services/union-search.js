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
  method: 'post',
  url: '/search/index_set/union_search/',
};

/** 联合查询Mapping操作符 */
const unionMapping = {
  method: 'post',
  url: '/search/index_set/union_search/fields/',
};

/** 联合查询图表 */
const unionDateHistogram = {
  method: 'post',
  url: '/search/index_set/aggs/union_search/date_histogram/',
};

/** 联合查询导出日志 */
const unionExport = {
  method: 'get',
  url: '/search/index_set/union_search/export/',
};

/** 联合查询导出历史 */
const unionExportHistory = {
  method: 'get',
  url: '/search/index_set/union_search/export_history/?bk_biz_id=:bk_biz_id&page=:page&pagesize=:pagesize&show_all=:show_all&index_set_ids=:index_set_ids',
};

/** 联合查询检索历史 */
const unionSearchHistory = {
  method: 'get',
  url: '/search/index_set/union_search/history/?index_set_ids=:index_set_ids',
};

/** 联合查询标签列表 */
const unionLabelList = {
  method: 'get',
  url: '/index_set/tag/list/',
};

/** 联合查询创造标签 */
const unionCreateLabel = {
  method: 'post',
  url: '/index_set/tag/',
};

/** 索引集添加标签 */
const unionAddLabel = {
  method: 'post',
  url: '/index_set/:index_set_id/tag/add/',
};

/** 索引集删除标签 */
const unionDeleteLabel = {
  method: 'post',
  url: '/index_set/:index_set_id/tag/delete/',
};

/** 创建联合查询收藏组合 */
const unionCreateFavorite = {
  method: 'post',
  url: '/search/favorite_union/',
};

/** 删除联合查询收藏组合 */
const unionDeleteFavorite = {
  method: 'delete',
  url: '/search/favorite_union/:favorite_union_id/',
};

/** 联合查询收藏组合列表 */
const unionFavoriteList = {
  method: 'get',
  url: '/search/favorite_union/?space_uid=:space_uid',
};

/** 联合查询历史记录列表 */
const unionHistoryList = {
  method: 'post',
  url: '/search/index_set/option/history/',
};

/** 联合查询删除历史记录 */
const unionDeleteHistory = {
  method: 'post',
  url: '/search/index_set/option/history/delete/',
};

/** 联合查询删除历史记录 */
const unionTerms = {
  method: 'post',
  url: '/search/index_set/aggs/union_search/terms/',
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
