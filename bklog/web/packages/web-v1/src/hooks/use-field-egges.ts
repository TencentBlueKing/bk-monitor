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
import { ref } from 'vue';

import useStore from '@/hooks/use-store';
import { ConditionOperator } from '@/store/condition-operator';

export default () => {
  const store = useStore();

  const isRequesting = ref(false);
  const isValidateItem = ref(false);

  let requestTimer;

  const taskPool = [];

  const setIsRequesting = (val: boolean) => {
    isRequesting.value = val;
  };

  const isValidateEgges = (field: any) => {
    isValidateItem.value = ['keyword'].includes(field.field_type);
    return isValidateItem.value;
  };

  /**
   * 自动补全提示接口请求任务
   */
  const requestFieldEgges = (field: any, value?: string, callback?: (resp: any) => void, finallyFn?: () => void) => {
    /**
     * 检测字段是否为 flattened 字段
     */
    if (field.field_type === 'flattened') {
      setIsRequesting(false);
      return;
    }

    if (
      taskPool.some(task => {
        return task.fields[0] === field && task.query_value === value && task.pending;
      })
    ) {
      setIsRequesting(false);
      return;
    }

    const getConditionValue = () => {
      if (['keyword'].includes(field.field_type)) {
        return [`*${value}*`];
      }
      setIsRequesting(false);
      return [];
    };

    if (value !== undefined && value !== null && !isValidateEgges(field)) {
      setIsRequesting(false);
      return;
    }

    const size = value?.length > 0 ? 50 : 100;
    requestTimer && clearTimeout(requestTimer);
    requestTimer = setTimeout(() => {
      setIsRequesting(true);

      const addition = value
        ? [
            {
              field: field.field_name,
              operator: '=~',
              value: getConditionValue(),
            },
          ].map(val => {
            const instance = new ConditionOperator(val);
            return instance.getRequestParam();
          })
        : [];

      const taskArgs = {
        fields: [field],
        addition,
        force: true,
        size,
        pending: true,
        index: taskPool.length,
        commit: false,
        cancelToken: true,
        query_value: value,
      };

      for (const task of taskPool) {
        task.pending = false;
      }

      taskPool.push(taskArgs);
      store
        .dispatch('requestIndexSetValueList', taskArgs)
        .then(resp => {
          if (taskArgs.pending) {
            store.commit('updateIndexFieldEggsItems', resp.data?.aggs_items ?? {});
            callback?.(resp);
          }
        })
        .catch(err => {
          if (err.code === 'ERR_CANCELED') {
            console.log('取消请求');
          }
        })
        .finally(() => {
          if (taskArgs.pending) {
            setIsRequesting(false);
          }
          const index = taskPool.findIndex(t => t === taskArgs);
          taskPool.splice(index, 1);
          finallyFn?.();
        });
    }, 300);
  };

  return {
    requestFieldEgges,
    isValidateEgges,
    isRequesting,
    setIsRequesting,
    isValidateItem,
  };
};
