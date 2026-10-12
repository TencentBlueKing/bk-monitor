import { computed, defineComponent, onMounted, ref, type PropType } from 'vue';

import RelatedLogLayout from './related-log-layout';
import { useContextRelatedLog } from './hooks/use-context-related-log';
import { useRealtimeRelatedLog } from './hooks/use-realtime-related-log';
import { useRelatedLogRowResolver } from './hooks/use-related-log-row-resolver';

const panelProps = {
  retrieveParams: {
    type: Object,
    required: true,
  },
  rowKey: {
    type: String,
    default: '',
  },
  logParams: {
    type: Object,
    default: () => ({}),
  },
  targetFields: {
    type: Array as PropType<string[]>,
    default: () => [],
  },
  indexSetId: {
    type: Number,
    default: 0,
  },
  rowIndex: {
    type: Number,
    default: 0,
  },
  /** 实时日志模式：切换 viewModel 实现并透传给布局组件 */
  isRealTime: {
    type: Boolean,
    default: false,
  },
};

/**
 * 弹窗内容面板：仅在 dialog visible 时挂载。
 * 关闭弹窗会卸载本组件，viewModel / 过滤条件 / 日志缓存随 onBeforeUnmount 一并销毁。
 *
 * 上下文日志与实时日志共用同一份入参契约与挂载流程，仅 viewModel 实现与标题不同，
 * 因此收敛为单组件，由 isRealTime 决定走哪条分支。
 */
export const RelatedLogDialogPanel = defineComponent({
  name: 'RelatedLogDialogPanel',
  props: panelProps,
  setup(props) {
    const indexSetId = ref(props.indexSetId);
    const rowIndex = computed(() => props.rowIndex);
    const retrieveParams = computed(() => props.retrieveParams || {});
    const targetFields = computed(() => (props.targetFields || []) as string[]);
    const targetRow = ref<Record<string, any>>({});

    /** 两个 hook 入参签名一致，按模式选择实现，避免条件分支调用 hook */
    const createViewModel = props.isRealTime ? useRealtimeRelatedLog : useContextRelatedLog;
    const viewModel = createViewModel({
      indexSetId,
      targetRow,
      targetFields,
    });

    const { resolveByRowKey } = useRelatedLogRowResolver({
      targetRow,
      indexSetId,
    });

    onMounted(async () => {
      if (!props.rowKey && !Object.keys(props.logParams || {}).length) {
        return;
      }
      const ready = await resolveByRowKey(props.rowKey, props.logParams as Record<string, any>);
      if (!ready) {
        return;
      }
      await viewModel.init();
    });

    return () => (
      <div class='standalone-related-log-page dialog-related-log-page'>
        <RelatedLogLayout
          title={viewModel.t(props.isRealTime ? '实时日志' : '上下文')}
          viewModel={{
            ...viewModel,
            indexSetId: computed(() => indexSetId.value),
            rowIndex,
            retrieveParams,
          }}
          isRealTime={props.isRealTime}
        />
      </div>
    );
  },
});
