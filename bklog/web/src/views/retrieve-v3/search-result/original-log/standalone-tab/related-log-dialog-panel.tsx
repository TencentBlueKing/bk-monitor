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
};

/**
 * 弹窗内容面板：仅在 dialog visible 时挂载。
 * 关闭弹窗会卸载本组件，viewModel / 过滤条件 / 日志缓存随 onBeforeUnmount 一并销毁。
 */
export const ContextLogDialogPanel = defineComponent({
  name: 'ContextLogDialogPanel',
  props: panelProps,
  setup(props) {
    const indexSetId = ref(props.indexSetId);
    const rowIndex = computed(() => props.rowIndex);
    const retrieveParams = computed(() => props.retrieveParams || {});
    const targetFields = computed(() => (props.targetFields || []) as string[]);
    const targetRow = ref<Record<string, any>>({});

    const viewModel = useContextRelatedLog({
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
          title={viewModel.t('上下文')}
          viewModel={{
            ...viewModel,
            indexSetId: computed(() => indexSetId.value),
            rowIndex,
            retrieveParams,
          }}
        />
      </div>
    );
  },
});

export const RealTimeLogDialogPanel = defineComponent({
  name: 'RealTimeLogDialogPanel',
  props: panelProps,
  setup(props) {
    const indexSetId = ref(props.indexSetId);
    const rowIndex = computed(() => props.rowIndex);
    const retrieveParams = computed(() => props.retrieveParams || {});
    const targetFields = computed(() => (props.targetFields || []) as string[]);
    const targetRow = ref<Record<string, any>>({});

    const viewModel = useRealtimeRelatedLog({
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
          title={viewModel.t('实时日志')}
          viewModel={{
            ...viewModel,
            indexSetId: computed(() => indexSetId.value),
            rowIndex,
            retrieveParams,
          }}
          isRealTime
        />
      </div>
    );
  },
});
