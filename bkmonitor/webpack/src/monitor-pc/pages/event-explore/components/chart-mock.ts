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
export const chartMockData = {
  unit: '',
  series: [
    {
      dimensions: {
        type: 'Normal',
      },
      target: 'SUM(_index){type=Normal}',
      metric_field: '_result_',
      alias: '_result_',
      type: 'bar',
      dimensions_translation: {},
      unit: '',
      datapoints: [
        [220, 1739221200000],
        [240, 1739224800000],
        [242, 1739228400000],
        [222, 1739232000000],
        [224, 1739235600000],
        [226, 1739239200000],
        [233, 1739242800000],
        [247, 1739246400000],
        [270, 1739250000000],
        [266, 1739253600000],
        [247, 1739257200000],
        [248, 1739260800000],
        [236, 1739264400000],
        [239, 1739268000000],
        [262, 1739271600000],
        [246, 1739275200000],
        [240, 1739278800000],
        [259, 1739282400000],
        [260, 1739286000000],
        [241, 1739289600000],
        [239, 1739293200000],
        [241, 1739296800000],
        [264, 1739300400000],
        [263, 1739304000000],
        [253, 1739307600000],
        [251, 1739311200000],
        [255, 1739314800000],
        [250, 1739318400000],
        [255, 1739322000000],
      ],
    },
    {
      dimensions: {
        type: 'Warning',
      },
      target: 'SUM(_index){dimensions.type=Warning}',
      metric_field: '_result_',
      alias: '_result_',
      type: 'bar',
      dimensions_translation: {},
      unit: '',
      datapoints: [
        [47, 1739221200000],
        [32, 1739224800000],
        [26, 1739228400000],
        [53, 1739232000000],
        [26, 1739235600000],
        [38, 1739239200000],
        [35, 1739242800000],
        [45, 1739246400000],
        [37, 1739250000000],
        [46, 1739253600000],
        [69, 1739257200000],
        [47, 1739260800000],
        [40, 1739264400000],
        [29, 1739268000000],
        [39, 1739271600000],
        [57, 1739275200000],
        [46, 1739278800000],
        [41, 1739282400000],
        [42, 1739286000000],
        [56, 1739289600000],
        [45, 1739293200000],
        [34, 1739296800000],
        [46, 1739300400000],
        [51, 1739304000000],
        [58, 1739307600000],
        [35, 1739311200000],
        [44, 1739314800000],
        [43, 1739318400000],
        [35, 1739322000000],
      ],
    },
    {
      dimensions: {
        type: 'Default',
      },
      target: 'SUM(_index){dimensions.type=Default}',
      metric_field: '_result_',
      alias: '_result_',
      type: 'bar',
      dimensions_translation: {},
      unit: '',
      datapoints: [
        [6, 1739221200000],
        [3, 1739224800000],
        [0, 1739228400000],
        [1, 1739232000000],
        [1, 1739235600000],
        [13, 1739239200000],
        [16, 1739242800000],
        [21, 1739246400000],
        [14, 1739250000000],
        [16, 1739253600000],
        [26, 1739257200000],
        [24, 1739260800000],
        [14, 1739264400000],
        [9, 1739268000000],
        [16, 1739271600000],
        [33, 1739275200000],
        [11, 1739278800000],
        [8, 1739282400000],
        [11, 1739286000000],
        [9, 1739289600000],
        [6, 1739293200000],
        [6, 1739296800000],
        [4, 1739300400000],
        [7, 1739304000000],
        [8, 1739307600000],
        [16, 1739311200000],
        [4, 1739314800000],
        [7, 1739318400000],
        [9, 1739322000000],
      ],
    },
  ],
};
