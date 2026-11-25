/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
const nativeRoots = ['.monitor-trace-log', '.tippy-content', '.t-popup', '.t-dialog', '.t-drawer', '.t-message__list', '.t-notification__list'];
const themeRoot = /^(:root(?:\[theme-mode=['"]dark['"]\]|:not\(\[theme-mode=['"]dark['"]\]\))?)(?:\s+|$)/;
const embeddedScope = `:where(${nativeRoots.join(', ')})`;
const embeddedTokenScope = `:is(${nativeRoots.join(', ')})`;
const logDrawers = [
  '.bklog-compat-drawer',
  '.bklog-full-row-viewer-sideslider',
  '.agg-field-item-sideslider',
  '.field-alias-drawer',
  '.cluster-settings-drawer',
];
const logDialogs = ['.bklog-info-box', '.log-realtime-dialog-main', '.log-context-dialog-main'];
const ownedPopup = ':where(.monitor-trace-log *, .bklog-text-tooltip)';
const ownedDrawer = `:where(.monitor-trace-log *, ${logDrawers.join(', ')})`;
const ownedDialog = `:where(.monitor-trace-log *, :has(${logDialogs.join(', ')}))`;
const logOverlayLayers = {
  'body .t-popup': ownedPopup,
  'body .t-drawer': ownedDrawer,
  'body .t-dialog__ctx.t-dialog__ctx--fixed': ownedDialog,
  'body .t-message__list': ':where(.monitor-trace-log *)',
  'body .t-notification': ':where(.monitor-trace-log *)',
};
const portalSelector = /^\.t-(?:popup|dialog|drawer|message|notification)(?:\b|__|--)/;
/** Trace embeds in a host document; native controls and teleported overlays both need styles. */
export function monitorControlStyleScope(kind) {
  return {
    postcssPlugin: 'bklog-monitor-control-scope',
    Once(root) {
      if (kind !== 'trace') return;
      const file = root.source?.input.file?.replaceAll('\\', '/') || '';
      const native = file.includes('/tdesign-vue-next/');
      const legacy = file.includes('/bk-magic-vue/lib/ui/');
      const sharedTheme = file.endsWith('/shared/styles/theme/tdesign-bklog.scss');
      if (!native && !legacy && !sharedTheme) return;
      root.walkRules(rule => {
        if (rule.parent?.type === 'atrule' && /keyframes$/i.test(rule.parent.name)) return;
        rule.selectors = rule.selectors.flatMap(selector => {
          if (sharedTheme) {
            if (Object.hasOwn(logOverlayLayers, selector)) return [selector + logOverlayLayers[selector]];
            const match = selector.match(themeRoot);
            if (!match) return [selector];
            const context = match[1];
            const body = selector.slice(match[0].length);
            // Keep namespaced BKLog tokens available to consumers. TDesign aliases
            // and Tabs overrides must stay within the embedded control scopes.
            if (!body && rule.nodes.every(node => node.type === 'decl' && node.prop.startsWith('--td-'))) {
              return [context === ':root' ? embeddedTokenScope : `${context} ${embeddedTokenScope}`];
            }
            // Portaled directive tooltips carry an ownership class on the
            // transition element itself, even when mounted directly under body.
            if (body.startsWith(':is(.t-popup--animation')) {
              return [`${context} ${body}${ownedPopup}`];
            }
            if (body.startsWith('.t-drawer :is(.t-drawer__content-wrapper')) {
              return [`${context} ${body.replace('.t-drawer ', `.t-drawer${ownedDrawer} `)}`];
            }
            if (body.startsWith(':is(.t-dialog-zoom__vue-enter-active')) {
              return [`${context} ${body.replace(') :is(', `)${ownedDialog} :is(`)}`];
            }
            return /\.t-tabs(?:\b|__)/.test(body) ? [`${context} ${embeddedScope} ${body}`] : [selector];
          }
          if (!native) return /^\.(tippy-|bk-tooltip-|bk-option-|bk-select-search-input|bk-select-dropdown-)/.test(selector)
            ? [selector] : [`.tippy-content ${selector}`, `.monitor-trace-log ${selector}`];
          // Popup roots live under body. The remaining controls are scoped to a
          // Trace root or one of these native overlay containers.
          if (portalSelector.test(selector)) return [selector];
          if ([':root', 'html', 'body'].includes(selector.trim())) return nativeRoots;
          if (selector.startsWith(':root')) return nativeRoots.map(scope => `${selector} ${scope}`);
          return nativeRoots.map(scope => `${scope} ${selector}`);
        });
      });
    },
  };
}
