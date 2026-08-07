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
 * worker-loader 的包装 loader，供 Monitor 嵌入构建内联 Worker 使用。
 *
 * Monitor 产物是 CommonJS 库（externalsType: "commonjs"、library.type: "commonjs"），
 * 而 worker-loader 会把父编译的 externals / output 原样带到 Worker 子编译上
 * （见 worker-loader/dist/index.js 中的 ExternalsPlugin 与 createChildCompiler）。
 * 于是 Worker 产物里会出现 require("vue") / require("dayjs")，
 * 而 Blob Worker 没有 CommonJS 运行时，运行期直接抛
 * "Uncaught ReferenceError: require is not defined"。
 *
 * 因此这里在 pitch 的同步窗口内把父编译选项临时改成「浏览器 Worker 自包含」语义：
 * 外部依赖一律打进 Worker，不再产出 require()。
 * webpack 的 createChildCompiler 是同步展开 compiler.options 的，
 * ExternalsPlugin 也在 pitch 同步段内完成构造，
 * 所以同一个 tick 内改完即还原，不会被其它 loader 观察到。
 */

const workerLoader = require('worker-loader');

/** Worker 子编译需要覆盖的父编译选项。undefined 表示删除该项。 */
const WORKER_COMPILER_OVERRIDES = {
  // 外部依赖必须打进 Blob，Worker 里没有 require / 宿主全局变量可用。
  externals: undefined,
  externalsType: undefined,
};

/** Worker 子编译需要覆盖的 output 选项。 */
const WORKER_OUTPUT_OVERRIDES = {
  // Worker 入口不是库，不需要 CommonJS 库包装。
  library: undefined,
  // 经典 Worker 用 importScripts 加载分片，与 commonjs chunkFormat 不兼容。
  chunkFormat: 'array-push',
  chunkLoading: 'import-scripts',
  workerChunkLoading: 'import-scripts',
};

const applyOverrides = (target, overrides) => {
  const previous = {};
  for (const [key, value] of Object.entries(overrides)) {
    previous[key] = target[key];
    if (value === undefined) {
      delete target[key];
    } else {
      target[key] = value;
    }
  }
  return previous;
};

const restoreOverrides = (target, previous) => {
  for (const [key, value] of Object.entries(previous)) {
    if (value === undefined) {
      delete target[key];
    } else {
      target[key] = value;
    }
  }
};

function pitch(...args) {
  const options = this._compiler?.options;
  if (!options) {
    return workerLoader.pitch.apply(this, args);
  }

  const previousOptions = applyOverrides(options, WORKER_COMPILER_OVERRIDES);
  const previousOutput = applyOverrides(options.output ?? {}, WORKER_OUTPUT_OVERRIDES);

  try {
    return workerLoader.pitch.apply(this, args);
  } finally {
    restoreOverrides(options.output ?? {}, previousOutput);
    restoreOverrides(options, previousOptions);
  }
}

// loader-runner 对 object 形态取 module.default 作为 normal loader、module.pitch 作为 pitch。
// 用对象导出可避免给 worker-loader 自身的导出函数挂属性。
module.exports = {
  default: workerLoader,
  pitch,
};
