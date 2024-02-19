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
import { getActionParams } from '../../../../../../monitor-api/modules/action';

/* 将变量({{xxx}})替换为变量值 */
export const setVariableToString = (variableMap: Map<string, { id: string; example: string }>, targetStr: string) => {
  /* 获取字符串里的变量 */
  const getVariabelStrList = (value: string) => {
    const list = value.match(/\{\{(.*?)\}\}/g);
    return list?.filter((item, index, arr) => arr.indexOf(item, 0) === index) || []; // 去重
  };
  const varList = getVariabelStrList(targetStr); // 字符串内的变量
  const hasVar = !!varList.length; // 是否含有变量
  if (hasVar) {
    const varInfos = varList.map(v => variableMap.get(v.replace(/{{|}}/g, '')));
    const variables = {};
    varInfos.forEach(vInfo => {
      if (vInfo) {
        variables[vInfo.id] = vInfo;
      }
    });
    const result = `${targetStr}`.replace(/\{\{(.*?)\}\}/g, (match, key) => variables[key]?.example || '');
    return result;
  }
  return targetStr;
};

/* 校验http回调json数据 */
export const variableJsonVerify = async (pluginId, jsonData) =>
  new Promise((resolve, reject) => {
    getActionParams(
      {
        alert_ids: [],
        action_configs: [
          {
            plugin_id: pluginId,
            execute_config: {
              template_detail: {
                interval_notify_mode: 'standard',
                method: 'GET',
                url: 'http://127.0.0.1',
                headers: [{ key: 'test', value: '', desc: '', is_builtin: false, is_enabled: false }],
                authorize: { auth_type: 'none', auth_config: {} },
                body: {
                  data_type: 'raw',
                  params: [],
                  content: jsonData,
                  content_type: 'json'
                },
                query_params: []
              },
              timeout: 600
            },
            name: '测试json判断'
          }
        ],
        is_demo: true
      },
      { needMessage: false }
    )
      .then(() => {
        resolve(true);
      })
      .catch(err => {
        reject(err);
      });
  });
