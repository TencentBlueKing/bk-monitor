import { Loading } from '@/shared/ui/loading/native';
import { h } from 'vue';
import { DialogPlugin } from 'tdesign-vue-next';
import { t } from '../../../shared/composables/use-locale';
import { createInfoService } from './info-box-contract';
import { overlayRegistry } from '../../../shared/global/overlay/overlay-registry.js';
import 'tdesign-vue-next/es/dialog/style/index.css';
import 'tdesign-vue-next/es/loading/style/index.css';
export const bkInfoBox = createInfoService((props, source) => {
  props = { ...props, zIndex: props.zIndex ?? overlayRegistry.nextZIndex() };
  if (source.icon || source.type === 'loading') {
    const body = props.body;
    return DialogPlugin({
      ...props,
      theme: 'default',
      body: () =>
        h('div', { class: 'bklog-info-box-content' }, [
          source.icon ? h('i', { class: source.icon }) : h(Loading, { size: '32px' }),
          typeof body === 'function' ? body(h) : body,
        ]),
    });
  }
  return DialogPlugin(props);
}, t);
export { bkInfoBox as InfoBox };
