import { h, type Ref, type SetupContext, type ComponentOptions, type VNodeRef } from 'vue';
import createIpSelector from '@blueking/ip-selector/dist/vue3.x';

/** Official Vue3 factory; this installed SDK still contains an internal Vue2 app. */
export default (options: Record<string, unknown>) => {
  const definition = createIpSelector(options);
  const sdkSetup = definition.setup!;
  return {
    ...definition,
    compatConfig: { ...definition.compatConfig, MODE: 3 },
    setup(props: Record<string, unknown>, context: SetupContext) {
      const state = sdkSetup(props, context) as { rootRef: Ref<HTMLElement | null>; app: unknown };
      // String refs through the compatibility runtime do not reliably update the SDK's closed-over ref.
      // A callback ref fills the official ref before its existing mounted hook executes.
      return { ...state, mountRoot: (element: HTMLElement | null) => { state.rootRef.value = element; } };
    },
    render(this: { mode?: string; mountRoot: VNodeRef }) {
      return h('div', {
        role: 'bk-ip-selector',
        ref: this.mountRoot,
        style: { height: this.mode === 'dialog' ? 'auto' : 'inherit' },
      });
    },
  } satisfies ComponentOptions;
};
