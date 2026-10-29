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

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { upgradeImports } from './seed-native-source.mjs';
test('only actual module references change; business text, handlers and comments remain identical',()=>{
 const source=`// vue-router/composables
import {useRoute} from 'vue-router/composables';
const text='vue-router/composables';
const handler=()=>api.request('search',{addition:fullConditions,permission:permissions});`;
 const result=upgradeImports(source,'component.ts');
 assert.equal(result.code, source.replace("from 'vue-router/composables'", 'from "vue-router"'));
});
test('Vue SFC template and styles are preserved while Vue3 library entry changes',()=>{
 const source=`<template><div @click="handle">vue-router/composables</div></template><script lang="ts">import Picker from '@blueking/date-picker/vue2';</script><style>.vue2{display:flex}</style>`;
 const result=upgradeImports(source,'component.vue');
 assert.equal(result.code,source.replace("'@blueking/date-picker/vue2'",'"@blueking/date-picker"'));
});
