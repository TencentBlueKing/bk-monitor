import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import ItemSkeleton from '@/app/skeleton/item-skeleton';
import { t } from '@/shared/composables/use-locale';
import './management-list-loading.scss';

/** Presentation only: keep the actual table, headers, slots and pagination mounted. */
export default defineComponent({
  name: 'ManagementListLoading',
  props: {
    loading: { type: Boolean, default: false },
    rows: { type: Number, default: 6 },
    rowHeight: { type: Number, default: 42 },
  },
  setup(props, { slots }) {
    const root = ref<HTMLElement | null>(null);
    const geometry = ref({ top: 40, left: 0, width: '100%', columns: ['1fr', '1fr', '1fr', '1fr', '1fr'], rowHeight: props.rowHeight, rows: props.rows,
      maxHeight: undefined as number | undefined, tableMinHeight: 40 + props.rows * props.rowHeight });
    let observer: ResizeObserver | undefined;
    let mutation: MutationObserver | undefined;
    let header: Element | null = null;
    let contentElement: Element | null = null;
    let disposed = false;

    const measure = () => {
      if (!props.loading || !root.value) return;
      const element = root.value;
      const table = element.querySelector('.t-table');
      const head = table?.querySelector('thead');
      if (!table || !head) return;
      const box = element.getBoundingClientRect();
      const tableBox = table.getBoundingClientRect();
      const headBox = head.getBoundingClientRect();
      const cells = [...head.querySelectorAll('tr:last-child > th')].filter(cell => cell.getBoundingClientRect().width > 0);
      const row = table.querySelector('tbody tr:not(.t-table__empty-row)');
      const height = row?.getBoundingClientRect().height;
      const rowHeight = height && height >= 32 && height <= 96 ? height : props.rowHeight;
      const content = table.querySelector<HTMLElement>('.t-table__content');
      const constrained = Boolean(content?.style.height || content?.style.maxHeight);
      const maxHeight = constrained ? Math.max(0, content!.getBoundingClientRect().bottom - headBox.bottom) : undefined;
      const bodyHeight = table.querySelector('tbody')?.getBoundingClientRect().height ?? 0;
      const rows = Math.max(props.rows, Math.ceil(Math.min(bodyHeight, maxHeight ?? Infinity) / rowHeight));
      geometry.value = {
        top: Math.max(0, headBox.bottom - box.top + element.scrollTop),
        left: tableBox.left - box.left + element.scrollLeft,
        width: `${Math.max(tableBox.width, headBox.width)}px`,
        columns: cells.length ? cells.map(cell => `${cell.getBoundingClientRect().width}px`) : geometry.value.columns,
        rowHeight,
        rows,
        maxHeight,
        tableMinHeight: constrained ? 0 : headBox.height + rows * rowHeight,
      };
      if (header !== head) {
        if (header) observer?.unobserve(header);
        header = head;
        observer?.observe(head);
        mutation?.disconnect();
        mutation?.observe(head, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'colspan'] });
        if (contentElement) mutation?.observe(contentElement, { attributes: true, attributeFilter: ['style'] });
      }
      if (contentElement !== content) {
        if (contentElement) observer?.unobserve(contentElement);
        contentElement = content;
        if (content) {
          observer?.observe(content);
          mutation?.observe(content, { attributes: true, attributeFilter: ['style'] });
        }
      }
    };
    watch(() => [props.loading, props.rowHeight], async () => {
      await nextTick();
      if (!disposed) measure();
    }, { flush: 'post' });
    onMounted(() => {
      if (typeof MutationObserver !== 'undefined') mutation = new MutationObserver(measure);
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(measure);
        if (root.value) observer.observe(root.value);
      }
      root.value?.addEventListener('scroll', measure, true);
      measure();
    });
    onBeforeUnmount(() => {
      disposed = true;
      observer?.disconnect();
      mutation?.disconnect();
      root.value?.removeEventListener('scroll', measure, true);
    });

    return () => (
      <div ref={root} class={['management-list-loading', { 'is-loading': props.loading }]} aria-busy={props.loading}
        style={props.loading ? {
          minHeight: `${geometry.value.top + Math.min(geometry.value.rows * geometry.value.rowHeight, geometry.value.maxHeight ?? Infinity)}px`,
          '--bklog-table-skeleton-min-height': `${geometry.value.tableMinHeight}px`,
        } : undefined}>
        {slots.default?.()}
        {props.loading && (
          <div class='management-list-skeleton' role='status' aria-label={t('加载中')} data-testid='management-list-skeleton'
            style={{ top: `${geometry.value.top}px`, left: `${geometry.value.left}px`, width: geometry.value.width,
              maxHeight: geometry.value.maxHeight === undefined ? undefined : `${geometry.value.maxHeight}px` }}>
            {Array.from({ length: geometry.value.rows }, (_, row) => (
              <div class='management-list-skeleton__row' aria-hidden='true' key={row}
                style={{ gridTemplateColumns: geometry.value.columns.join(' '), height: `${geometry.value.rowHeight}px` }}>
                {geometry.value.columns.map((_, column) => (
                  <div class='management-list-skeleton__cell' key={column}>
                    <ItemSkeleton rows={1} columns={1} type='list' gap='0px' rowHeight='14px' widths={[['72%', '56%', '84%'][(row + column) % 3]]} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  },
});
