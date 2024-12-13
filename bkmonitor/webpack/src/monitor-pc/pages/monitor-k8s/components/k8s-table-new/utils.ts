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

const datapointsMock = [
  [2499, 1732260720000],
  [870, 1732260840000],
  [2477, 1732260960000],
  [2318, 1732261080000],
  [2116, 1732261200000],
  [3319, 1732261320000],
  [1627, 1732261440000],
  [2349, 1732261560000],
  [2993, 1732261680000],
  [2331, 1732261800000],
  [3400, 1732261920000],
  [1325, 1732262040000],
  [4376, 1732262160000],
  [2611, 1732262280000],
  [1466, 1732262400000],
  [2288, 1732262520000],
  [2335, 1732262640000],
  [2871, 1732262760000],
  [3858, 1732262880000],
  [1122, 1732263000000],
  [2277, 1732263120000],
  [2254, 1732263240000],
  [3454, 1732263360000],
  [4397, 1732263480000],
  [2220, 1732263600000],
  [1982, 1732263720000],
  [2161, 1732263840000],
  [2497, 1732263960000],
  [1743, 1732264080000],
  [1234, 1732264200000],
];

export function getK8sTableAsyncDataMock(param: any) {
  return new Promise(res => {
    const result = [];
    const resourceType = param.resourceType;
    const column = param.column;
    for (const resourceTypeId of param[resourceType]) {
      result.push({
        [resourceType]: resourceTypeId,
        [column]: {
          datapoints: datapointsMock,
          unit: null,
        },
      });
    }
    setTimeout(() => {
      res(result);
    }, 1000);
  });
}
