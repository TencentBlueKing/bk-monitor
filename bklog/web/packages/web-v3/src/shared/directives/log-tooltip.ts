/**
 * 项目自定义指令 v-log-tooltip。
 * TDesign 没有 tooltip 指令，弹出层使用 TDesign Popup。
 */
import type { Directive } from 'vue';
import { bindHoverPopup, refreshHoverPopup, unbindHoverPopup } from './log-popup';

const logTooltip: Directive = {
  mounted(el, binding) {
    bindHoverPopup(el, binding);
  },
  updated(el, binding) {
    refreshHoverPopup(el, binding);
  },
  unmounted(el) {
    unbindHoverPopup(el);
  },
};

export default logTooltip;
