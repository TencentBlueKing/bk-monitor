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
type LogSearchFunction = (indexSetId: number, bizId: number, params: any) => void;

const { bklogsearch_host: bklogsearchHost } = window;
const origin = process.env.NODE_ENV === 'development' ? process.env.proxyUrl : location.origin;
/**
 * 跳转到日志检索
 * @param indexSetId 索引集id
 * @param bizId
 * @param params
 * @returns
 */
const tologSearch: LogSearchFunction = (indexSetId, bizId, params) => {
  if (params) {
    window.open(`${bklogsearchHost}#/retrieve/${indexSetId}?bizId=${bizId}`);
    return;
  }
  window.open(
    `${bklogsearchHost}#/retrieve/${indexSetId}?bizId=${bizId}&retrieveParams=${encodeURI(JSON.stringify(params))}`
  );
};

type PerformanceDetailFunction = (bizId: number, id: string) => void;
/**
 * 跳转到主机详情
 * @param bizId
 * @param id
 */
const toPerformanceDetail: PerformanceDetailFunction = (bizId, id) => {
  window.open(`${origin}${location.pathname.toString().replace('fta/', '')}?bizId=${bizId}#/performance/detail/${id}`);
};

/**
 * 跳转到策略详情
 * @param bizId
 * @param id
 */
const toStrategyConfigDetail: PerformanceDetailFunction = (bizId, id) => {
  window.open(
    `${origin}${location.pathname.toString().replace('fta/', '')}?bizId=${bizId}#/strategy-config/detail/${id}`
  );
};

/**
 * 集群管理跳转到bcs
 * @param projectName
 * @param bcsClusterId
 */
const toBcsDetail: PerformanceDetailFunction = (projectName, bcsClusterId) => {
  window.open(`${window.bk_bcs_url}bcs/projects/${projectName}/clusters?clusterId=${bcsClusterId}&active=info`);
};

export { toBcsDetail, tologSearch, toPerformanceDetail, toStrategyConfigDetail };
