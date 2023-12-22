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
import { RouteConfig } from 'vue-router';

import * as dataRetrievalAuth from '../../pages/data-retrieval/authority-map';
import * as traceAuth from '../../pages/trace-retrieval/authority-map';
// eslint-disable-next-line max-len
// const DataRetrievalNew = () => import(/* webpackChunkName: 'DataRetrieval'*/ '../../pages/data-retrieval/data-retrieval');
const IndexRetrievalNew = () =>
  import(/* webpackChunkName: 'IndexRetrievalNew'*/ '../../pages/data-retrieval/index-retrieval');
const EventRetrievalNew = () =>
  import(/* webpackChunkName: 'EventRetrievalNew'*/ '../../pages/data-retrieval/event-retrieval');
const LogRetrievalNew = () =>
  import(/* webpackChunkName: 'LogRetrievalNew'*/ '../../pages/data-retrieval/log-retrieval');
const TraceRetrieval = () =>
  import(/* webpackChunkName: 'TraceRetrieval'*/ '../../pages/trace-retrieval/trace-retrieval');
export default [
  {
    path: '/data-retrieval',
    name: 'data-retrieval',
    components: {
      noCache: IndexRetrievalNew
    },
    meta: {
      title: '指标检索',
      navId: 'data-retrieval',
      navClass: 'data-retrieval-nav',
      noNavBar: true,
      needClearQuery: true, // 需要清空query搜索条件
      authority: {
        map: dataRetrievalAuth,
        page: dataRetrievalAuth.VIEW_AUTH
      },
      route: {
        parent: 'data'
      }
    }
  },
  {
    path: '/log-retrieval',
    name: 'log-retrieval',
    components: {
      noCache: LogRetrievalNew
    },
    meta: {
      title: '日志检索',
      navId: 'log-retrieval',
      navClass: 'log-retrieval-nav',
      noNavBar: true,
      needClearQuery: true, // 需要清空query搜索条件
      authority: {
        map: dataRetrievalAuth,
        page: dataRetrievalAuth.VIEW_AUTH
      },
      route: {
        parent: 'data'
      }
    }
  },
  {
    path: '/event-retrieval',
    name: 'event-retrieval',
    components: {
      noCache: EventRetrievalNew
    },
    meta: {
      title: '事件检索',
      navId: 'event-retrieval',
      navClass: 'event-retrieval-nav',
      noNavBar: true,
      needClearQuery: true, // 需要清空query搜索条件
      authority: {
        map: dataRetrievalAuth,
        page: dataRetrievalAuth.VIEW_AUTH
      },
      route: {
        parent: 'data'
      }
    }
  },
  {
    path: '/trace/home',
    name: 'trace-retrieval',
    components: {
      noCache: TraceRetrieval
    },
    meta: {
      title: 'Trace检索',
      navId: 'trace-retrieval',
      navClass: 'trace-retrieval-nav',
      noChangeLoading: true,
      noNavBar: true,
      needClearQuery: true, // 需要清空query搜索条件
      route: {
        parent: 'data'
      },
      authority: {
        map: traceAuth,
        page: traceAuth.VIEW_AUTH
      }
    }
  }
] as RouteConfig[];
