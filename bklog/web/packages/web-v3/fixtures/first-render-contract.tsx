import { createApp, computed, defineComponent, nextTick, ref } from 'vue';
import { Loading } from '../src/shared/ui/loading/native';
import NavigationSkeleton from '../src/shared/ui/loading/navigation-skeleton';
import RetrievePageSkeleton from '../src/app/skeleton/retrieve-page-skeleton.vue';
import { useSkeletonPresence } from '../src/shared/ui/loading/presence';
import 'tdesign-vue-next/es/style/index.css';
import '../src/shared/ui/loading/skeleton.scss';

// Entirely synthetic. Controls represent independent deferred tasks; no services or app bootstrap.
createApp(defineComponent({
  setup() {
    const modules = ref(false), menu = ref(false), result = ref(false), counter = ref(0);
    const sample = ref('No sample');
    const resolveResults = async () => {
      result.value = true;
      counter.value++;
      await nextTick();
      const overlay = document.querySelector('[data-testid="module-loading"]');
      const content = document.querySelector<HTMLElement>('[data-testid="result-content"]');
      sample.value = JSON.stringify({ leaving: overlay?.classList.contains('is-leaving'),
        content: content?.textContent, contentOpacity: content ? getComputedStyle(content).opacity : null });
    };
    const pending = computed(() => !modules.value);
    const page = useSkeletonPresence(pending);
    return () => <main style={{ fontFamily: 'sans-serif' }}>
      <header style={{ display: 'flex', height: '52px', background: '#182132', color: '#fff' }}>
        <div style={{ position: 'relative', width: '300px' }}><span>Synthetic workspace</span>
          <NavigationSkeleton loading={!menu.value} count={2} /></div>
        <div style={{ position: 'relative', width: '360px' }}><span>Synthetic menu</span>
          <NavigationSkeleton loading={!menu.value} count={3} /></div>
      </header>
      <div style={{ display: 'flex', gap: '12px', padding: '16px' }}>
        <button onClick={async () => { await nextTick(); modules.value = true; }}>Initialize modules</button>
        <button onClick={() => { menu.value = true; }}>Resolve navigation</button>
        <button onClick={resolveResults}>Resolve results</button>
        <button onClick={() => { result.value = false; }}>Retry results</button>
        <button onClick={() => { counter.value++; }}>Update content</button>
      </div>
      <output data-testid='handoff-sample'>{sample.value}</output>
      <section data-phase={modules.value ? 'modules' : 'initializing'} style={{ position: 'relative', minHeight: '500px', padding: '16px' }}>
        <h2>Synthetic query toolbar</h2>
        <Loading loading={!result.value} showOverlay data-testid='module-loading'>
          <article style={{ height: '300px', background: '#fff' }} data-testid='result-content'>
            {result.value ? `Synthetic results ${counter.value}` : 'Waiting for synthetic results'}
          </article>
        </Loading>
        {page.visible.value && <RetrievePageSkeleton cover fieldWidth={160}
          class={['bklog-skeleton-presence', { 'is-leaving': page.leaving.value }]} />}
      </section>
    </main>;
  },
})).mount('#first-render-contract');
