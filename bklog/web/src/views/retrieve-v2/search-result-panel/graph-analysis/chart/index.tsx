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
    const exceptionShow = ref(true);
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

    const renderException = () => {
      if (!props.chartOptions.data || !props.chartOptions.data.list || props.chartOptions.data.list.length === 0) {
        return [
          <bk-exception
            class='exception-wrap-item exception-part'
            type='empty'
            scene='part'
          ></bk-exception>,
        ];
      }
      // 图表查询配置变更的情况
      // if(exceptionShow.value){
      //   return [<bk-exception class="exception-wrap-item"  type="500">
      //     <span class="title">图表查询配置已变更</span>
      //     <div class="text-wrap">
      //       <span class="text">请重新发起查询</span>
      //       <div>
      //         <bk-button
      //           theme="primary"
      //           type="submit"
      //           // onClick="search"
      //           class="mr10"
      //           size="small"
      //         >查询
      //         </bk-button>
      //         <bk-button size="small" class="mr10" onClick={()=>{exceptionShow.value=false}}>我知道了</bk-button>
      //       </div>
      //     </div>
      //   </bk-exception> ];
      // }
    };

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
