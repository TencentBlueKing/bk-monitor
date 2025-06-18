import { defineComponent, ref, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router/composables';
import useStore from '@/hooks/use-store';
import http from '@/api/index';
import './share.scss';
import { messageError } from '@/common/bkmagic';

export default defineComponent({
  setup() {
    const router = useRouter();
    const route = useRoute();
    const store = useStore();

    const linkId = route.params.linkId as string;

    if (!linkId) {
      router.push({ name: 'retrieve' });
      return;
    }

    const getLinkParams = () => {
      http.request('retrieve/getShareParams', { query: { token: linkId } }).then(resp => {
        if (resp.result) {
          const data = resp.data.data;
          const { storage, indexItem, catchFieldCustomConfig } = data.store;
          store.commit('updateStorage', storage);
          store.commit('updateIndexItem', indexItem);
          store.commit('retrieve/updateCatchFieldCustomConfig', catchFieldCustomConfig);
          router.push({ ...data.route });
          return;
        }

        messageError(resp.message || '获取分享链接参数失败，请稍后重试！');
      });
    };

    onMounted(() => {
      getLinkParams();
    });

    return () => (
      <div class='analysis-animation-container'>
        <bk-exception
          type='search-empty'
          style={{
            marginTop: '20px',
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
            top: '0',
          }}
          scene='part'
        >
          {'正在解析地址, 请稍候 ...'}
        </bk-exception>
      </div>
    );
  },
});
