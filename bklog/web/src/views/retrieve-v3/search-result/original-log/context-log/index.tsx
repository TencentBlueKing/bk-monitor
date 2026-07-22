import { defineComponent, ref, watch } from 'vue';

import { ContextLogDialogPanel } from '../standalone-tab/related-log-dialog-panel';

import '../standalone-tab/index.scss';
import './index.scss';

export default defineComponent({
  name: 'ContextLog',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
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
    /** 每次打开递增，强制销毁并重建 panel，避免复用旧状态/缓存 */
    const mountKey = ref(0);

    watch(
      () => [props.isShow, props.rowKey] as const,
      ([show]) => {
        if (show) {
          mountKey.value += 1;
          visible.value = true;
          return;
        }
        visible.value = false;
      },
      { immediate: true },
    );

    const handleClose = () => {
      visible.value = false;
    };

    const handleAfterLeave = () => {
      emit('close-dialog');
    };

    return () => (
      <bk-dialog
        ext-cls='log-context-dialog-main'
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
          <ContextLogDialogPanel
            key={mountKey.value}
            indexSetId={props.indexSetId}
            logParams={props.logParams}
            retrieveParams={props.retrieveParams}
            rowIndex={props.rowIndex}
            rowKey={props.rowKey}
            targetFields={props.targetFields as string[]}
          />
        )}
      </bk-dialog>
    );
  },
});
