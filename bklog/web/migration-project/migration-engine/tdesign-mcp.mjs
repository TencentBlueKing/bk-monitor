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

import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdir, writeFile } from 'node:fs/promises';
const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(here, '../../packages/web-v3/package.json'));
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StreamableHTTPClientTransport } = require('@modelcontextprotocol/sdk/client/streamableHttp.js');
const operation = process.argv[2] || 'list';
const names = process.argv.slice(3);
const operations = { list: 'get-component-list', docs: 'get-component-docs', dom: 'get-component-dom' };
if (!operations[operation] || (operation !== 'list' && !names.length))
  throw new Error('Usage: node tdesign-mcp.mjs list | docs|dom component...');
const client = new Client({ name: 'bklog-vue3-migration', version: '1.0.0' });
try {
  await client.connect(new StreamableHTTPClientTransport(new URL('http://mcp.tdesign.woa.com/mcp')));
  const { tools } = await client.listTools();
  if (!tools.some(tool => tool.name === operations[operation]))
    throw new Error('Official MCP does not expose requested documentation tool');
  const result = await client.callTool({
    name: operations[operation],
    arguments: { framework: 'vue-next', ...(names.length ? { names } : {}) },
  });
  if (result.isError) throw new Error(JSON.stringify(result.content));
  const dir = resolve(here, '../artifacts/tdesign');
  await mkdir(dir, { recursive: true });
  const output = resolve(dir, `${operation}-${names.join('-') || 'components'}.json`);
  await writeFile(
    output,
    `${JSON.stringify({ fetchedAt: new Date().toISOString(), endpoint: 'http://mcp.tdesign.woa.com/mcp', framework: 'vue-next', result }, null, 2)}\n`,
  );
  console.log(output);
} finally {
  await client.close();
}
