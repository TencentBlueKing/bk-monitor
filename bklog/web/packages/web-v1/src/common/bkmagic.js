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
 * @file 引入 bk-magic-vue 组件
 * @author <>
 */

import Vue from 'vue';
import { bkMessage } from 'bk-magic-vue';

export const messageError = (message, delay = 3000, ellipsisLine = 0) => {
  bkMessage({
    message,
    delay,
    ellipsisLine,
    theme: 'error',
    zIndex: 9999,
  });
};

export const messageSuccess = (message, delay = 3000, ellipsisLine = 0) => {
  bkMessage({
    message,
    delay,
    ellipsisLine,
    theme: 'success',
    zIndex: 9999,
  });
};

export const messageInfo = (message, delay = 3000, ellipsisLine = 0) => {
  bkMessage({
    message,
    delay,
    ellipsisLine,
    theme: 'primary',
    zIndex: 9999,
  });
};

export const messageWarn = (message, delay = 3000, ellipsisLine = 0) => {
  bkMessage({
    message,
    delay,
    ellipsisLine,
    theme: 'warning',
    zIndex: 9999,
  });
};

Vue.prototype.messageError = messageError;
Vue.prototype.messageSuccess = messageSuccess;
Vue.prototype.messageInfo = messageInfo;
Vue.prototype.messageWarn = messageWarn;
