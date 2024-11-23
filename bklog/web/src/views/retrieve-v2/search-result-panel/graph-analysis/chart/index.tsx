import { computed, defineComponent, ref, watch } from 'vue';
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
    const { setChartOptions, destroyInstance } = useChartRender({
      target: refRootElement,
      type: props.chartOptions.type,
    });
    const showTable = computed(() => props.chartOptions.type === 'table');

    watch(
      () => props.chartCounter,
      () => {
        const { xFields, yFields, dimensions, data, type } = props.chartOptions;
        if (!showTable.value) {
          setTimeout(() => {
            setChartOptions(xFields, yFields, dimensions, data, type);
          });
        } else {
          destroyInstance();
        }
      },
    );
    const rendChildNode = () => {
      if (showTable.value) {
        return (
          <bk-table data={props.chartOptions.data.list}>
            {props.chartOptions.data.select_fields_order.map(col => (
              <bk-table-column
                label={col}
                prop={col}
                key={col}
              ></bk-table-column>
            ))}
          </bk-table>
        );
      }

      return (
        <div
          ref={refRootElement}
          class='chart-canvas'
        ></div>
      );
    };

    const renderContext = () => {
      return <div class='bklog-chart-container'>{rendChildNode()}</div>;
    };
    return {
      renderContext,
    };
  },
  render() {
    return this.renderContext();
  },
});
