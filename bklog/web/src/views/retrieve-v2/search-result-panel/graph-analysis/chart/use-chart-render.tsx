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

  const getXAxisType = (xFields: string[], data?: any) => {
    if (xFields.length === 1) {
      const schema = (data.result_schema ?? []).find(f => f.field_name === xFields[0])?.field_type ?? 'category';
      return /^date/.test(schema) ? 'time' : 'category';
    }

    return 'category';
  };

  const updateLineBarOption = (xFields?: string[], yFields?: string[], data?: any, type?: string) => {
    // options.xAxis.data = (xFields ?? []).map((item: string) => (data?.list ?? []).map(row => row[item]));
    // options.xAxis.type = getXAxisType(xFields, data);

    // options.series = (yFields ?? []).map((item: string) => ({
    //   type,
    //   data: (data?.list ?? []).map(row => row[item]),
    // }));
    let xAxisData = [];
    let summedGseIndexes = [];
    function sumGseIndexByHostId(eData: any, xAxisNames: string[], yAxis: string) {
      const result = {};
      console.log(xAxisNames, yAxis);

      eData.forEach((item: any) => {
        let xAxisName = xAxisNames.reduce((accumulator, currentValue, index) => {
          return (
            accumulator + item[currentValue] + (index === xAxisNames.length - 1 ? "" : "_")
          );
        }, "");

        if (!result[xAxisName]) {
          result[xAxisName] = 0;
        }
        result[xAxisName] += item[yAxis];
      });
      console.log(result);
      summedGseIndexes.push(Object.values(result));
      xAxisData.push(...Object.keys(result));
      // return Object.values(result);
    }
    // const summedGseIndexes = sumGseIndexByHostId(tableData.value,xAxis.value[0],yAxis.value[0]);


    yFields.forEach((y, index) => {
      sumGseIndexByHostId(data?.list, xFields, yFields[index]);
    });
    console.log(summedGseIndexes);
    const series = summedGseIndexes.map((item) => {
      return {
        type: type,
        data: item,
      };
    });
    options.xAxis.data = xAxisData
    options.xAxis.type = getXAxisType(xFields, data);
    options.series = series
    chartInstance.setOption(options);
  };

  const updatePieOption = (_?: string[], yFields?: string[], data?: any, type?: string) => {
    options.series = (yFields ?? []).map((item: string) => ({
      type,
      radius: '50%',
      data: {
        name: item,
        value: (data?.list ?? []).map(row => row[item]),
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
    }));

    chartInstance.setOption(options);
  };

  // 数字 & 线性图
  const updateLineAndBarOption = (xFields?: string[], yFields?: string[], data?: any, type?: string) => { };

  const updateChartOptions = (xFields?: string[], yFields?: string[], data?: any, type?: string) => {
    console.log(xFields, yFields, data, type);

    const actionMap = {
      pie: updatePieOption,
      line: updateLineBarOption,
      bar: updateLineBarOption,
      line_bar: updateLineAndBarOption,
    };

    actionMap[type]?.(xFields, yFields, data, type);
  };

  const setChartOptions = (xFields?: string[], yFields?: string[], data?: any, type?: string) => {
    if (!chartInstance) {
      initChartInstance();
    }
    setDefaultOption(type);
    updateChartOptions(xFields, yFields, data, type);
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
