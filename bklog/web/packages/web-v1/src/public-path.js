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

/**
 * @file webpack public path config
 * @author <>
 */

// 支持通过 window.__WEBPACK_PUBLIC_PATH__ 全局变量动态设置 public path
// 如果设置了该变量，优先使用该变量的值来覆盖 webpack 配置中的 publicPath
// 否则使用 webpack 配置中的默认值（'auto' 模式会根据入口文件位置自动计算相对路径）
// 如果既没有设置全局变量，也不是 'auto' 模式，则使用传统逻辑：生产环境使用 BK_STATIC_URL，开发环境使用 '/'
if (typeof window !== 'undefined' && window.__WEBPACK_PUBLIC_PATH__ !== undefined) {
  // 使用全局变量设置的路径，确保以 '/' 结尾
  const customPath = window.__WEBPACK_PUBLIC_PATH__;
  __webpack_public_path__ = customPath.endsWith('/') ? customPath : `${customPath}/`;
} else if (process.env.NODE_ENV === 'production' && window.BK_STATIC_URL) {
  // 生产环境且未设置全局变量时，使用 BK_STATIC_URL
  __webpack_public_path__ = `${window.BK_STATIC_URL}/`;
} else if (process.env.NODE_ENV !== 'production') {
  // 开发环境且未设置全局变量时，使用 '/'
  __webpack_public_path__ = '/';
}
// 如果以上条件都不满足，则使用 webpack 配置中的 'auto' 模式（不设置 __webpack_public_path__）
