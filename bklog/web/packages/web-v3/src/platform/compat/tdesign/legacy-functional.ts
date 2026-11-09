import { createCommentVNode, createTextVNode, renderList, toDisplayString } from 'vue';
import { createLegacySlotRenderer, type LegacyComponentOptions } from './legacy-slot.ts';
const visited = new WeakSet<LegacyComponentOptions>();
// Vue2's precompiled functional templates expect helpers on their context;
// @vue/compat supplies props/slots but omits these compiler-generated helpers.
export function patchLegacyFunctionalContext(component: unknown) {
  if (!component || (typeof component !== 'object' && typeof component !== 'function')) return;
  const control = component as LegacyComponentOptions;
  const options = control.options || control;
  if (visited.has(options)) return;
  visited.add(options);
  if (options.functional && options.render) {
    const render = options.render;
    options.render = function (h, context) {
      return render(h, {
        ...context,
        _c: h,
        _t: createLegacySlotRenderer(context!.scopedSlots || {}),
        _e: createCommentVNode,
        _v: createTextVNode,
        _s: toDisplayString,
        _l: renderList,
      });
    };
  }
  for (const child of Object.values(options.components || {})) patchLegacyFunctionalContext(child);
}
