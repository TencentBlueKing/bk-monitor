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
// 空间类型对应map
export const SPACE_TYPE_MAP = {
  bkcc: {
    name: window.i18n.tc('业务'),
    color: '#3A84FF',
    backgroundColor: '#EDF4FF',
  },
  default: {
    name: window.i18n.tc('监控空间'),
    color: '#63656E',
    backgroundColor: '#F0F1F5',
  },
  bkci: {
    name: window.i18n.tc('研发项目'),
    color: '#EA3536',
    backgroundColor: '#FEEBEA',
  },
  bcs: {
    name: window.i18n.tc('容器项目'),
    color: '#FE9C00',
    backgroundColor: '#FFF1DB',
  },
  paas: {
    name: window.i18n.tc('蓝鲸应用'),
    color: '#14A568',
    backgroundColor: '#E4FAF0',
  },
  bksaas: {
    name: window.i18n.tc('蓝鲸应用'),
    color: '#14A568',
    backgroundColor: '#E4FAF0',
  },
};
