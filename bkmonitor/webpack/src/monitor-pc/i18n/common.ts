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
import button from '../lang/button';
import content from '../lang/content';
import doc from '../lang/doc';
import dropdown from '../lang/dropdown';
import formContent from '../lang/form-content';
import formLabel from '../lang/form-label';
import message from '../lang/message';
import newHome from '../lang/new-home';
import newMetricView from '../lang/new-metric-view';
import placeholder from '../lang/placeholder';
import route from '../lang/route';
import strategy from '../lang/strategy';
import tableColumn from '../lang/table-column';
import tableContent from '../lang/table-content';
import tips from '../lang/tips';
import title from '../lang/title';
import tooltips from '../lang/tooltips';
import trace from '../lang/trace';
import validate from '../lang/validate';

export type MonitorLang = typeof MonitorLangData;
const MonitorLangData = {
  button,
  content,
  route,
  doc,
  formContent,
  formLabel,
  dropdown,
  placeholder,
  validate,
  message,
  tableColumn,
  tableContent,
  tips,
  tooltips,
  title,
  strategy,
  newHome,
  newMetricView,
  trace,
};

// 比较两个翻译文件是否多出来的词条
export function compareJson(
  a: Record<string, string>,
  b: Record<string, string>,
  needLogChange = false,
  needAddLabel = false
) {
  for (const key of Object.keys(a)) {
    if (!b[key]) {
      console.log(`${needAddLabel ? '多出来的词条：' : ''}'${key}': '${a[key]}',`);
    } else if (needLogChange && a[key] !== b[key]) {
      console.log(`翻译不相同的词条：${key}：${a[key]}`);
    }
  }
}
// console.info('============监控相较于产品翻译button====================');
// compareJson(button, frontendButton, false, false);
// console.info('============监控相较于产品翻译content====================');
// compareJson(content, frontendContent, false, false);
// console.info('============监控相较于产品翻译label====================');
// compareJson(label, frontendLabel, false, false);
// console.info('============监控相较于产品翻译route====================');
// compareJson(menu, frontendMenu, false, false);
// console.info('============产品翻译相较于监控button====================');
// compareJson(frontendButton, button, true);
// console.info('============产品翻译相较于监控content====================');
// compareJson(frontendContent, content, true);
// console.info('============产品翻译相较于监控label====================');
// compareJson(frontendLabel, label, true);
// 存储需要修改的重复词条
const needSetJson: Record<string, string> = {};

// 标识是否存在需要修改的重复词条
let hasNeedSetData = false;

type MonitorLangDataType = typeof MonitorLangData;
/**
 * @description 合并所有翻译文件
 * @returns {Record<string, Record<string, string>>} 合并后的翻译文件
 */
export function mergeI18nJson() {
  const keyList = Object.keys(MonitorLangData) as Array<keyof MonitorLang>;

  const data = keyList.reduce((data, name) => mergeJson(data, MonitorLangData[name], name), {});

  // 合并所有翻译文件
  // data = mergeJson(data, button, 'button');
  // data = mergeJson(data, label, 'label');
  // data = mergeJson(data, menu);

  // 打印需要修改的重复词条
  hasNeedSetData && console.error('需要修改重复的词条：', needSetJson);
  const reg = new RegExp(`^${keyList.map(key => `${key}-`).join('|')}`, 'm');
  // 将合并后的翻译文件进行格式化，并返回格式化后的翻译文件
  return {
    zhCN: Object.keys(data).reduce((res, key) => {
      res[key] = key.replace(reg, '');
      return res;
    }, {}) as MonitorLangDataType[keyof MonitorLangDataType],
    enUS: data as MonitorLangDataType[keyof MonitorLangDataType],
  };
}
/**
 * @description 将两个翻译文件进行合并
 * @param {Record<string, string>} data - 合并后的翻译文件
 * @param {Record<string, string>} item - 需要合并的翻译文件
 * @param {string} prefix - 翻译文件的前缀
 * @returns {Record<string, string>} 合并后的翻译文件
 */
function mergeJson<T extends keyof MonitorLang>(data: Record<string, string>, item: MonitorLang[T], prefix?: T) {
  return Object.keys(item).reduce((res, key) => {
    if (prefix && data[key]) {
      res[`${prefix}-${key}`] = item[key];
      needSetJson[`${prefix}-${key}`] = item[key];
      hasNeedSetData = true;
    } else {
      res[key] = item[key];
    }
    return res;
  }, data);
}
