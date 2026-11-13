import { defineComponent, h, onBeforeUnmount, onMounted, ref, watch, type PropType } from 'vue';
import { DropdownLoadingSkeleton, LoadingSkeleton } from './skeleton';
import './list-skeleton.scss';

export type ListSkeletonVariant = 'log' | 'log-table' | 'fields';
export const LIST_ROW_HEIGHT = { log: 64, 'log-table': 64, fields: 32 } as const;
export const listSkeletonRows = (height: number, rowHeight: number) => Math.max(1, Math.ceil(height / rowHeight));

/** Fill the actual list viewport. Never size a panel from the Loading icon's font-size. */
export const ListLoadingSkeleton = defineComponent({
  name: 'ListLoadingSkeleton',
  props: { variant: { type: String as PropType<ListSkeletonVariant>, default: 'log' } },
  setup(props) {
    const root = ref<HTMLElement | null>(null);
    const rows = ref(12);
    let observer: ResizeObserver | undefined;
    const measure = () => {
      const height = root.value?.clientHeight;
      if (height) rows.value = listSkeletonRows(height, LIST_ROW_HEIGHT[props.variant]);
    };
    watch(() => props.variant, measure, { flush: 'post' });
    onMounted(() => {
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(measure);
        if (root.value) observer.observe(root.value);
      }
      measure();
    });
    onBeforeUnmount(() => observer?.disconnect());
    const bar = (width: string, className = '') => h('span', { class: ['bklog-list-skeleton__bar', className], style: { width } });
    return () => h('div', { ref: root, class: ['bklog-list-skeleton', `bklog-list-skeleton--${props.variant}`],
      role: 'status', 'aria-label': 'Loading', style: { '--bklog-list-row-height': `${LIST_ROW_HEIGHT[props.variant]}px` } },
    Array.from({ length: rows.value }, (_, index) => h('div', { class: 'bklog-list-skeleton__row', 'aria-hidden': 'true', key: index }, [
      props.variant === 'fields' ? bar('14px', 'bklog-list-skeleton__icon') : bar('20px'),
      props.variant === 'log-table' ? h('div', { class: 'bklog-list-skeleton__lines' }, [bar('90%'), bar('72%')]) : null,
      h('div', { class: 'bklog-list-skeleton__lines' }, [
        bar(`${[96, 82, 91][index % 3]}%`),
        props.variant === 'log' || props.variant === 'log-table' ? bar(`${[78, 93, 65][index % 3]}%`) : null,
      ]),
    ])));
  },
});

// Stable functions avoid recreating directive overlays on unrelated renders.
export const renderLogListSkeleton = () => h(ListLoadingSkeleton, { variant: 'log' });
export const renderLogTableSkeleton = () => h(ListLoadingSkeleton, { variant: 'log-table' });
export const renderFieldListSkeleton = () => h(ListLoadingSkeleton, { variant: 'fields' });
export const renderDropdownListSkeleton = () => h(DropdownLoadingSkeleton);
/** Code/textarea preview, with no row-number or table columns. */
export const renderCodeSampleSkeleton = () => h('div', { class: 'bklog-code-sample-skeleton', role: 'status', 'aria-label': 'Loading' },
  [96, 78, 88].map(width => h('span', { class: 'bklog-list-skeleton__bar', style: { width: `${width}%` } })));
/** A tail/refresh request must not replace already readable log rows. */
export const renderListRefreshSkeleton = () => h('span', { class: 'bklog-list-refresh-skeleton' }, [h(LoadingSkeleton)]);
export const listSkeletonIndicators = { log: renderLogListSkeleton, 'log-table': renderLogTableSkeleton,
  fields: renderFieldListSkeleton, dropdown: renderDropdownListSkeleton };
