import BklogPopover from '@/components/bklog-popover';
import { defineComponent } from 'vue';
import useContent from './use-content';

export default defineComponent({
  setup() {
    const { getContent } = useContent();

    return () => {
      <BklogPopover
        trigger='click'
        content={getContent}
      >
        Img-SpaceName
      </BklogPopover>;
    };
  },
});
