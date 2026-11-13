import { defineComponent, toRef } from 'vue';
import { useSkeletonPresence } from './presence';
import './presence.scss';

export default defineComponent({
  name: 'NavigationSkeleton',
  props: { loading: Boolean, count: { type: Number, default: 1 } },
  setup(props) {
    const { visible, leaving } = useSkeletonPresence(toRef(props, 'loading'));
    return () => visible.value ? <div class={['bklog-navigation-skeleton bklog-skeleton-presence', { 'is-leaving': leaving.value }]}
      role='status' aria-label='Loading'>
      {Array.from({ length: props.count }, (_, index) => <span key={index} />)}
    </div> : null;
  },
});
