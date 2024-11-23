import { defineComponent, ref, watch } from 'vue';
import useChartRender from './use-chart-render';
import './index.scss';

export default defineComponent({
  props: {
    chartOptions: {
      type: Object,
      default: () => ({}),
    },
    // 用于触发更新，避免直接监听chartData性能问题
    chartCounter: {
      type: Number,
      default: 0,
    },
  },
  setup(props, {}) {
    const refRootElement = ref();
    const { setChartOptions } = useChartRender({ target: refRootElement, type: props.chartOptions.type });

    watch(
      () => props.chartCounter,
      () => {
        const { xFields, yFields, data, type } = props.chartOptions;
        setChartOptions(xFields, yFields, data, type);
      },
    );

    const renderContext = () => {
      return (
        <div class='bklog-chart-container'>
          <div
            ref={refRootElement}
            class='chart-canvas'
          ></div>
        </div>
      );
    };
    return {
      renderContext,
    };
  },
  render() {
    return this.renderContext();
  },
});
