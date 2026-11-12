import { defineComponent, h, type App, type Directive, type ComponentObjectPropsOptions } from 'vue';
import { Loading as NativeLoading, LoadingPlugin as nativeLoadingPlugin, type TdLoadingProps } from 'tdesign-vue-next';
import { isEqual } from 'lodash-es';
import { renderLoadingSkeleton } from './skeleton';

/** Keep TDesign's attachment, delay, overlay, scroll lock and teardown semantics. */
export const Loading = defineComponent<TdLoadingProps>({
  name: 'SkeletonLoading',
  inheritAttrs: false,
  props: NativeLoading.props as ComponentObjectPropsOptions<TdLoadingProps>,
  setup(props, { attrs, slots }) {
    return () => h(NativeLoading, {
      ...attrs, ...props,
      indicator: props.indicator === false ? false : (typeof props.indicator === 'function' ? props.indicator : renderLoadingSkeleton),
    }, { ...slots, indicator: slots.indicator ?? (typeof props.indicator === 'function' ? props.indicator : undefined) });
  },
});

export const LoadingPlugin = Object.assign(
  (options: Parameters<typeof nativeLoadingPlugin>[0] = {}, context?: Parameters<typeof nativeLoadingPlugin>[1]) => {
    const value = typeof options === 'boolean' ? { loading: options } : options;
    return nativeLoadingPlugin({ ...value, indicator: value.indicator === false ? false : (typeof value.indicator === 'function' ? value.indicator : renderLoadingSkeleton) }, context);
  },
  { install(app: App) { app.config.globalProperties.$loading = LoadingPlugin; } },
);

type BindingValue = boolean | (TdLoadingProps & { isLoading?: boolean; title?: string });

/** One instance per host. An active options change must not orphan the previous overlay. */
export function createSkeletonLoadingDirective(service = LoadingPlugin): Directive<HTMLElement, BindingValue> {
  const instances = new WeakMap<HTMLElement, ReturnType<typeof LoadingPlugin>>();
  const remove = (el: HTMLElement) => {
    instances.get(el)?.hide();
    instances.delete(el);
  };
  const paint = (el: HTMLElement, value: BindingValue, modifiers: Partial<Record<string, boolean>>) => {
    remove(el);
    const options = typeof value === 'object' && value !== null ? value : { loading: Boolean(value) };
    const loading = options.loading ?? ('isLoading' in options ? options.isLoading : true);
    if (!loading) return;
    instances.set(el, service({
      attach: () => el,
      fullscreen: Boolean(modifiers.fullscreen),
      inheritColor: Boolean(modifiers.inheritColor),
      ...options,
      text: options.text ?? ('title' in options ? options.title : undefined),
      loading,
    }));
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
