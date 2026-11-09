/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */

const slotGuardFrom =
  'currentInstance && !(ctx === null && currentRenderingInstance) && !(ctx && ctx.root !== currentInstance.root)';
const slotGuardTo =
  'currentInstance && !currentRenderingInstance && !(ctx && ctx.root !== currentInstance.root)';

const ownKeysFrom =
  /PublicInstanceProxyHandlers\.ownKeys = \(target\) => \{\s*warn\$1\(\s*`Avoid app logic that relies on enumerating keys on a component instance\. The keys will be empty in production mode to avoid performance overhead\.`\s*\);\s*return Reflect\.ownKeys\(target\);\s*\};/;

const instanceHasOwnFrom = `get({ _: instance }, key) {
    if (key === "__v_skip") {
      return true;
    }`;
const instanceHasOwnTo = `get({ _: instance }, key) {
    if (key === "hasOwnProperty") {
      return Object.prototype.hasOwnProperty;
    }
    if (key === "__v_skip") {
      return true;
    }`;

const nullParentPatchFrom = `patch(
          prevTree,
          nextTree,
          // parent may have changed if it's in a teleport
          hostParentNode(prevTree.el),
          // anchor may have changed if it's in a fragment
          getNextHostNode(prevTree),
          instance,
          parentSuspense,
          namespace
        );`;
const nullParentPatchTo = `if (prevTree.el && hostParentNode(prevTree.el)) {
        patch(
          prevTree,
          nextTree,
          // parent may have changed if it's in a teleport
          hostParentNode(prevTree.el),
          // anchor may have changed if it's in a fragment
          getNextHostNode(prevTree),
          instance,
          parentSuspense,
          namespace
        );
        }`;

function patchVueRuntime(code) {
  return code
    .replaceAll(slotGuardFrom, slotGuardTo)
    .replace(
      ownKeysFrom,
      'PublicInstanceProxyHandlers.ownKeys = (target) => Reflect.ownKeys(target);',
    )
    .replaceAll(instanceHasOwnFrom, instanceHasOwnTo)
    .replaceAll(nullParentPatchFrom, nullParentPatchTo)
    .replaceAll(
      'parentNode: (node) => node.parentNode,',
      'parentNode: (node) => node == null ? null : node.parentNode,',
    )
    .replaceAll(
      'warn$1(`provide() can only be used inside setup().`);',
      'warn$1(`provide() can only be used inside setup().`); try { (window.__provideStack = window.__provideStack || []).push(new Error().stack || \"\"); } catch(e) {}',
    );
}

function patchDraggable(code) {
  return code
    .replace(
      'var addContext = function addContext(domElement, context) {\n  return domElement.__draggable_context = context;\n};',
      'var addContext = function addContext(domElement, context) {\n  if (!domElement) return;\n  return domElement.__draggable_context = context;\n};',
    )
    .replace(
      'updated: function updated() {\n    this.componentStructure.updated();\n  }',
      'updated: function updated() {\n    if (this.componentStructure) this.componentStructure.updated();\n  }',
    )
    .replace(
      'componentStructure = this.componentStructure;\n    componentStructure.updated();',
      'componentStructure = this.componentStructure;\n    if (componentStructure) componentStructure.updated();',
    )
    .replace(
      'q=function(t,e){return t.__draggable_context=e}',
      'q=function(t,e){return t&&(t.__draggable_context=e)}',
    )
    .replace(
      'updated:function(){this.componentStructure.updated()}',
      'updated:function(){this.componentStructure&&this.componentStructure.updated()}',
    )
    .replace('r=this.componentStructure;r.updated()', 'r=this.componentStructure;r&&r.updated()')
    .replace('var $slots = this.$slots,', 'var $slots = this.$ && this.$.slots || this.$slots,')
    .replace('var t=this.$slots,e=this.$attrs', 'var t=this.$&&this.$.slots||this.$slots,e=this.$attrs');
}

function patchAiBlueking(code) {
  if (!code.includes('addEventListener("unload"') && !code.includes("addEventListener('unload'")) {
    return code;
  }
  return code
    .replaceAll('addEventListener("unload"', 'addEventListener("pagehide"')
    .replaceAll('removeEventListener("unload"', 'removeEventListener("pagehide"')
    .replaceAll("addEventListener('unload'", "addEventListener('pagehide'")
    .replaceAll("removeEventListener('unload'", "removeEventListener('pagehide'")
    .replaceAll(
      '(0, Yr.provide)(Xs, r);',
      'if ((0, Yr.getCurrentInstance)()) (0, Yr.provide)(Xs, r);',
    );
}

function patchModule(id, code) {
  const path = id.replaceAll('\\', '/');
  if (path.includes('/@vue/compat/') || path.includes('/vue/dist/vue.esm-bundler')) {
    const next = patchVueRuntime(code);
    return next === code ? null : next;
  }
  if (path.includes('/vuedraggable/')) {
    const next = patchDraggable(code);
    return next === code ? null : next;
  }
  if (path.includes('/ai-blueking/')) {
    const next = patchAiBlueking(code);
    return next === code ? null : next;
  }
  return null;
}

export function runtimeWarningPatchesVitePlugin() {
  return {
    name: 'runtime-warning-patches',
    enforce: 'pre',
    transform(code, id) {
      const next = patchModule(id, code);
      return next ? { code: next, map: null } : undefined;
    },
  };
}

export function runtimeWarningPatchesEsbuildPlugin() {
  return {
    name: 'runtime-warning-patches',
    setup(build) {
      build.onLoad({ filter: /@vue\+compat|@vue\/compat|vuedraggable|ai-blueking/ }, async (args) => {
        if (!/\.(?:m?js|cjs)$/.test(args.path)) return null;
        const { readFile } = await import('node:fs/promises');
        const source = await readFile(args.path, 'utf8');
        const next = patchModule(args.path, source);
        if (!next) return null;
        return { contents: next, loader: 'js' };
      });
    },
  };
}
