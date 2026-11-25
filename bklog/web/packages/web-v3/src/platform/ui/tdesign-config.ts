/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { h } from 'vue';
import type { GlobalConfigProvider } from 'tdesign-vue-next';

/** Same funnel used by the log collection list header filters. */
const tableFilterIcon = () => h('i', { class: 'bk-icon icon-funnel filter-icon' });

/** One owner for component defaults. Keep 1.20.x behavior; locale and explicit
 * component props can override it. Geometry belongs to style profiles, not here. */
export function createApplicationControlConfig(locale: GlobalConfigProvider): GlobalConfigProvider {
  return {
    ...locale,
    form: { requiredMark: true, requiredMarkPosition: 'left', ...locale.form },
    drawer: { closeOnEscKeydown: true, closeOnOverlayClick: true, ...locale.drawer },
    table: { size: 'medium', hideSortTips: false, ...locale.table, filterIcon: tableFilterIcon },
  };
}
