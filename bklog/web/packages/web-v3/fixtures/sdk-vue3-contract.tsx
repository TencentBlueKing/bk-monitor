import { createApp, defineComponent, ref } from 'vue';
import UsernameSelector from '../src/shared/ui/user-selector/legacy-contract';
import '@blueking/bk-user-selector/vue3/vue3.css';
import 'tdesign-vue-next/es/style/index.css';

// Authored synthetic users only; the fixture endpoint never forwards to a business service.
createApp(defineComponent({
  setup() {
    const selected = ref(['synthetic.alex']), disabled = ref(false), blurCount = ref(0);
    const selector = ref<{ focus(): void } | null>(null);
    return () => <main style={{ padding: '24px', fontFamily: 'sans-serif' }}>
      <h1>Vue3 SDK user selector</h1>
      <button onClick={() => selector.value?.focus()}>Focus selector</button>
      <button onClick={() => { disabled.value = !disabled.value; }}>Toggle disabled</button>
      <UsernameSelector ref={selector} api='/__fixtures__/sdk-user-directory' placeholder='Synthetic username'
        style={{ width: '400px', marginTop: '16px' }} value={selected.value} disabled={disabled.value}
        onChange={value => { selected.value = value; }} onBlur={() => { blurCount.value++; }} />
      <output data-testid='selected-users'>{JSON.stringify(selected.value)}</output>
      <output data-testid='blur-count'>{blurCount.value}</output>
      <h2>Non-clearable tags</h2>
      <UsernameSelector api='/__fixtures__/sdk-user-directory' style={{ width: '400px' }}
        value={['synthetic.alex']} tagClearable={false} />
    </main>;
  },
})).mount('#sdk-vue3-contract');
