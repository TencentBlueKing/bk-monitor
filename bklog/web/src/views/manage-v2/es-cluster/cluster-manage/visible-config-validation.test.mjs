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

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { hasEmptyDorisBizAttrValue } from './visible-config-validation.ts';

describe('visible-config-validation', () => {
  it('allows empty other labels when space_type is non-empty', () => {
    assert.equal(
      hasEmptyDorisBizAttrValue([
        { id: 'space_type', values: [{ id: 'bkci' }] },
        { id: 'biz_property', values: [] },
      ]),
      false,
    );
  });

  it('requires every label to have values when space_type is absent', () => {
    assert.equal(hasEmptyDorisBizAttrValue([{ id: 'biz_property', values: [] }]), true);
  });

  it('requires every label to have values when space_type is empty', () => {
    assert.equal(
      hasEmptyDorisBizAttrValue([
        { id: 'space_type', values: [] },
        { id: 'biz_property', values: [{ id: 'value_a' }] },
      ]),
      true,
    );
  });

  it('allows all labels to have values', () => {
    assert.equal(
      hasEmptyDorisBizAttrValue([
        { id: 'space_type', values: [{ id: 'bkci' }] },
        { id: 'biz_property', values: [{ id: 'value_a' }] },
      ]),
      false,
    );
  });
});
