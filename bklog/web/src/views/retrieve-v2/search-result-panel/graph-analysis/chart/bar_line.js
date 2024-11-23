export function getBarLineData(xFields, yFields, data, type) {
    let xAxisData = [];
    let summedGseIndexes = [];
    const result = {};
    function sumGseIndexByHostId(eData, xAxisNames, yAxis) {
      
      console.log(xAxisNames, yAxis);

      eData.forEach((item) => {
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
      summedGseIndexes.push(Object.values(result));
      xAxisData.push(...Object.keys(result));
    }
    yFields.forEach((y, index) => {
      sumGseIndexByHostId(data?.list, xFields, yFields[index]);
    });
    console.log('23', xAxisData,summedGseIndexes);
    const series = summedGseIndexes.map((item) => {
      return {
        type: type,
        data: item,
      };
    });
    // options.xAxis.data = xAxisData
    // options.xAxis.type = getXAxisType(xFields, data);
    // options.series = series
    return { xAxisData, series };
}