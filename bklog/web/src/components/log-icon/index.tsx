import { defineComponent, computed } from 'vue';

import './index.scss';

export default defineComponent({
  name: 'LogIcon',
  props: {
    svg: {
      default: false,
      type: Boolean,
    },
    type: {
      required: true,
      type: String,
    },
    common: {
      default: false,
      type: Boolean,
    },
  },

  setup(props, { emit }) {
    const commonPrefix = computed(() => (props.common ? 'bk' : 'bklog'));
    const iconPrefix = computed(() => (props.common ? 'icon' : 'bklog'));
    return () => {
      if (props.svg) {
        return (
          <svg class='log-svg-icon'>
            <use xlinkHref={`#${iconPrefix.value}-${props.type}`}></use>
          </svg>
        );
      }
      const classes = {
        [`${iconPrefix.value}-${props.type}`]: true,
        [`${commonPrefix.value}-icon`]: true,
      };
      return (
        <i
          class={classes}
          on-click={() => emit('click')}
        />
      );
    };
  },
});
