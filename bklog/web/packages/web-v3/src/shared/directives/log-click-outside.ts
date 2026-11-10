/**
 * 项目自定义指令 v-log-click-outside。
 * TDesign 没有 click-outside 指令。
 */
import type { Directive } from 'vue';

type Host = HTMLElement & { _logClickOutside?: (event: MouseEvent) => void };

const logClickOutside: Directive = {
  mounted(el, binding) {
    const host = el as Host;
    host._logClickOutside = event => {
      if (event.target instanceof Node && !host.contains(event.target) && typeof binding.value === 'function') {
        binding.value(event);
      }
    };
    document.addEventListener('mousedown', host._logClickOutside);
  },
  unmounted(el) {
    const host = el as Host;
    if (host._logClickOutside) document.removeEventListener('mousedown', host._logClickOutside);
  },
};

export default logClickOutside;
