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
    name: window.i18n.t('业务'),
    color: '#3A84FF',
    backgroundColor: '#EDF4FF',
  },
  default: {
    name: window.i18n.t('监控空间'),
    color: '#63656E',
    backgroundColor: '#F0F1F5',
  },
  bkci: {
    name: window.i18n.t('研发项目'),
    color: '#EA3536',
    backgroundColor: '#FEEBEA',
  },
  bcs: {
    name: window.i18n.t('容器项目'),
    color: '#FE9C00',
    backgroundColor: '#FFF1DB',
  },
  paas: {
    name: window.i18n.t('蓝鲸应用'),
    color: '#14A568',
    backgroundColor: '#E4FAF0',
  },
  bksaas: {
    name: window.i18n.t('蓝鲸应用'),
    color: '#14A568',
    backgroundColor: '#E4FAF0',
  },
};

/**
 * @description 查找targetNode是否含有指定名称为targetStr className | id | tagName
 * @param targetNode DOM节点
 * @param targetStr className | id | tagName
 * @returns
 */
export const hasTargetCondition = (targetNode: HTMLElement, targetStr: string): boolean => {
  const [prefix, ...args] = targetStr.split('');
  const content = args.join('');
  return (
    (prefix === '.' && targetNode.className?.includes(content)) ||
    (prefix === '#' && targetNode.id?.includes(content)) ||
    targetStr.toLocaleUpperCase() === targetNode.nodeName
  );
};

/* 获取event事件的父级列表（新的浏览器版本无path属性） */
/**
 * 不传targetStr参数时: 获取event事件的父级列表
 * 传入targetStr参数时: 查找targetStr
 * @param event 事件对象
 * @param targetStr 目标节点
 * @returns event事件的父集列表 或者 targetStr
 */
export const getEventPaths = (event: any | Event, targetStr = ''): (any | Event)[] => {
  if (event.path) {
    return targetStr ? event.path : event.path.filter(dom => hasTargetCondition(dom, targetStr));
  }
  const path = [];
  let target = event.target;
  while (target) {
    if (targetStr) {
      if (hasTargetCondition(target, targetStr)) {
        path.push(target);
        return path;
      }
    } else {
      path.push(target);
    }
    target = target.parentNode;
  }
  return path;
};
