import { computed, defineComponent, h, type App, type Directive, type ComponentObjectPropsOptions } from 'vue';
import { dissolveSkeleton, useSkeletonPresence } from './presence';
import { Loading as NativeLoading, LoadingPlugin as nativeLoadingPlugin, type TdLoadingProps } from 'tdesign-vue-next';
import { isEqual } from 'lodash-es';
import { renderLoadingSkeleton } from './skeleton';

/** Keep TDesign's attachment, delay, overlay, scroll lock and teardown semantics. */
export const Loading = defineComponent<TdLoadingProps>({
  name: 'SkeletonLoading',
  inheritAttrs: false,
  props: NativeLoading.props as ComponentObjectPropsOptions<TdLoadingProps>,
  setup(props, { attrs, slots }) {
    const presence = useSkeletonPresence(computed(() => props.loading !== false));
    return () => h(NativeLoading, {
      ...attrs, ...props,
      class: ['bklog-module-loading', attrs.class, { 'is-leaving': presence.leaving.value }],
      loading: presence.visible.value,
      indicator: props.indicator === false ? false : (typeof props.indicator === 'function' ? props.indicator : renderLoadingSkeleton),
    }, { ...slots, indicator: slots.indicator ?? (typeof props.indicator === 'function' ? props.indicator : undefined) });
  },
});

let pluginSequence = 0;
export const LoadingPlugin = Object.assign(
  (options: Parameters<typeof nativeLoadingPlugin>[0] = {}, context?: Parameters<typeof nativeLoadingPlugin>[1]) => {
    const value = typeof options === 'boolean' ? { loading: options } : options;
    const ownerClass = `bklog-loading-owner-${++pluginSequence}`;
    const pluginOptions = { ...value,
      class: [ownerClass, (value as Record<string, unknown>).class],
      indicator: value.indicator === false ? false : (typeof value.indicator === 'function' ? value.indicator : renderLoadingSkeleton),
    };
    const instance = nativeLoadingPlugin(pluginOptions, context);
    let hidden = false, destroyed = false;
    let cancelExit: (() => void) | undefined;
    const destroy = () => {
      if (destroyed) return;
      destroyed = true;
      cancelExit?.();
      instance?.hide();
    };
    return {
      destroy,
      hide() {
        if (hidden || destroyed) return;
        hidden = true;
        const element = typeof document === 'undefined' ? null : document.querySelector<HTMLElement>(`.${ownerClass}`);
        if (element) cancelExit = dissolveSkeleton(element, destroy);
        else destroy();
      },
    };
  },
  { install(app: App) { app.config.globalProperties.$loading = LoadingPlugin; } },
);

type BindingValue = boolean | (TdLoadingProps & { isLoading?: boolean; title?: string });

/** One instance per host. An active options change must not orphan the previous overlay. */
export function createSkeletonLoadingDirective(service = LoadingPlugin): Directive<HTMLElement, BindingValue> {
  const instances = new WeakMap<HTMLElement, { instance: ReturnType<typeof LoadingPlugin>; closing: boolean }>();
  const remove = (el: HTMLElement) => {
    const owned = instances.get(el);
    if (owned?.instance.destroy) owned.instance.destroy();
    else if (owned && !owned.closing) owned.instance.hide();
    instances.delete(el);
  };
  const paint = (el: HTMLElement, value: BindingValue, modifiers: Partial<Record<string, boolean>>) => {
    const options = typeof value === 'object' && value !== null ? value : { loading: Boolean(value) };
    const loading = options.loading ?? ('isLoading' in options ? options.isLoading : true);
    if (!loading) {
      const owned = instances.get(el);
      if (owned && !owned.closing) { owned.closing = true; owned.instance.hide(); }
      return;
    }
    // New requests and unmount destroy a previous visual exit before native ownership changes.
    remove(el);
    instances.set(el, { instance: service({
      attach: () => el,
      fullscreen: Boolean(modifiers.fullscreen),
      inheritColor: Boolean(modifiers.inheritColor),
      ...options,
      text: options.text ?? ('title' in options ? options.title : undefined),
      loading,
    }), closing: false });
  };
  return {
    mounted(el, binding) { paint(el, binding.value, binding.modifiers); },
    updated(el, binding) {
      if (!isEqual(binding.value, binding.oldValue)) paint(el, binding.value, binding.modifiers);
    },
    unmounted: remove,
  };
}
export const LoadingDirective = createSkeletonLoadingDirective();
