import { defineComponent, ref, watch } from 'vue';

import { useDialogVisible } from '@/shared/global/overlay/index';
import { RelatedLogDialogPanel } from '../standalone-tab/related-log-dialog-panel';

import '../standalone-tab/index.scss';
import './index.scss';

export default defineComponent({
  emits: ['close-dialog', 'closeDialog', 'update:isShow'],

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
    const { visible, setVisible, onValueChange } = useDialogVisible(false, {
      id: 'retrieve-context-log-dialog',
      type: 'dialog',
      group: 'retrieve-related-log',
      rootSelector: '.log-context-dialog-main',
    });
    /** 每次打开递增，强制销毁并重建 panel，避免复用旧状态/缓存 */
    const mountKey = ref(0);

    watch(
      () => [props.isShow, props.rowKey] as const,
      ([show]) => {
        if (show) {
          mountKey.value += 1;
          setVisible(true);
          return;
        }
        setVisible(false);
      },
      { immediate: true },
    );

    const handleClose = () => {
      setVisible(false);
    };

    // Internal close / Escape / overlay exclusion must also reset the parent prop.
    watch(visible, (show, previous) => {
      if (!show && previous) emit('update:isShow', false);
    });

    const handleAfterLeave = () => {
      // A previous leave transition may finish after this panel is reopened.
      if (!visible.value) emit('close-dialog');
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
        onAfterLeave={handleAfterLeave}
        onValueChange={(value: boolean) => {
          onValueChange(value);
          if (!value) handleClose();
        }}
      >
        {visible.value && (
          <RelatedLogDialogPanel
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
