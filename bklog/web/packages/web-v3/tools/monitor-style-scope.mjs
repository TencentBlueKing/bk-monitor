/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
const nativeRoots = ['.monitor-trace-log', '.tippy-content', '.t-popup', '.t-dialog', '.t-drawer', '.t-message__list', '.t-notification__list'];
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
      if (!native && !legacy) return;
      root.walkRules(rule => {
        if (rule.parent?.type === 'atrule' && /keyframes$/i.test(rule.parent.name)) return;
        rule.selectors = rule.selectors.flatMap(selector => {
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
