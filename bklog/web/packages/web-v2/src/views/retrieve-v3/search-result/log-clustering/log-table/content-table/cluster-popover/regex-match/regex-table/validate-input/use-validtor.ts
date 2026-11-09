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
/*
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
 *
 * Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at https://opensource.org/licenses/MIT
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for
 * the specific language governing permissions and limitations under the License.
 */

import { reactive, toRefs } from 'vue';

export type Rules = Array<{
  validator: (value: any) => Promise<boolean> | boolean;
  message: (() => string) | string;
}>;

const getRuleMessage = (rule: Rules[0]) => {
  if (typeof rule.message === 'function') {
    return rule.message();
  }
  return rule.message;
};

export default function (rules: Rules | undefined) {
  const state = reactive({
    loading: false,
    error: false,
    message: '',
  });

  const validator = (targetValue: any) => {
    state.error = false;
    state.message = '';
    if (!rules) {
      return Promise.resolve(true);
    }
    const run = (() => {
      let stepIndex = -1;
      return (): Promise<boolean> => {
        stepIndex += 1;
        if (stepIndex >= rules.length) {
          return Promise.resolve(true);
        }
        const rule = rules[stepIndex];
        return Promise.resolve().then(() => {
          const result = rule.validator(targetValue);
          // 异步验证
          if (typeof result !== 'boolean' && typeof result.then === 'function') {
            return result
              .then((data: boolean) => {
                // 异步验证结果为 false
                if (data === false) {
                  return Promise.reject(getRuleMessage(rule));
                }
              })
              .then(
                () => run(),
                () => {
                  state.error = true;
                  const message = getRuleMessage(rule);
                  state.message = message;
                  return Promise.reject(message);
                },
              );
          }
          // 验证失败
          if (!result) {
            state.error = true;
            const message = getRuleMessage(rule);
            state.message = message;
            return Promise.reject(message);
          }
          // 下一步
          return run();
        });
      };
    })();

    return run();
  };

  return {
    ...toRefs(state),
    validator,
  };
}
