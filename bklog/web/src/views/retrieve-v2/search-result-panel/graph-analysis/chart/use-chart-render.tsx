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

import { formatDate } from '@/common/util';
import * as Echarts from 'echarts';
import { cloneDeep } from 'lodash';

import { lineOrBarOptions, pieOptions } from './chart-config-def';
export default ({ target, type }: { target: Ref<any>; type: string }) => {
  let chartInstance: Echarts.ECharts = null;
  let options: any = {};

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
        const target = groupedData[field] ?? {};

        const group1Keys = Object.keys(target).sort();
        const group2Keys = Object.keys(group).sort();

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

  const getDateTimeFormatValue = value => {
    // 如果是12位长度的格式，是后端返回的一个特殊格式 yyyyMMddHHmm
    if (`${value}`.length === 12 && /^\d+$/.test(value)) {
      return `${value.substring(0, 4)}-${value.substring(4, 6)}-${value.substring(6, 8)} ${value.substring(8, 10)}:${value.substring(10, 12)}`;
    }

    const timestamp = /^\d+$/.test(value) ? Number(value) : value;
    const timeValue = formatDate(timestamp, /^\d+$/.test(value), true);
    return timeValue || value;
  };

  const aggregateData = (data, dimensions, metrics, type, timeField?) => {
    const dimFields = dimensions.length > 0 ? dimensions : [timeField];
    if (timeField && dimensions.length > 0) {
      const timeGroup = {};
      data.forEach(item => {
        if (timeGroup[item[timeField]] === undefined) {
          timeGroup[item[timeField]] = [];
        }

        timeGroup[item[timeField]].push(item);
      });

      const categories = Object.keys(timeGroup)
        .sort()
        .map(key => [key, getDateTimeFormatValue(key)]);

      const seriesData = categories
        .map(([key, timeValue]) => {
          const aggregatedData = aggregateDataByDimensions(timeGroup[key] ?? [], dimFields, metrics);
          return metrics.map(metric => ({
            name: metric,
            type,
            data: Object.keys(aggregatedData).map(item => [timeValue, aggregatedData[item][metric], item]),
          }));
        })
        .flat(2);

      const seriesDataMap = new Map();
      seriesData.forEach(d => {
        if (!seriesDataMap.has(d.name)) {
          seriesDataMap.set(d.name, {});
        }

        const mapValue = seriesDataMap.get(d.name);
        d.data.forEach(([timeValue, value, key]) => {
          if (mapValue[key] === undefined) {
            mapValue[key] = [];
          }

          mapValue[key].push([timeValue, value, key]);
        });
      });

      return {
        categories: categories.map(c => c[1]),
        seriesData: Array.from(
          seriesDataMap.entries().map(([name, mapValue]) => {
            return Object.keys(mapValue).map(k => {
              return {
                name: `${name}-${k}`,
                type,
                data: mapValue[k],
              };
            });
          })
        ).flat(2),
      };
    }

    const aggregatedData = aggregateDataByDimensions(data, dimFields, metrics);

    // 提取用于 ECharts 的数据
    const categories = Object.keys(aggregatedData).sort();

    const seriesData = metrics.map(metric => ({
      name: metric,
      type,
      data: categories.map(item => [item, aggregatedData[item][metric]]),
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
      value: seriesData[0].data[index][1],
    }));

    return pieChartData;
  };

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

  const getTooltipFormatter = () => {
    return {
      formatter: params => {
        const args = Array.isArray(params) ? params : [params];
        const label = new Set(args.map(p => p.name));
        const content = `<div>${label ? `<span>${[...label].join(',')}</span></br>` : ''}${args
          .map(({ value, seriesName }) => `<span>${value[2] ?? seriesName}: ${abbreviateNumber(value[1])}</span>`)
          .join('</br>')}</div>`;
        return content;
      },
    };
  };

  const getLineBarChartOption = () => {
    const option = cloneDeep(lineOrBarOptions);
    Object.assign(option.tooltip, getTooltipFormatter());

    return option;
  };

  const getPieChartOption = () => {
    return cloneDeep(pieOptions);
  };

  const getLineDefaultOption = () => {
    const option = getLineBarChartOption();
    Object.assign(option.tooltip, { trigger: 'axis' });
    return option;
  };

  const setDefaultOption = t => {
    const optionMap = {
      line: getLineDefaultOption,
      bar: getLineBarChartOption,
      pie: getPieChartOption,
    };

    options = optionMap[t]?.() ?? getLineBarChartOption();
  };

  const initChartInstance = () => {
    if (target.value?.$el) {
      chartInstance = Echarts.init(target.value?.$el);
      setDefaultOption(type);
    }
  };

  const formatTimeDimensionResultData = ({ categories, seriesData }, formatDateField = false) => {
    if (formatDateField) {
      return {
        categories: categories.map(value => getDateTimeFormatValue(value)),
        seriesData: seriesData.map(item => {
          const data = item.data;
          return {
            ...item,
            data: data.map(d => {
              d[0] = getDateTimeFormatValue(d[0]);
              return d;
            }),
          };
        }),
      };
    }

    return {
      categories,
      seriesData,
    };
  };

  const updateLineBarOption = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string
  ) => {
    const { categories, seriesData } = formatTimeDimensionResultData(
      aggregateData(data?.list ?? [], xFields, yFields, type, dimensions[0]),
      dimensions.length === 1
    );
    options.xAxis.data = categories;
    Object.assign(options.yAxis.axisLabel, getYAxisLabel());
    options.series = seriesData;
    chartInstance.setOption(options);
  };

  const updatePieOption = (dimensions?: string[], yFields?: string[], _?: string[], data?: any) => {
    const pieChartData = aggregatePieData(data.list, dimensions, yFields[0]);
    options.series.data = pieChartData;
    chartInstance.setOption(options);
  };

  const updateChartOptions = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string
  ) => {
    const actionMap = {
      pie: updatePieOption,
      line: updateLineBarOption,
      bar: updateLineBarOption,
    };

    actionMap[type]?.(xFields, yFields, dimensions, data, type);
  };

  const setChartOptions = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string
  ) => {
    chartInstance?.clear();
    if (!chartInstance) {
      initChartInstance();
    }

    if (chartInstance) {
      setDefaultOption(type);
      updateChartOptions(xFields, yFields, dimensions, data, type);
    }
  };

  onMounted(() => {
    initChartInstance();
  });

  const destroyInstance = () => {
    chartInstance?.clear();
    chartInstance = null;
  };

  const getChartInstance = () => {
    return chartInstance;
  };

  return {
    setChartOptions,
    destroyInstance,
    getChartInstance,
  };
};
