import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import { useI18n } from 'vue-i18n';

import type { IRumTimelineFoldVM } from '../../typings';

import './timeline-fold-row.scss';

/** 子级折叠行相对父级的缩进，与 Span 行的类型标签缩进对齐 */
const LEVEL_INDENT = 16;

/** 被折叠的一段连续同级 Span，点击整行展开 */
export default defineComponent({
  name: 'TimelineFoldRow',
  props: {
    data: {
      type: Object as PropType<IRumTimelineFoldVM>,
      required: true,
    },
  },
  emits: {
    expand: (_key: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    return () => (
      <div
        style={{ paddingLeft: `${8 + props.data.level * LEVEL_INDENT}px` }}
        class='timeline-fold-row'
        onClick={() => emit('expand', props.data.key)}
      >
        <i18n-t
          class='fold-text'
          keypath='已折叠 {0} 个 Span，{1}'
          tag='span'
        >
          <span class='fold-count'>{props.data.count}</span>
          <span class='fold-action'>{t('点击展开')}</span>
        </i18n-t>
        <i class='icon-monitor icon-double-down fold-icon' />
      </div>
    );
  },
});
