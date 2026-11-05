/**
 * 项目自定义指令 v-log-overflow-tips。
 * 文本溢出时才弹出 TDesign Popup。TDesign 没有对应指令。
 */
import type { Directive } from 'vue';
import { bindHoverPopup, refreshHoverPopup, unbindHoverPopup } from './log-popup';

const logOverflowTips: Directive = {
  mounted(el, binding) {
    bindHoverPopup(el, binding, true);
  },
  updated(el, binding) {
    refreshHoverPopup(el, binding, true);
  },
  unmounted(el) {
    unbindHoverPopup(el);
  },
};

export default logOverflowTips;
