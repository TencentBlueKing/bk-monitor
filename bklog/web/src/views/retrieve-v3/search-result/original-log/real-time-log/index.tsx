import { computed, defineComponent, nextTick, ref, watch } from 'vue';

import RelatedLogLayout from '../standalone-tab/related-log-layout';
import { useRealtimeRelatedLog } from '../standalone-tab/hooks/use-realtime-related-log';

import '../standalone-tab/index.scss';
import './index.scss';

export default defineComponent({
  name: 'RealTimeLog',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
    logParams: {
      type: Object,
      default: () => ({}),
    },
    targetFields: {
      type: Array,
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
  },
  setup(props, { emit }) {
    const visible = ref(false);
    const indexSetId = computed(() => props.indexSetId);
    const rowIndex = computed(() => props.rowIndex);
    const retrieveParams = computed(() => props.retrieveParams || {});
    const targetFields = computed(() => props.targetFields as string[]);
    const targetRow = ref<Record<string, any>>({});

    const viewModel = useRealtimeRelatedLog({
      indexSetId,
      targetRow,
      targetFields,
    });

    const init = async () => {
      if (!props.isShow || !props.indexSetId || !props.logParams || !Object.keys(props.logParams).length) {
        return;
      }

      targetRow.value = props.logParams as Record<string, any>;
      await nextTick();
      await viewModel.init();
    };

    watch(
      () => [props.isShow, props.indexSetId, props.logParams],
      async () => {
        visible.value = props.isShow;
        if (props.isShow) {
          await init();
        } else {
          viewModel.dispose();
        }
      },
      { immediate: true },
    );

    const handleClose = () => {
      visible.value = false;
    };

    const handleAfterLeave = () => {
      viewModel.dispose();
      emit('close-dialog');
    };

    return () => (
      <bk-dialog
        ext-cls='log-realtime-dialog-main'
        draggable={false}
        esc-close
        mask-close={false}
        render-directives='if'
        show-footer={false}
        value={visible.value}
        fullscreen
        on-after-leave={handleAfterLeave}
        on-value-change={(value: boolean) => {
          if (!value) handleClose();
        }}
      >
        {visible.value && (
          <div class='standalone-related-log-page dialog-related-log-page'>
            <RelatedLogLayout
              title={viewModel.t('实时日志')}
              viewModel={{
                ...viewModel,
                indexSetId,
                rowIndex,
                retrieveParams,
              }}
              isRealTime
            />
          </div>
        )}
      </bk-dialog>
    );
  },
});
