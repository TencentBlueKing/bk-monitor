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
import { onMounted, Ref } from 'vue';

import useResizeObserve from '@/hooks/use-resize-observe';
import * as Echarts from 'echarts';
import { cloneDeep } from 'lodash';

import { lineOrBarOptions, pieOptions } from './chart-config-def';
export default ({ target, type }: { target: Ref<HTMLDivElement>; type: string }) => {
  let chartInstance: Echarts.ECharts = null;
  let options: any = {};

  const getLineBarChartOption = () => {
    const options = cloneDeep(lineOrBarOptions);
    return options;
  };

  const getPieChartOption = () => {
    const options = cloneDeep(pieOptions);
    return options;
  };

  type DataItem = Record<string, any>;

  const aggregateDataByDimensions = (data: DataItem[], dimensionFields: string[], metricFields: string[]) => {
    const groupedData = {};
    let reservedFields = dimensionFields;

    data.forEach(item => {
      reservedFields.forEach(field => {
        if (groupedData[field] === undefined) {
          groupedData[field] = {};
        }

        if (groupedData[field][item[field]] === undefined) {
          groupedData[field][item[field]] = {};
        }

        metricFields.forEach(m => {
          if (groupedData[field][item[field]][m] === undefined) {
            groupedData[field][item[field]][m] = 0;
          }

          groupedData[field][item[field]][m] += item[m];
        });
      });
    });

    const getNewGroup = (index, group) => {
      const field = reservedFields[index];
      if (field) {
        const target = groupedData[field];

        const group1Keys = Object.keys(target);
        const group2Keys = Object.keys(group);

        if (group2Keys.length === 0) {
          return getNewGroup(index + 1, target);
        }

        const newGroup = {};
        group1Keys.forEach(k1 => {
          group2Keys.forEach(k2 => {
            metricFields.forEach(m => {
              const key3 = `${k1},${k2}`;
              if (newGroup[key3] === undefined) {
                newGroup[key3] = {};
              }

              newGroup[key3][m] = Math.min(target[k1][m], group[k2][m]);
            });
          });
        });

        return getNewGroup(index + 1, newGroup);
      }

      return group;
    };

    return getNewGroup(0, {});
  };

  const aggregateData = (data, dimensions, metrics, type, timeField?) => {
    if (timeField) {
      const timeGroup = {};
      data.forEach(item => {
        if (timeGroup[item[timeField]] === undefined) {
          timeGroup[item[timeField]] = [];
        }

        timeGroup[item[timeField]].push(item);
      });

      const dimFields = dimensions.length > 0 ? dimensions : [timeField];
      const categories = Object.keys(timeGroup);
      const seriesData = Object.keys(timeGroup)
        .map(key => {
          const aggregatedData = aggregateDataByDimensions(timeGroup[key] ?? [], dimFields, metrics);
          return metrics.map(metric => ({
            name: metric,
            type,
            data: Object.keys(aggregatedData).map(item => [key, aggregatedData[item][metric]]),
          }));
        })
        .flat(2);

      return {
        categories,
        seriesData,
      };
    }

    const aggregatedData = aggregateDataByDimensions(data, dimensions, metrics);

    // 提取用于 ECharts 的数据
    const categories = Object.keys(aggregatedData);

    const seriesData = metrics.map(metric => ({
      name: metric,
      type,
      data: categories.map(item => aggregatedData[item][metric]),
    }));

    return {
      categories,
      seriesData,
    };
  };

  const aggregatePieData = (dataList, dimensions, valueField) => {
    const { categories, seriesData } = aggregateData(dataList, dimensions, [valueField], 'pie');
    // 转换为饼图数据格式
    const pieChartData = categories.map((key, index) => ({
      name: key,
      value: seriesData[0].data[index],
    }));

    return pieChartData;
  };

  const setDefaultOption = t => {
    const optionMap = {
      line: getLineBarChartOption,
      bar: getLineBarChartOption,
      pie: getPieChartOption,
    };

    options = optionMap[t]?.() ?? getLineBarChartOption();
  };

  const initChartInstance = () => {
    if (target.value) {
      chartInstance = Echarts.init(target.value);
      setDefaultOption(type);
    }
  };

  // const getXAxisType = (xFields: string[], data?: any, timeDimensions?: string[]) => {
  //   if (timeDimensions.length === 1) {
  //     return 'time';
  //   }

  //   if (xFields.length === 1) {
  //     const schema = (data.result_schema ?? []).find(f => f.field_name === xFields[0])?.field_type ?? 'category';
  //     return /^date/.test(schema) ? 'time' : 'category';
  //   }

  //   return 'category';
  // };

  /** 缩写数字 */
  const abbreviateNumber = (value: number) => {
    let newValue = value;
    let suffix = '';

    if (value >= 1000 && value < 1000000) {
      newValue = value / 1000;
      suffix = 'K';
    } else if (value >= 1000000 && value < 1000000000) {
      newValue = value / 1000000;
      suffix = ' Mil';
    } else if (value >= 1000000000) {
      newValue = value / 1000000000;
      suffix = 'Bil';
    }

    // 使用 Intl.NumberFormat 来格式化数字，避免不必要的小数部分
    const formatter = new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 3, // 最多保留一位小数
      minimumFractionDigits: 0, // 最少保留零位小数
    });

    return `${formatter.format(newValue)}${suffix}`;
  };

  const getYAxisLabel = () => {
    return {
      fontSize: 12,
      padding: [0, 5, 0, 0],
      color: '#979BA5',
      formatter: (value: number) => abbreviateNumber(value),
    };
  };

  const getXAxisTimeValue = (data: any[], timeField: string) => {
    return data.map(d => d[timeField]);
  };

  const updateLineBarOption = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string,
  ) => {
    const { categories, seriesData } = aggregateData(data?.list ?? [], xFields, yFields, type, dimensions[0]);

    options.xAxis.data = dimensions[0] ? getXAxisTimeValue(data?.list ?? [], dimensions[0]) : categories;
    Object.assign(options.yAxis.axisLabel, getYAxisLabel());
    options.series = seriesData;
    chartInstance.setOption(options);
  };

  const updatePieOption = (dimensions?: string[], yFields?: string[], _?: string[], data?: any) => {
    const pieChartData = aggregatePieData(data.list, dimensions, yFields[0]);
    options.series.data = pieChartData;
    chartInstance.setOption(options);
  };

  // 数字 & 线性图
  // const updateLineAndBarOption = (xFields?: string[], yFields?: string[], data?: any, type?: string) => {};

  const updateChartOptions = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string,
  ) => {
    const actionMap = {
      pie: updatePieOption,
      line: updateLineBarOption,
      bar: updateLineBarOption,
      // line_bar: updateLineAndBarOption,
    };

    actionMap[type]?.(xFields, yFields, dimensions, data, type);
  };

  const setResizeObserve = () => {
    const getTargetElement = () => {
      return target.value.parentElement;
    };

    useResizeObserve(getTargetElement, () => {
      chartInstance?.resize();
    });
  };

  const setChartOptions = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string,
  ) => {
    chartInstance?.clear();
    if (!chartInstance) {
      setResizeObserve();
      initChartInstance();
    }
    setDefaultOption(type);
    updateChartOptions(xFields, yFields, dimensions, data, type);
  };

  onMounted(() => {
    initChartInstance();
  });

  const destroyInstance = () => {
    chartInstance?.clear();
    chartInstance = null;
  };

  return {
    setChartOptions,
    destroyInstance,
  };
};
