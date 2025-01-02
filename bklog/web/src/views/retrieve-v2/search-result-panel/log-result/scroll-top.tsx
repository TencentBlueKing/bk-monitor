import { computed, defineComponent, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import useScroll from '@/hooks/use-scroll';
import { getTargetElement } from '@/hooks/hooks-helper';

import { GLOBAL_SCROLL_SELECTOR } from './log-row-attributes';

export default defineComponent({
  setup() {
    const { $t } = useLocale();
    const offsetTop = ref(0);

    useScroll(GLOBAL_SCROLL_SELECTOR, event => {
      offsetTop.value = (event.target as HTMLElement).scrollTop;
    });

    const showBox = computed(() => offsetTop.value > 1000);
    const scrollTop = () => {
      getTargetElement(GLOBAL_SCROLL_SELECTOR)?.scrollTo(0, 0);
    };

    const renderBody = () => (
      <span
        class={['btn-scroll-top', { 'show-box': showBox.value }]}
        v-bk-tooltips={$t('返回顶部')}
        onClick={() => scrollTop()}
      >
        <i class='bklog-icon bklog-zhankai'></i>
      </span>
    );
    return {
      renderBody,
    };
  },
  render() {
    return this.renderBody();
  },
});
