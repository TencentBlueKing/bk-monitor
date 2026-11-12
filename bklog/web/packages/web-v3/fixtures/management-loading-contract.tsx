import { createApp, defineComponent, ref } from 'vue';
import { Button, Table } from 'tdesign-vue-next';
import ManagementListLoading from '../src/shared/ui/loading/management-list-loading';
import 'tdesign-vue-next/es/style/index.css';
import '../src/shared/styles/theme/management-lists.scss';

// Authored from scratch; no requests, application bootstrap or business records.
createApp(defineComponent({
  setup() {
    const loading = ref(true), wide = ref(false), populated = ref(false), constrained = ref(false);
    const columns = [
      { colKey: 'name', title: 'Synthetic name', width: 240 },
      { colKey: 'kind', title: 'Synthetic kind', width: 160 },
      { colKey: 'status', title: 'Synthetic status', width: 180 },
      { colKey: 'operation', title: 'Operation', width: 120 },
    ];
    const data = Array.from({ length: 12 }, (_, index) => ({ name: `Synthetic row ${index + 1}`, kind: 'Example', status: 'Ready', operation: '—' }));
    return () => (
      <main class='manage-ui-aligned' style={{ padding: '24px', fontFamily: 'sans-serif' }}>
        <h1>Management table: isolated loading contract</h1>
        <p>Entirely synthetic; no backend requests.</p>
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
          <Button aria-pressed={loading.value} onClick={() => { loading.value = !loading.value; }}>Toggle loading</Button>
          <Button aria-pressed={populated.value} onClick={() => { populated.value = !populated.value; }}>Toggle data</Button>
          <Button aria-pressed={wide.value} onClick={() => { wide.value = !wide.value; }}>Toggle width</Button>
          <Button aria-pressed={constrained.value} onClick={() => { constrained.value = !constrained.value; }}>Toggle height</Button>
        </div>
        <section style={{ width: wide.value ? '100%' : '760px', maxWidth: '100%' }}>
          <ManagementListLoading loading={loading.value}>
            <Table class='bklog-legacy-table' columns={columns} data={populated.value ? data : []} maxHeight={constrained.value ? 220 : undefined} rowKey='name' pagination={{ defaultCurrent: 1, defaultPageSize: 5, pageSizeOptions: [5, 10, 20], total: populated.value ? data.length : 0 }} />
          </ManagementListLoading>
        </section>
      </main>
    );
  },
})).mount('#management-loading-contract');
