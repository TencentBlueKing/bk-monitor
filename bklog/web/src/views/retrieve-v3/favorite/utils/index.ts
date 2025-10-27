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

import type { IGroupNameRules } from '../types';

/**
 * 验证名称格式
 * @param value 要验证的值
 * @returns 是否通过验证
 */
export const validateName = (value: string): boolean => {
  if (!value?.trim()) {
    return false;
  }

  const nameRegex =
    /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：""【】、；''，。、]+$/im;
  return nameRegex.test(value.trim());
};

/**
 * 检查名称是否已存在
 * @param dataList 数据列表
 * @param value 要检查的值
 * @param key 比较的键名
 * @returns 是否已存在
 */
export const checkNameExists = <T extends Record<string, any>>(dataList: T[], value: string, key: keyof T): boolean => {
  return dataList.some(item => item[key] === value);
};

/**
 * 获取分组名验证规则
 * @param dataList 数据列表
 * @param key 字段键名
 * @returns 验证规则对象
 */
export const getGroupNameRules = <T extends Record<string, any>>(
  dataList: T[],
  key = 'group_name',
): IGroupNameRules => {
  return {
    [key]: [
      {
        validator: (val: string) => validateName(val),
        message: window.$t('{n}不规范, 包含特殊符号', { n: window.$t('组名') }),
        trigger: 'blur',
      },
      {
        validator: (val: string) => !checkNameExists(dataList, val, key),
        message: window.$t('组名重复'),
        trigger: 'blur',
      },
      {
        required: true,
        message: window.$t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.$t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
    ],
  };
};

/**
 * 显示消息提示
 * @param message 消息内容
 * @param theme 主题类型
 */
export const showMessage = (message: string, theme: 'error' | 'success' | 'warning' = 'success'): void => {
  window.mainComponent?.$bkMessage({ message, theme });
};

/**
 * 处理API错误
 * @param error 错误对象
 * @param defaultMessage 默认错误消息
 */
export const handleApiError = (error: any, defaultMessage: string): void => {
  const message = error?.message || defaultMessage;
  showMessage(message, 'error');
};
