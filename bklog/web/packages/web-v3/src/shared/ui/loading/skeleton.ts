import { defineComponent, h } from 'vue';


/** Compact skeleton for controls; panels use the existing page/table/chart skeletons. */
export const LoadingSkeleton = defineComponent({
  name: 'LoadingSkeleton',
  setup() {
    return () => h('span', { class: 'bklog-loading-skeleton', style: { position: 'relative', zIndex: 1 }, role: 'status', 'aria-label': 'Loading' },
      [100, 78, 90].map(width => h('span', { class: 'bklog-loading-skeleton__bar', style: { width: `${width}%` } })));
  },
});

export const renderLoadingSkeleton = () => h(LoadingSkeleton);

/** Dropdown items retain their 24px row rhythm instead of a centred panel indicator. */
export const DropdownLoadingSkeleton = defineComponent({
  name: 'DropdownLoadingSkeleton',
  props: {
    rows: { type: Number, default: 3 },
    itemHeight: { type: Number, default: 24 },
  },
  setup(props) {
    return () => h('div', { class: 'bklog-dropdown-skeleton', role: 'status', 'aria-label': 'Loading' },
      Array.from({ length: props.rows }, (_, index) => h('div', {
        class: 'bklog-dropdown-skeleton__item', style: { height: `${props.itemHeight}px` },
      }, [h('span', { class: 'bklog-dropdown-skeleton__bar', style: { width: `${[92, 72, 84][index % 3]}%` } })])));
  },
});
