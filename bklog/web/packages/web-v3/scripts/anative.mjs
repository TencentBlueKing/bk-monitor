#!/usr/bin/env node
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

import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const nativeRoot = join(root, '.ai-native');

const SPEC_KIND_DIR = {
  feature: 'features',
  data: 'data',
  state: 'state',
  ui: 'ui',
  action: 'actions',
  test: 'test-cases',
};

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function listJson(dir) {
  return readdirSync(dir)
    .filter(name => name.endsWith('.json'))
    .map(name => join(dir, name));
}

function typeOf(value) {
  if (Array.isArray(value)) return 'array';
  if (value === null) return 'null';
  return typeof value;
}

function validateAgainstSchema(data, schema, path = '$') {
  const errors = [];
  if (schema.type && typeOf(data) !== schema.type) {
    errors.push(`${path} expected ${schema.type}`);
    return errors;
  }
  if (schema.enum && !schema.enum.includes(data)) {
    errors.push(`${path} not in enum`);
  }
  if (schema.pattern && typeof data === 'string' && !new RegExp(schema.pattern).test(data)) {
    errors.push(`${path} does not match ${schema.pattern}`);
  }
  if (schema.minLength && typeof data === 'string' && data.length < schema.minLength) {
    errors.push(`${path} shorter than ${schema.minLength}`);
  }
  if (schema.minItems && Array.isArray(data) && data.length < schema.minItems) {
    errors.push(`${path} needs at least ${schema.minItems} items`);
  }
  if (schema.type === 'object') {
    for (const key of schema.required || []) {
      if (!(key in data)) errors.push(`${path}.${key} is required`);
    }
    if (schema.additionalProperties === false) {
      const allowed = new Set(Object.keys(schema.properties || {}));
      for (const key of Object.keys(data)) {
        if (!allowed.has(key)) errors.push(`${path}.${key} is not allowed`);
      }
    }
    for (const [key, childSchema] of Object.entries(schema.properties || {})) {
      if (key in data) errors.push(...validateAgainstSchema(data[key], childSchema, `${path}.${key}`));
    }
  }
  if (schema.type === 'array' && schema.items && Array.isArray(data)) {
    data.forEach((item, index) => {
      errors.push(...validateAgainstSchema(item, schema.items, `${path}[${index}]`));
    });
  }
  return errors;
}

function loadSpecs() {
  const specs = {};
  for (const [kind, dirName] of Object.entries(SPEC_KIND_DIR)) {
    specs[kind] = listJson(join(nativeRoot, 'specs', dirName))
      .map(readJson)
      .filter(item => item.id);
  }
  return specs;
}

export function validateSpecs() {
  const errors = [];
  const specs = loadSpecs();
  for (const [kind, items] of Object.entries(specs)) {
    const schema = readJson(join(nativeRoot, 'schemas', `${kind}.schema.json`));
    for (const item of items) {
      errors.push(...validateAgainstSchema(item, schema, item.id));
    }
  }
  return { ok: errors.length === 0, errors, counts: Object.fromEntries(Object.entries(specs).map(([k, v]) => [k, v.length])) };
}

export function checkContracts() {
  const specs = loadSpecs();
  const errors = [];
  const ids = new Set(Object.values(specs).flat().map(item => item.id));
  for (const feature of specs.feature) {
    for (const dep of feature.dependencies || []) {
      if (!ids.has(dep)) errors.push(`${feature.id} missing dependency ${dep}`);
    }
  }
  for (const test of specs.test) {
    if (!ids.has(test.feature)) errors.push(`${test.id} missing feature ${test.feature}`);
    const feature = specs.feature.find(item => item.id === test.feature);
    const acceptanceIds = new Set((feature?.acceptance || []).map(item => item.id));
    for (const scenario of test.scenarios || []) {
      if (!acceptanceIds.has(scenario.acceptance)) {
        errors.push(`${test.id} scenario ${scenario.id} missing acceptance ${scenario.acceptance}`);
      }
    }
  }
  return { ok: errors.length === 0, errors };
}

export function analyzeImpact() {
  const graph = readJson(join(nativeRoot, 'impact', 'retrieve-search.json'));
  return {
    ok: true,
    feature: graph.feature,
    files: graph.nodes.filter(node => node.type === 'file').map(node => node.id),
    tests: graph.nodes.filter(node => node.type === 'test').map(node => node.id),
  };
}

function print(result) {
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  process.exitCode = result.ok ? 0 : 1;
}

const [, , command, sub] = process.argv;
const key = `${command || ''} ${sub || ''}`.trim();

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith('anative.mjs')) {
  if (key === 'spec validate') print(validateSpecs());
  else if (key === 'contract check') print(checkContracts());
  else if (key === 'impact analyze') print(analyzeImpact());
  else {
    process.stdout.write('anative <spec validate|contract check|impact analyze>\n');
    process.exitCode = command ? 1 : 0;
  }
}
