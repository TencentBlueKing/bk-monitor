/* eslint-disable codecc/license */
type RuntimeWindow = Window & {
  [key: string]: unknown;
  _?: unknown;
  '__core-js_shared__'?: Record<string, unknown>;
  __VUE_INSTANCE_SETTERS__?: unknown[];
  __VUE_SSR_SETTERS__?: unknown[];
  rawWindow?: Window;
  webpackChunktrace?: unknown[];
};

const vueSetterKeys = ['__VUE_INSTANCE_SETTERS__', '__VUE_SSR_SETTERS__'] as const;
const sandboxRuntimeKeys = [
  '__VUE_DEVTOOLS_HOOK',
  '__VUE_DEVTOOLS_KIT_APP_RECORDS__',
  '__VUE_DEVTOOLS_KIT_ACTIVE_APP_RECORD__',
  '__VUE_DEVTOOLS_KIT_ACTIVE_APP_RECORD_ID__',
  '__VUE_DEVTOOLS_KIT_CUSTOM_TABS__',
  '__VUE_DEVTOOLS_KIT_CUSTOM_COMMANDS__',
  '__VUE_DEVTOOLS_KIT_GLOBAL_STATE__',
  '__VUE_DEVTOOLS_KIT_CONTEXT__',
  '__VUE_DEVTOOLS_UPDATE_CLIENT_DETECTED__',
  'filterCSS',
  'filterXSS',
  'i18n',
  'regeneratorRuntime',
];

export function prepareMicroAppRuntime(target: RuntimeWindow) {
  const rawWindow = (target.rawWindow || target) as RuntimeWindow;
  const globals = target === rawWindow ? [target] : [target, rawWindow];
  const vueBaselines = globals.flatMap(global =>
    vueSetterKeys.map(key => ({ global, key, members: global[key]?.slice() || [] }))
  );
  const functionPrototype = Function.prototype;
  const toStringBaseline = Object.getOwnPropertyDescriptor(functionPrototype, 'toString');
  const sharedBaseline = target['__core-js_shared__'];
  const inspectBaseline = sharedBaseline && Object.getOwnPropertyDescriptor(sharedBaseline, 'inspectSource');
  const nativeStringBaseline =
    sharedBaseline && Object.getOwnPropertyDescriptor(sharedBaseline, 'native-function-to-string');

  // Lodash otherwise captures the previous sandbox instance in its noConflict closure.
  target._ = undefined;
  // These library exports belong to the sandbox, including modules loaded after startup.
  for (const key of sandboxRuntimeKeys) target[key] = undefined;
  const injectedData = target.__BK_WEWEB_DATA__;
  const timeoutBaseline = target.setTimeout;
  const clearTimeoutBaseline = target.clearTimeout;
  const timeouts = new Set<number>();
  const setOwnedTimeout: Window['setTimeout'] = (handler, timeout, ...args) => {
    const callback =
      typeof handler === 'function'
        ? (...callbackArgs: unknown[]) => {
            timeouts.delete(timer);
            handler.apply(rawWindow, callbackArgs);
          }
        : handler;
    const timer = timeoutBaseline.call(target, callback, timeout, ...args);
    timeouts.add(timer);
    return timer;
  };
  const clearOwnedTimeout: Window['clearTimeout'] = timer => {
    if (timer !== undefined) timeouts.delete(timer);
    clearTimeoutBaseline.call(target, timer);
  };
  target.setTimeout = setOwnedTimeout;
  target.clearTimeout = clearOwnedTimeout;

  return () => {
    const ownedSetters = vueBaselines.map(({ global, key, members }) => ({
      array: global[key],
      members: global[key]?.filter(setter => members.indexOf(setter) < 0) || [],
    }));
    const chunks = target.webpackChunktrace;
    const chunkPush = chunks?.push;
    const installedToString = functionPrototype.toString;
    const shared = target['__core-js_shared__'];
    const installedInspect = shared?.inspectSource;
    const restoreSharedHelpers = () => {
      if (shared && target['__core-js_shared__'] === shared) {
        restoreOwnedField(shared, 'inspectSource', inspectBaseline, installedInspect);
        restoreOwnedField(shared, 'native-function-to-string', nativeStringBaseline, installedToString);
      }
      restoreOwnedField(functionPrototype, 'toString', toStringBaseline, installedToString);
    };
    // The host can load its own core-js before destroying this app and capture these closures.
    restoreSharedHelpers();
    let disposed = false;

    return () => {
      if (disposed) return;
      disposed = true;
      for (const { array, members } of ownedSetters) {
        if (!array) continue;
        for (let i = array.length - 1; i >= 0; i--) {
          if (members.indexOf(array[i]) >= 0) array.splice(i, 1);
        }
      }
      if (chunks && target.webpackChunktrace === chunks && chunks.push === chunkPush) {
        chunks.push = Array.prototype.push;
      }
      target._ = undefined;
      for (const key of sandboxRuntimeKeys) target[key] = undefined;
      if (target.__BK_WEWEB_DATA__ === injectedData) target.__BK_WEWEB_DATA__ = undefined;
      for (const timer of timeouts) clearTimeoutBaseline.call(target, timer);
      timeouts.clear();
      if (target.setTimeout === setOwnedTimeout) target.setTimeout = timeoutBaseline;
      if (target.clearTimeout === clearOwnedTimeout) target.clearTimeout = clearTimeoutBaseline;
      restoreSharedHelpers();
    };
  };
}

function restoreOwnedField(target: object, key: string, previous: PropertyDescriptor | undefined, owned: unknown) {
  if (owned === previous?.value || Object.getOwnPropertyDescriptor(target, key)?.value !== owned) return;
  if (previous) Object.defineProperty(target, key, previous);
  else Reflect.deleteProperty(target, key);
}
