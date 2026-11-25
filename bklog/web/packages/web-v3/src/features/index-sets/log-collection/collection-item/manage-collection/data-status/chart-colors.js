// ECharts paints to canvas, so resolve CSS variables before passing colors to it.
export function readChartColors(element) {
  const style = getComputedStyle(element);
  return {
    axis: style.getPropertyValue('--bklog-panel-divider').trim()
      || style.getPropertyValue('--td-component-stroke').trim() || '#DCDEE5',
    series: style.getPropertyValue('--td-brand-color').trim() || '#339DFF',
    text: style.getPropertyValue('--td-text-color-secondary').trim() || '#63656E',
    tooltip: {
      backgroundColor: style.getPropertyValue('--td-bg-color-container').trim() || '#fff',
      borderColor: style.getPropertyValue('--td-component-stroke').trim() || '#DCDEE5',
      textStyle: { color: style.getPropertyValue('--td-text-color-primary').trim() || '#313238' },
    },
  };
}

export function observeChartColors(element, getInstance, cartesian = true) {
  const observer = new MutationObserver(() => {
    const chart = getInstance();
    if (!chart || chart.isDisposed()) return;

    const colors = readChartColors(element);
    chart.setOption({
      ...(cartesian && {
        xAxis: { axisLine: { lineStyle: { color: colors.axis } } },
        yAxis: { splitLine: { lineStyle: { color: colors.axis } } },
        series: [{ itemStyle: { color: colors.series } }],
      }),
      ...(!cartesian && { legend: { textStyle: { color: colors.text } } }),
      textStyle: { color: colors.text },
      tooltip: colors.tooltip,
    });
  });
  observer.observe(document.documentElement, { attributeFilter: ['theme-mode'] });
  return () => observer.disconnect();
}
