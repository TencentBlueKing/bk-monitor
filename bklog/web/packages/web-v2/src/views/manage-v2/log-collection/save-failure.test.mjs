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

import { getFormValidateMessage, getSaveFailureMessage, isRequestErrorAlreadyShown } from './save-failure.ts';

describe('save-failure', () => {
  it('AC-001 prefers response message when result is false', () => {
    assert.equal(getSaveFailureMessage({ result: false, message: '集群不可用' }, '保存失败'), '集群不可用');
    assert.equal(getSaveFailureMessage({ result: false, data: { message: '名称重复' } }, '保存失败'), '名称重复');
    assert.equal(getSaveFailureMessage({ result: false }, '保存失败'), '保存失败');
  });

  it('AC-002 skips cancel and request-layer errors', () => {
    assert.equal(isRequestErrorAlreadyShown({ code: 'ERR_CANCELED' }), true);
    assert.equal(isRequestErrorAlreadyShown({ name: 'CanceledError' }), true);
    assert.equal(isRequestErrorAlreadyShown('业务码错误文案'), true);
    assert.equal(isRequestErrorAlreadyShown({ response: { status: 500 }, message: '系统出现异常' }), true);
    assert.equal(isRequestErrorAlreadyShown({ isAxiosError: true, message: 'Network Error' }), true);
    assert.equal(isRequestErrorAlreadyShown({ message: '未知失败' }), false);
  });

  it('AC-003 reads the first form validate message', () => {
    assert.equal(getFormValidateMessage({ table_id: ['请输入英文名'] }, '请完善存储配置'), '请输入英文名');
    assert.equal(getFormValidateMessage({}, '请完善存储配置'), '请完善存储配置');
  });
});
