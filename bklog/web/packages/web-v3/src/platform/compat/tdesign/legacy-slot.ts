import { h, mergeProps, renderSlot, type Slots, type VNode, type VNodeChild } from 'vue';

export interface LegacyFunctionalContext {
  scopedSlots?: Slots;
  [property: string]: unknown;
}
type LegacyRender = (createElement: typeof h, context?: LegacyFunctionalContext) => VNodeChild;
type LegacyLifecycle = (this: LegacyControlInstance) => void;
export interface LegacyComponentOptions {
  options?: LegacyComponentOptions;
  name?: string;
  functional?: boolean;
  render?: LegacyRender;
  components?: Record<string, unknown>;
  beforeCreate?: LegacyLifecycle | LegacyLifecycle[];
  beforeMount?: LegacyLifecycle | LegacyLifecycle[];
}
interface LegacyControlInstance {
  $options: LegacyComponentOptions & { render: LegacyRender };
  $attrs: Record<string, unknown>;
  $createElement: typeof h;
  _t?: ReturnType<typeof createLegacySlotRenderer>;
  $: {
    ctx: Record<string, unknown>;
    slots: Slots;
    accessCache: Record<string, number>;
    render?: (this: LegacyControlInstance) => VNodeChild;
  };
}

// Vue2.6 precompiled controls pass arrays; Vue2.7 controls pass lazy functions.
// Use the native slot renderer so both fallback forms keep their lazy semantics.
export function createLegacySlotRenderer(slots: Slots) {
  return (
    name: string,
    fallback?: VNode[] | (() => VNode[]),
    props?: Record<string, unknown>,
    bindObject?: Record<string, unknown>,
  ) =>
    renderSlot(
      slots,
      name,
      bindObject ? mergeProps(props || {}, bindObject) : props,
      fallback ? (typeof fallback === 'function' ? fallback : () => fallback) : undefined,
    );
}
export function initializeLegacySlots(this: LegacyControlInstance) {
  if (this.$options.name === 'bk-table-column') {
    const cellSlot =
      this.$attrs.nativeCellSlot || this.$attrs['native-cell-slot'] === '' || this.$attrs['native-cell-slot'] === true;
    const render = this.$options.render;
    const createElement = this.$createElement;
    // V2 excludes scoped cell slots from the hidden column registration tree.
    this.$.render = cellSlot
      ? () => h('div')
      : function (this: LegacyControlInstance) {
          return render.call(this, createElement);
        };
  }
  if (this._t) {
    Object.defineProperty(this.$.ctx, '_t', { configurable: true, value: createLegacySlotRenderer(this.$.slots) });
    delete this.$.accessCache._t;
  }
}

export function initializeLegacyRenderProxy(this: LegacyControlInstance) {
  Object.defineProperty(this.$.ctx, '_renderProxy', { configurable: true, get: () => this });
}
const adapted = new WeakSet<LegacyComponentOptions>();
/** Install only on vendor controls, before their instances are created. */
export function patchLegacyComponentSlots(component: unknown) {
  if (!component || (typeof component !== 'object' && typeof component !== 'function')) return;
  const control = component as LegacyComponentOptions;
  const options = control.options || control;
  if (adapted.has(options) || (!options.render && !options.components && options.name !== 'bk-table-column')) return;
  adapted.add(options);
  for (const [name, hook] of [
    ['beforeCreate', initializeLegacyRenderProxy],
    ['beforeMount', initializeLegacySlots],
  ] as const) {
    const previous = options[name];
    const hooks = Array.isArray(previous) ? previous : previous ? [previous] : [];
    if (!hooks.includes(hook)) options[name] = [hook, ...hooks];
  }
  for (const child of Object.values(options.components || {})) patchLegacyComponentSlots(child);
}
