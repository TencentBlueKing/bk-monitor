import { defineComponent, Ref, ref } from 'vue';
import useResizeObserve from '@/hooks/use-resize-observe';

export default defineComponent({
  props: {
    rowIndex: {
      type: Number,
      default: 0,
    },
  },
  emits: ['row-resize'],
  setup(props, { emit, slots }) {
    const refRowNodeRoot: Ref<HTMLElement> = ref();
    const renderRowVNode = () => {
      return (
        <div
          ref={refRowNodeRoot}
          data-row-index={props.rowIndex}
        >
          <div>{slots.default?.()}</div>
        </div>
      );
    };

    const getTargetElement = () => {
      return refRowNodeRoot.value?.firstElementChild ?? refRowNodeRoot;
    };

    useResizeObserve(getTargetElement, entry => {
      emit('row-resize', entry);
    });

    return {
      renderRowVNode,
    };
  },
  render() {
    return this.renderRowVNode();
  },
});
