import { defineComponent, ref } from 'vue';
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
    const refRowNodeRoot = ref();
    const renderRowVNode = () => {
      return (
        <div
          ref={refRowNodeRoot}
          data-row-index={props.rowIndex}
        >
          {slots.default?.()}
        </div>
      );
    };

    useResizeObserve(refRowNodeRoot, entry => {
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
