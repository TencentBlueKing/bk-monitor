/* eslint-disable codecc/comment-ratio */
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

export const PROFILING_QUERY_DATA = {
  flame_data: {
    name: 'total',
    value: 480000000,
    children: [
      {
        id: 16,
        name: 'net/http.(*conn).serve',
        value: 460000000,
        self: 0,
        children: [
          {
            id: 15,
            name: 'net/http.serverHandler.ServeHTTP',
            value: 460000000,
            self: 0,
            children: [
              {
                id: 14,
                name: 'github.com/gin-gonic/gin.(*Engine).ServeHTTP',
                value: 460000000,
                self: 0,
                children: [
                  {
                    id: 13,
                    name: 'github.com/gin-gonic/gin.(*Engine).handleHTTPRequest',
                    value: 460000000,
                    self: 0,
                    children: [
                      {
                        id: 12,
                        name: 'github.com/gin-gonic/gin.LoggerWithConfig.func1',
                        value: 460000000,
                        self: 0,
                        children: [
                          {
                            id: 11,
                            name: 'github.com/gin-gonic/gin.CustomRecoveryWithWriter.func1',
                            value: 460000000,
                            self: 0,
                            children: [
                              {
                                id: 9,
                                name: 'github.com/gin-gonic/gin.(*Context).Next',
                                value: 460000000,
                                self: 0,
                                children: [
                                  {
                                    id: 10,
                                    name: 'go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin.Middleware.func1',
                                    value: 460000000,
                                    self: 0,
                                    children: [
                                      {
                                        id: 8,
                                        name: 'main.main.func2',
                                        value: 450000000,
                                        self: 10000000,
                                        children: [
                                          {
                                            id: 7,
                                            name: 'main.generateRandomNumbers',
                                            value: 440000000,
                                            self: 20000000,
                                            children: [
                                              {
                                                id: 6,
                                                name: 'math/rand.Intn',
                                                value: 420000000,
                                                self: 20000000,
                                                children: [
                                                  {
                                                    id: 5,
                                                    name: 'math/rand.(*Rand).Intn',
                                                    value: 400000000,
                                                    self: 60000000,
                                                    children: [
                                                      {
                                                        id: 2,
                                                        name: 'math/rand.(*Rand).Int63',
                                                        value: 340000000,
                                                        self: 0,
                                                        children: [
                                                          {
                                                            id: 3,
                                                            name: 'math/rand.(*Rand).Int31',
                                                            value: 340000000,
                                                            self: 0,
                                                            children: [
                                                              {
                                                                id: 4,
                                                                name: 'math/rand.(*Rand).Int31n',
                                                                value: 340000000,
                                                                self: 30000000,
                                                                children: [
                                                                  {
                                                                    id: 1,
                                                                    name: 'math/rand.(*lockedSource).Int63',
                                                                    value: 160000000,
                                                                    self: 160000000,
                                                                    children: []
                                                                  },
                                                                  {
                                                                    id: 17,
                                                                    name: 'math/rand.(*rngSource).Uint64',
                                                                    value: 30000000,
                                                                    self: 0,
                                                                    children: [
                                                                      {
                                                                        id: 18,
                                                                        name: 'math/rand.(*rngSource).Int63',
                                                                        value: 30000000,
                                                                        self: 30000000,
                                                                        children: []
                                                                      }
                                                                    ]
                                                                  },
                                                                  {
                                                                    id: 19,
                                                                    name: 'sync.(*Mutex).Unlock',
                                                                    value: 120000000,
                                                                    self: 110000000,
                                                                    children: [
                                                                      {
                                                                        id: 21,
                                                                        name: 'runtime.asyncPreempt',
                                                                        value: 10000000,
                                                                        self: 10000000,
                                                                        children: []
                                                                      }
                                                                    ]
                                                                  }
                                                                ]
                                                              }
                                                            ]
                                                          }
                                                        ]
                                                      }
                                                    ]
                                                  }
                                                ]
                                              }
                                            ]
                                          }
                                        ]
                                      },
                                      {
                                        id: 20,
                                        name: 'main.findMax',
                                        value: 10000000,
                                        self: 10000000,
                                        children: []
                                      }
                                    ]
                                  }
                                ]
                              }
                            ]
                          }
                        ]
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      },
      {
        id: 28,
        name: 'runtime.mcall',
        value: 20000000,
        self: 0,
        children: [
          {
            id: 27,
            name: 'runtime.park_m',
            value: 20000000,
            self: 0,
            children: [
              {
                id: 26,
                name: 'runtime.schedule',
                value: 10000000,
                self: 0,
                children: [
                  {
                    id: 25,
                    name: 'runtime.findRunnable',
                    value: 10000000,
                    self: 0,
                    children: [
                      {
                        id: 24,
                        name: 'runtime.stealWork',
                        value: 10000000,
                        self: 0,
                        children: [
                          {
                            id: 22,
                            name: 'runtime/internal/atomic.(*Int64).Load',
                            value: 10000000,
                            self: 0,
                            children: [
                              {
                                id: 23,
                                name: 'runtime.checkTimers',
                                value: 10000000,
                                self: 10000000,
                                children: []
                              }
                            ]
                          }
                        ]
                      }
                    ]
                  }
                ]
              },
              {
                id: 31,
                name: 'runtime.execute',
                value: 10000000,
                self: 0,
                children: [
                  {
                    id: 30,
                    name: 'runtime.setThreadCPUProfiler',
                    value: 10000000,
                    self: 0,
                    children: [
                      {
                        id: 29,
                        name: 'runtime.timer_settime',
                        value: 10000000,
                        self: 10000000,
                        children: []
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ],
    id: 0
  },
  type: 'cpu',
  unit: 'nanoseconds',
  table_data: [
    {
      id: 0,
      name: 'total',
      self: 480000000,
      total: 480000000
    },
    {
      id: 16,
      name: 'net/http.(*conn).serve',
      self: 0,
      total: 460000000
    },
    {
      id: 15,
      name: 'net/http.serverHandler.ServeHTTP',
      self: 0,
      total: 460000000
    },
    {
      id: 14,
      name: 'github.com/gin-gonic/gin.(*Engine).ServeHTTP',
      self: 0,
      total: 460000000
    },
    {
      id: 13,
      name: 'github.com/gin-gonic/gin.(*Engine).handleHTTPRequest',
      self: 0,
      total: 460000000
    },
    {
      id: 12,
      name: 'github.com/gin-gonic/gin.LoggerWithConfig.func1',
      self: 0,
      total: 460000000
    },
    {
      id: 11,
      name: 'github.com/gin-gonic/gin.CustomRecoveryWithWriter.func1',
      self: 0,
      total: 460000000
    },
    {
      id: 9,
      name: 'github.com/gin-gonic/gin.(*Context).Next',
      self: 0,
      total: 460000000
    },
    {
      id: 10,
      name: 'go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin.Middleware.func1',
      self: 0,
      total: 460000000
    },
    {
      id: 8,
      name: 'main.main.func2',
      self: 10000000,
      total: 450000000
    },
    {
      id: 7,
      name: 'main.generateRandomNumbers',
      self: 20000000,
      total: 440000000
    },
    {
      id: 6,
      name: 'math/rand.Intn',
      self: 20000000,
      total: 420000000
    },
    {
      id: 5,
      name: 'math/rand.(*Rand).Intn',
      self: 60000000,
      total: 400000000
    },
    {
      id: 2,
      name: 'math/rand.(*Rand).Int63',
      self: 0,
      total: 340000000
    },
    {
      id: 3,
      name: 'math/rand.(*Rand).Int31',
      self: 0,
      total: 340000000
    },
    {
      id: 4,
      name: 'math/rand.(*Rand).Int31n',
      self: 30000000,
      total: 340000000
    },
    {
      id: 1,
      name: 'math/rand.(*lockedSource).Int63',
      self: 160000000,
      total: 160000000
    },
    {
      id: 19,
      name: 'sync.(*Mutex).Unlock',
      self: 110000000,
      total: 120000000
    },
    {
      id: 17,
      name: 'math/rand.(*rngSource).Uint64',
      self: 0,
      total: 30000000
    },
    {
      id: 18,
      name: 'math/rand.(*rngSource).Int63',
      self: 30000000,
      total: 30000000
    },
    {
      id: 28,
      name: 'runtime.mcall',
      self: 0,
      total: 20000000
    },
    {
      id: 27,
      name: 'runtime.park_m',
      self: 0,
      total: 20000000
    },
    {
      id: 20,
      name: 'main.findMax',
      self: 10000000,
      total: 10000000
    },
    {
      id: 21,
      name: 'runtime.asyncPreempt',
      self: 10000000,
      total: 10000000
    },
    {
      id: 26,
      name: 'runtime.schedule',
      self: 0,
      total: 10000000
    },
    {
      id: 25,
      name: 'runtime.findRunnable',
      self: 0,
      total: 10000000
    },
    {
      id: 24,
      name: 'runtime.stealWork',
      self: 0,
      total: 10000000
    },
    {
      id: 22,
      name: 'runtime/internal/atomic.(*Int64).Load',
      self: 0,
      total: 10000000
    },
    {
      id: 23,
      name: 'runtime.checkTimers',
      self: 10000000,
      total: 10000000
    },
    {
      id: 31,
      name: 'runtime.execute',
      self: 0,
      total: 10000000
    },
    {
      id: 30,
      name: 'runtime.setThreadCPUProfiler',
      self: 0,
      total: 10000000
    },
    {
      id: 29,
      name: 'runtime.timer_settime',
      self: 10000000,
      total: 10000000
    }
  ],
  table_all: 480000000
};
