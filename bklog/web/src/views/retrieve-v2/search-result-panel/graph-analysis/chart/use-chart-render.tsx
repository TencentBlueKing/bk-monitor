import { cloneDeep } from 'lodash';
import { lineOrBarOptions, pieOptions } from './chart-config-def';
import { onMounted, Ref } from 'vue';
import * as Echarts from 'echarts';
import useResizeObserve from '@/hooks/use-resize-observe';
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

  const aggregateData = (dataList, xFields, yFields, type = 'bar') => {
    const aggregatedData = {};

    dataList.forEach(item => {
      // 创建分组键
      const groupKey = xFields.map(field => item[field]).join(',');

      if (!aggregatedData[groupKey]) {
        aggregatedData[groupKey] = yFields.reduce((acc, field) => {
          acc[field] = 0;
          return acc;
        }, {});
      }

      // 聚合 yFields
      yFields.forEach(field => {
        aggregatedData[groupKey][field] += item[field];
      });
    });

    // 转换为 ECharts 格式
    const categories = Object.keys(aggregatedData);
    const seriesData = yFields.map(yField => ({
      name: yField,
      type,
      data: categories.map(category => aggregatedData[category][yField]),
    }));

    return { categories, seriesData };
  };

  const aggregateTimeData = (dataList, xFields, yFields, timeField = null, type = 'bar') => {
    const aggregatedData = {};

    (dataList ?? []).forEach(item => {
      // 构建分组键
      const groupKey = xFields.map(field => item[field]).join(',');
      const timeKey = item[timeField];

      if (!aggregatedData[timeKey]) {
        aggregatedData[timeKey] = {};
      }

      if (!aggregatedData[timeKey][groupKey]) {
        aggregatedData[timeKey][groupKey] = yFields.reduce((acc, field) => {
          acc[field] = 0;
          return acc;
        }, {});
      }

      // 聚合 yFields
      yFields.forEach(field => {
        aggregatedData[timeKey][groupKey][field] += item[field];
      });
    });

    // 提取分类维度和序列数据
    const categories = Object.keys(aggregatedData).sort();
    // 生成 series 数据
    const seriesData = [];
    const uniqueDimensions = new Set<string>();

    categories.forEach(timeKey => {
      Object.keys(aggregatedData[timeKey]).forEach(dimensionKey => {
        uniqueDimensions.add(dimensionKey);
      });
    });

    uniqueDimensions.forEach(dimensionKey => {
      yFields.forEach(yField => {
        seriesData.push({
          name: `${dimensionKey} - ${yField}`,
          type,
          data: categories.map(category => {
            return aggregatedData[category][dimensionKey] ? aggregatedData[category][dimensionKey][yField] : 0;
          }),
        });
      });
    });

    return { categories, seriesData };
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

  const getXAxisType = (xFields: string[], data?: any, timeDimensions?: string[]) => {
    if (timeDimensions.length === 1) {
      return 'time';
    }

    if (xFields.length === 1) {
      const schema = (data.result_schema ?? []).find(f => f.field_name === xFields[0])?.field_type ?? 'category';
      return /^date/.test(schema) ? 'time' : 'category';
    }

    return 'category';
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

  const updateLineBarOption = (
    xFields?: string[],
    yFields?: string[],
    dimensions?: string[],
    data?: any,
    type?: string,
  ) => {
    options.xAxis.type = getXAxisType(xFields, data, dimensions);
    const { categories, seriesData } = dimensions[0]
      ? aggregateTimeData(data.list, xFields, yFields, dimensions[0], type)
      : aggregateData(data.list, xFields, yFields, type);

    options.xAxis.data = categories;
    Object.assign(options.yAxis.axisLabel, getYAxisLabel());
    options.series = seriesData;
    chartInstance.setOption(options);
  };

  const updatePieOption = (_?: string[], yFields?: string[], dimensions?: string[], data?: any) => {
    options.series.encode = {
      itemName: yFields[0],
      value: dimensions[0],
    };

    options.dataset.source = (data?.list ?? []).map(row => ({
      [yFields[0]]: row[yFields[0]],
      [dimensions[0]]: row[dimensions[0]],
    }));
    chartInstance.setOption(options);
  };

  // 数字 & 线性图
  const updateLineAndBarOption = (xFields?: string[], yFields?: string[], data?: any, type?: string) => {};

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
      line_bar: updateLineAndBarOption,
    };

    actionMap[type]?.(xFields, yFields, dimensions, data, type);
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
      initChartInstance();
    }
    setDefaultOption(type);
    updateChartOptions(xFields, yFields, dimensions, data, type);
  };

  useResizeObserve(
    () => target.value.parentElement,
    () => {
      chartInstance?.resize();
    },
  );

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
