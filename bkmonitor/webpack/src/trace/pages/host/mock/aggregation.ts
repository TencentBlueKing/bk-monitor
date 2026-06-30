/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import type { CompareTargetOption } from '../types/aggregation';

/** 目标对比 - 当前主目标（mock，后续由选中主机节点提供） */
export const MOCK_CURRENT_TARGET: CompareTargetOption = {
  id: '0-11.147.2.124',
  name: '11.147.2.124',
};

/** 目标对比 - 可选目标列表（mock） */
export const MOCK_COMPARE_TARGETS: CompareTargetOption[] = [
  { id: '0-11.34.234.2', name: '11.34.234.2' },
  { id: '0-234.223.22.1', name: '234.223.22.1' },
  { id: '0-11.147.2.125', name: '11.147.2.125' },
  { id: '0-11.147.2.126', name: '11.147.2.126' },
  { id: '0-192.168.1.10', name: '192.168.1.10' },
  { id: '0-192.168.1.11', name: '192.168.1.11' },
];
