import { defineComponent } from 'vue';

export default defineComponent({
  props: {
    list: {
      type: Array,
      default: () => [],
    },
  },
  setup() {},
});
