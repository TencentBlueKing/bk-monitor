/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
/** Keep the V2 Trace package's control and body-overlay selector protocol. */
export function monitorControlStyleScope(kind) {
  return {
    postcssPlugin:'bklog-monitor-control-scope',
    Once(root) {
      if(kind!=='trace'||!root.source?.input.file?.replaceAll('\\','/').includes('/bk-magic-vue/lib/ui/'))return;
      root.walkRules(rule=>{
        if(rule.parent?.type==='atrule'&&/keyframes$/i.test(rule.parent.name))return;
        rule.selectors=rule.selectors.map(selector=>
          /^\.(tippy-|bk-tooltip-|bk-option-|bk-select-search-input|bk-select-dropdown-)/.test(selector)
            ? selector : `.tippy-content ${selector}, .monitor-trace-log ${selector}`);
      });
    },
  };
}
