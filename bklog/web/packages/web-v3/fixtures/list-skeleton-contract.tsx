import { createApp, defineComponent, ref } from 'vue';
import { Loading, LoadingDirective } from '../src/shared/ui/loading/native';
import { renderFieldListSkeleton, renderLogListSkeleton, renderLogTableSkeleton, renderListRefreshSkeleton } from '../src/shared/ui/loading/list-skeleton';
import 'tdesign-vue-next/es/style/index.css';
import '../src/shared/ui/loading/skeleton.scss';

// No backend requests or business records. Match real overlay ownership, including tbody.
const app = createApp(defineComponent({
  setup() {
    const loading = ref(true), tall = ref(false), narrow = ref(false);
    const populated = ref(false);
    return () => <main style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>List skeleton contract</h1>
      <button onClick={() => { loading.value = !loading.value; }}>Toggle loading</button>
      <button onClick={() => { tall.value = !tall.value; }}>Toggle height</button>
      <button onClick={() => { narrow.value = !narrow.value; }}>Toggle width</button>
      <button onClick={() => { populated.value = !populated.value; }}>Toggle existing rows</button>
      <div style={{ display: 'grid', gridTemplateColumns: `${narrow.value ? 160 : 260}px minmax(0,1fr)`, gap: '16px', marginTop: '16px' }}>
        <section><h2>Fields</h2><Loading loading={loading.value} indicator={renderFieldListSkeleton}>
          <div data-testid='fields' style={{ height: tall.value ? '680px' : '320px' }}>Synthetic field list</div>
        </Loading></section>
        <section><h2>Context / realtime</h2><Loading loading={loading.value} showOverlay={!populated.value} indicator={populated.value ? renderListRefreshSkeleton : renderLogListSkeleton}>
          <div data-testid='logs' style={{ height: tall.value ? '680px' : '320px' }}>Synthetic log list</div>
        </Loading></section>
      </div>
      <section style={{ height: tall.value ? '680px' : '360px', position: 'relative', marginTop: '16px' }}>
        <table style={{ width: '100%', height: '100%', tableLayout: 'fixed', borderCollapse: 'collapse' }}>
          <thead style={{ height: '32px', background: '#f5f7fa' }}><tr><th style={{ width: '90px' }}>Row</th><th style={{ width: '200px' }}>Time</th><th>Original log</th></tr></thead>
          <tbody v-loading={{ loading: loading.value, indicator: renderLogTableSkeleton }}><tr><td colSpan={3}>Synthetic results</td></tr></tbody>
        </table>
      </section>

    </main>;
  },
}));
app.directive('loading', LoadingDirective);
app.mount('#list-skeleton-contract');
