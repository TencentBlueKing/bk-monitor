/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import {
  createApp,
  h,
  nextTick,
  ref,
  type App,
  type Component,
  type ComponentPublicInstance,
  type VNode,
  type VNodeChild,
} from 'vue';
import type { ApplicationInjections } from '@/shared/types/component-injections';
import { routeLocationKey, routerKey } from 'vue-router';
import { createMonitorHostRouter, type MonitorHostRoute, type MonitorHostRouter } from './host-router';
type HostRenderData = {
  props?: Record<string, unknown>;
  attrs?: Record<string, unknown>;
  on?: Record<string, (...args: never[]) => unknown>;
  [key: string]: unknown;
};
type HostCreateElement = (component: Component | string, data?: HostRenderData, children?: VNodeChild) => VNode;
type MonitorFeedbackName = '$bkInfo' | 'messageError' | 'messageSuccess' | 'messageInfo' | 'messageWarn';
type MonitorFeedback = Pick<ApplicationInjections, MonitorFeedbackName>;
interface HostApplicationOptions<Store, I18n> {
  render: (h: HostCreateElement) => VNode;
  store?: Store;
  i18n?: I18n;
  router?: MonitorHostRouter;
}
/** Translate only the Vue2 mount envelope used by Monitor's existing hosts. */
export function createMonitorHostRenderer(): HostCreateElement {
  // Vue2-observed arrays do not notify Vue3. Snapshot on content changes while
  // retaining identity for unchanged values, so route updates cannot requery time.
  const arrays = new WeakMap<unknown[], unknown[]>();
  return (component, data = {}, children) => {
    const { props, attrs, on, ...rest } = data;
    const nativeProps = Object.fromEntries(Object.entries(props ?? {}).map(([name, value]) => {
      if (!Array.isArray(value)) return [name, value];
      const previous = arrays.get(value);
      const snapshot = previous && previous.length === value.length && previous.every((item, index) => Object.is(item, value[index]))
        ? previous : value.slice();
      arrays.set(value, snapshot);
      return [name, snapshot];
    }));
    const listeners = Object.fromEntries(Object.entries(on ?? {}).map(([name, handler]) => [
      `on${name.charAt(0).toUpperCase()}${name.slice(1)}`, handler,
    ]));
    return h(component, { ...rest, ...attrs, ...nativeProps, ...listeners }, children ?? undefined);
  };
}
export function createMonitorApplication<Store, I18n extends { t: (...args: never[]) => unknown }>(runtime: {
  configure: (app: App) => void;
  store: Store;
  i18n: I18n;
  feedback?: Partial<MonitorFeedback>;
  wrapRoot?: (node: VNode) => VNode;
}) {
  return class MonitorApplication {
    // Trace sets these on the exported constructor prototype before creation.
    declare $router: MonitorHostRouter;
    declare $route: MonitorHostRoute;
    declare _$route: MonitorHostRoute;
    readonly $store: Store;
    readonly $i18n: I18n;
    $t: I18n['t'];
    readonly $nextTick = nextTick;
    _isDestroyed = false;
    private app: App | undefined;
    private vm: (ComponentPublicInstance & Partial<MonitorFeedback>) | undefined;
    private hostRouter: ReturnType<typeof createMonitorHostRouter> | undefined;
    private renderVersion = ref(0);
    private renderNode = createMonitorHostRenderer();
    constructor(private options: HostApplicationOptions<Store, I18n>) {
      this.$store = options.store ?? runtime.store;
      this.$i18n = options.i18n ?? runtime.i18n;
      this.$t = this.$i18n.t.bind(this.$i18n) as I18n['t'];
      if (options.router) this.$router = options.router;
    }
    private feedback<Name extends MonitorFeedbackName>(name: Name): MonitorFeedback[Name] | undefined {
      return runtime.feedback?.[name] ?? this.vm?.[name] ?? this.app?.config.globalProperties[name];
    }
    get $bkInfo() { return this.feedback('$bkInfo'); }
    get messageError() { return this.feedback('messageError'); }
    get messageSuccess() { return this.feedback('messageSuccess'); }
    get messageInfo() { return this.feedback('messageInfo'); }
    get messageWarn() { return this.feedback('messageWarn'); }
    get $el(): Element | undefined {
      return this.vm?.$el;
    }
    get $refs(): ComponentPublicInstance['$refs'] {
      return this.vm?.$refs ?? {};
    }
    $mount(target: Element | string | null) {
      if (this.app || this._isDestroyed) return this;
      if (!this.$router) throw new Error('Monitor host router is required before mounting');
      this.hostRouter = createMonitorHostRouter(this.$router, this.$route);
      const bridge = this.hostRouter;
      if (!this.$route) Object.defineProperty(this, '$route', { get: () => bridge.route });
      const app = createApp({
        compatConfig: { MODE: 3 },
        render: () => {
          void this.renderVersion.value;
          const node = this.options.render(this.renderNode);
          return runtime.wrapRoot ? runtime.wrapRoot(node) : node;
        },
      });
      runtime.configure(app);
      app.provide(routerKey, bridge.router);
      app.provide(routeLocationKey, bridge.route);
      app.config.globalProperties.$router = bridge.router;
      Object.defineProperty(app.config.globalProperties, '$route', { configurable: true, get: () => bridge.route });
      this.app = app;
      this.vm = app.mount(target ?? document.createElement('div'));
      return this;
    }
    $forceUpdate() {
      if (this._isDestroyed) return;
      this.hostRouter?.synchronize();
      this.renderVersion.value++;
    }
    $destroy() {
      if (this._isDestroyed) return;
      this.app?.unmount();
      this.app = undefined;
      this.vm = undefined;
      this._isDestroyed = true;
    }
  };
}
