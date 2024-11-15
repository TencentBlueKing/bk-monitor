import { defineComponent } from 'vue';

export default defineComponent({
  props: {
    rowIndex: {
      type: Number,
      default: 0,
    },
  },
  setup(props) {
    const renderRowVNode = () => {
      return <div data-row-index={props.rowIndex}></div>;
    };
    return {
      renderRowVNode,
    };
  },
  render() {
    return this.renderRowVNode();
  },
});
