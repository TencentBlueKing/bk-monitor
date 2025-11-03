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

import http from '@/api';

const linkMap = {
  logExtract: 'UserGuide/ProductFeatures/log-analysis/customize-analyzer.md', // 日志清洗
  docCenter: 'UserGuide/Intro/README.md', // 产品文档
  logArchive: 'UserGuide/ProductFeatures/tools/log_archive.md', // 日志归档
  logCollection: 'UserGuide/ProductFeatures/integrations-logs/logs_overview.md', // 日志采集接入
  bkBase: 'BK-Base/UserGuide/Introduction/intro.md', // 基础计算平台
  queryString: 'UserGuide/ProductFeatures/data-visualization/query_string.md', // 查询语句语法
};

class ManageHelper {
  handleGotoLink(id: string) {
    const link = linkMap[id];
    if (link) {
      http
        .request('docs/getDocLink', {
          query: {
            md_path: link,
          },
        })
        .then(res => {
          window.open(res.data, '_blank');
        })
        .catch(() => false);
    }
  }
}

export default new ManageHelper();
