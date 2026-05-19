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

// 获取Grok列表
const getGrokList = {
  url: '/databus/grok/',
  method: 'get',
};

// 创建Grok
const createGrok = {
  url: '/databus/grok/',
  method: 'post',
};

// 更新Grok
const updateGrok = {
  url: '/databus/grok/:id/',
  method: 'put',
};

// 删除Grok
const deleteGrok = {
  url: '/databus/grok/:id/',
  method: 'delete',
};

// 获取更新人列表
const getUpdatedByList = {
  url: '/databus/grok/updated_by_list/',
  method: 'get',
};

// Grok调试
const debugGrok = {
  url: '/databus/grok/debug/',
  method: 'post',
};

export { getGrokList, createGrok, updateGrok, deleteGrok, getUpdatedByList, debugGrok };
