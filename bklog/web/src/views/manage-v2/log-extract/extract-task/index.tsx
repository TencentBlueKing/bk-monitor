import { defineComponent, ref, computed, watch, onMounted } from 'vue';
import useStore from '@/hooks/use-store';
import useRouter from '@/hooks/use-router';
import useRoute from '@/hooks/use-route';

import './index.scss';

export default defineComponent({
  name: 'Extract',
  setup() {
    const store = useStore();
    const router = useRouter();
    const route = useRoute();

    const isRender = ref(true);
    const isLoading = ref(false);

    const bkBizId = computed(() => store.state.bkBizId);

    watch(bkBizId, () => {
      isLoading.value = true;
      isRender.value = false;
      setTimeout(() => {
        isRender.value = true;
        if (route.query.create) {
          isLoading.value = false;
        }
      }, 400);
    });

    onMounted(() => {
      const bkBizId = store.state.bkBizId;
      const spaceUid = store.state.spaceUid;

      router.replace({
        query: {
          bizId: bkBizId,
          spaceUid: spaceUid,
          ...route.query,
        },
      });
    });

    return () => (
      <div
        class="log-extract-container"
        v-bkloading={{ isLoading: isLoading.value }}
      >
        <router-view></router-view>
      </div>
    );
  },
});
