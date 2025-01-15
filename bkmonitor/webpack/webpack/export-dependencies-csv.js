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
const path = require('node:path');
const file = require('node:fs');
const paths = [
  './package.json',
  './src/apm/package.json',
  './src/fta-solutions/package.json',
  './src/monitor-api/package.json',
  './src/monitor-common/package.json',
  './src/monitor-mobile/package.json',
  './src/monitor-pc/package.json',
  './src/monitor-static/package.json',
  './src/monitor-ui/package.json',
  // './src/trace/package.json'
];
const tracePath = './src/trace/package.json';
let setData = {};
paths.forEach(p => {
  const json = file.readFileSync(path.resolve(__dirname, p));
  const data = JSON.parse(json);
  setData = { ...setData, ...data.devDependencies, ...data.dependencies };
});
const list = Object.keys(setData).map(name => {
  const value = setData[name].replace(/[\^~]/, '');
  let path = name;
  if (path.includes('@')) {
    path = name.replace(/^@[^/]*\//gim, '');
  }
  return {
    name,
    value,
    link: value.includes('http') ? value : `https://registry.npmjs.org/${name}/-/${path}-${value}.tgz`,
  };
});

const json = file.readFileSync(path.resolve(__dirname, tracePath));
const data = JSON.parse(json);
const traceData = { ...data.devDependencies, ...data.dependencies };
Object.keys(traceData).forEach(name => {
  const value = traceData[name].replace(/[\^~]/, '');
  const item = list.find(set => set.name === name && set.value === value);
  if (!item) {
    let path = name;
    console.info(name);
    if (path.includes('@')) {
      path = name.replace(/^@[^/]*\//gim, '');
    }
    list.push({
      name,
      value,
      link: value.includes('http') ? value : `https://registry.npmjs.org/${name}/-/${path}-${value}.tgz`,
    });
  }
});
const jsonToExcel = (data, head = 'name,value,link', name = './前端依赖.csv') => {
  let str = head ? `${head}\n` : '';
  data.forEach(item => {
    Object.keys(item).forEach(key => {
      str = `${`${str + item[key]}\t`},`;
    });
    str += '\n';
  });
  file.writeFileSync(name, str);
};
jsonToExcel(list);
