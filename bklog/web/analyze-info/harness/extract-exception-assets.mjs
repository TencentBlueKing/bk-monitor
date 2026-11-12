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

import {readFileSync, writeFileSync, mkdirSync, copyFileSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {createHash} from 'node:crypto';
const [source, output] = process.argv.slice(2);
if (!source || !output) throw new Error('EXCEPTION_SOURCE_AND_OUTPUT_REQUIRED');
const text = readFileSync(source, 'utf8');
const names = {permissions:'403', notFound:'404', maintain:'500', Building:'building', empty:'empty', searchEmpty:'search-empty', login:'login'};
const matches = [...text.matchAll(/var ([\w$]+) = new Image\(\); \1\.src = 'data:image\/svg\+xml;base64,([^']+)'; var (\w+) = \1\.src;/g)];
const assets = [];
mkdirSync(output, {recursive:true});
for (const match of matches) {
 const type = names[match[3]];if (!type) continue;
 const body = Buffer.from(match[2], 'base64');
 if (!body.toString('utf8').includes('<svg')) throw new Error('INVALID_EXCEPTION_SVG');
 const file = type + '.svg';writeFileSync(resolve(output,file),body);
 assets.push({type,file,sha256:createHash('sha256').update(body).digest('hex'),bytes:body.length});
}
if (assets.length !== 7) throw new Error('EXCEPTION_ASSET_SET_INCOMPLETE');
const packageRoot = resolve(dirname(source),'..');
const pkg = JSON.parse(readFileSync(resolve(packageRoot,'package.json'),'utf8'));
copyFileSync(resolve(packageRoot,'License.txt'),resolve(output,'License.txt'));
writeFileSync(resolve(output,'origin.json'),JSON.stringify({package:pkg.name,version:pkg.version,license:'MIT',source:'lib/exception.js',sourceSha256:createHash('sha256').update(text).digest('hex'),generation:'byte-identical SVG payload extraction; no runtime dependency on the original component library',assets},null,2)+'\n');
console.log(JSON.stringify({status:'EXTRACTED_ORIGINAL_ASSETS',assets:assets.length,package:pkg.name,version:pkg.version}));
