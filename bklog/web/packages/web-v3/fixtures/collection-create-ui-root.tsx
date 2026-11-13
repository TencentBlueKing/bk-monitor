import i18n from '../src/platform/i18n/i18n';
import { createApp, defineComponent, ref } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import { installLegacyBkControls } from '../src/platform/compat/tdesign/legacy-bk-controls';
import { AddIcon } from 'tdesign-icons-vue-next';
import { Button, Checkbox, CheckboxGroup, TagInput, Textarea } from 'tdesign-vue-next';
import { useGlobalsStore } from '../src/app/state/domains/globals-store';
import { LoadingDirective } from '../src/shared/ui/loading/native';
import { renderCodeSampleSkeleton } from '../src/shared/ui/loading/list-skeleton';
import 'tdesign-vue-next/es/style/index.css';
import '../src/shared/ui/loading/skeleton.scss';
import '../src/features/collection/current/components/create-operation/step3-clean.scss';

import '../src/features/collection/current/components/create-operation/step2-configuration.scss';
import '../src/features/collection/current/components/create-operation/step4-storage.scss';
const { default: ReportLogSlider } = await import('../src/features/collection/current/components/business-comp/step3/report-log-slider');
const { default: LogFilter } = await import('../src/features/collection/current/components/business-comp/step2/log-filter');
const { default: ClusterTable } = await import('../src/features/collection/current/components/business-comp/step4/cluster-table');

// Synthetic initial state, without application bootstrap. Remote delimiter
// preview is covered by mocked contract tests; do not invoke it in this fixture.
const pinia = createPinia();
useGlobalsStore(pinia).setGlobalsData({ data_delimiter: [{ id: '|', name: '|' }] });
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] });
const app = createApp(defineComponent({
  setup() {
    const loading = ref(true), filter = ref<any>(), report = ref('');
    const drawer = ref(false), empty = ref(false), expanded = ref(['shared', 'exclusive']);
    const species = ref(['Application', 'Security', 'System', 'Other']);
    const conditions = { type: 'match' as const, match_content: 'synthetic', match_type: 'include' };
    return () => <main style={{ padding: '24px', fontFamily: 'sans-serif' }}>
      <h1>Collection create UI contract</h1>
      <Button theme='primary' icon={() => <AddIcon size='18px' />}>采集项</Button>
      <button onClick={() => { empty.value = false; drawer.value = true; }}>Open report</button>
      <button onClick={() => { empty.value = true; drawer.value = true; }}>Open empty report</button>
      <ReportLogSlider isShow={drawer.value} jsonText={empty.value ? {} : { message: 'Synthetic example', nested: { enabled: true }, items: ['first', 'second'] }} onChange={value => { drawer.value = value; }} />
      <section class='operation-step2-configuration'>
        <div class='source-log-info'><div class='label-form-box'><div class='form-box'><CheckboxGroup class='log-type-box' value={species.value} onChange={value => { species.value = value as string[]; }}>
          <div class='species-item'>{['Application', 'Security', 'System', 'Other'].map(name => <Checkbox class={{ other: name === 'Other' }} value={name}>{name}</Checkbox>)}
            <TagInput class='species-other-input' />
          </div>
        </CheckboxGroup></div></div></div>
      </section>
      <section style={{ maxWidth: '1100px' }}>
        <LogFilter ref={filter} conditions={conditions} />
        <button onClick={() => { report.value = String(filter.value?.validateInputs()); }}>Validate filters</button>
        <output>{report.value}</output>
      </section>
      <button onClick={() => { loading.value = !loading.value; }}>Toggle loading</button>
      <section class='operation-step3-clean' style={{ height: 'auto', margin: '20px 0' }}>
        <div class='log-sample-box' style={{ maxWidth: '1100px' }}>
          <div class='example-box'>Sample actions remain outside the editor</div>
          <div class='log-sample-editor' v-loading={{ loading: loading.value, indicator: renderCodeSampleSkeleton }}>
            <Textarea value='Synthetic example' autosize={{ minRows: 2, maxRows: 2 }} />
          </div>
        </div>
      </section>
      <section class='operation-step4-storage' style={{height: 'auto'}}><div class='cluster-box'>
        <bk-collapse value={expanded.value} onChange={value => { expanded.value = value; }}>
          {['shared', 'exclusive'].map((key, index) => <bk-collapse-item name={key} hideArrow v-slots={{ content: () => <div class='cluster-content'><ClusterTable loading={loading.value} clusterList={[]} name={index ? '业务独享集群' : '共享集群'} /></div> }}>
            <div class='cluster-title'><span class='title'>{index ? '业务独享集群' : '共享集群'}</span>{!!index && <span class='title-tips'>Synthetic group hint</span>}</div>
          </bk-collapse-item>)}
        </bk-collapse>
      </div></section>
    </main>;
  },
}));
installLegacyBkControls(app);
app.use(pinia); app.use(router); app.use(i18n);
app.directive('loading', LoadingDirective);
app.mount('#collection-create-ui');
