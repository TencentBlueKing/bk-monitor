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
import base64Svg from 'monitor-common/svg/base64';

import type { EditTemplateFormData } from '../components/template-form/typing';
const templateIconEnum = {
  DEFAULT: 'DEFAULT',
  P99: 'P99',
  AVG: 'AVG',
  SUCCESS_RATE: 'SUCCESS_RATE',
  CICD: 'CICD',
};

export const templateIconMap = {
  [templateIconEnum.DEFAULT]: 'icon-gaojing',
  [templateIconEnum.P99]: 'icon-a-99haoshi',
  [templateIconEnum.AVG]: 'icon-pingjunhaoshi',
  [templateIconEnum.SUCCESS_RATE]: 'icon-check',
  [templateIconEnum.CICD]: base64Svg.bkci,
};

/**
 * 判断模板表单数据是否被修改
 * @param newData 当前数据
 * @param oldData 原始数据
 * @returns 数据是否有修改，以及哪些字段被修改
 */
export const validTemplateDataIsEdit = (newData: EditTemplateFormData, oldData: EditTemplateFormData) => {
  const { algorithms, detect, user_group_list, is_auto_apply } = newData;
  const {
    algorithms: oldAlgorithms,
    detect: oldDetect,
    user_group_list: oldUserGroupList,
    is_auto_apply: oldIsAutoApply,
  } = oldData;

  /** 检测规则是否修改 */
  let algorithmsIsEdit = true;
  if (
    algorithms.length === oldAlgorithms.length &&
    algorithms.every(item => {
      const detail = oldAlgorithms.find(detail => detail.level === item.level);
      return detail && JSON.stringify(item.config) === JSON.stringify(detail.config);
    })
  ) {
    algorithmsIsEdit = false;
  }

  /** 判断条件是否修改 */
  let detectIsEdit = true;
  if (
    detect.type === oldDetect.type &&
    Object.keys(detect.config).every(key => detect.config[key] === oldDetect.config[key])
  ) {
    detectIsEdit = false;
  }

  /** 判断告警组是否修改 */
  let alarmGroupIsEdit = true;
  if (
    user_group_list.every(item => oldUserGroupList.find(detail => detail.id === item.id)) &&
    user_group_list.length === oldUserGroupList.length
  ) {
    alarmGroupIsEdit = false;
  }

  /** 判断自动下发是否修改 */
  const isAutoApplyIsEdit = is_auto_apply !== oldIsAutoApply;

  return {
    isEdit: algorithmsIsEdit || detectIsEdit || alarmGroupIsEdit || isAutoApplyIsEdit,
    algorithmsIsEdit,
    detectIsEdit,
    alarmGroupIsEdit,
    isAutoApplyIsEdit,
  };
};
