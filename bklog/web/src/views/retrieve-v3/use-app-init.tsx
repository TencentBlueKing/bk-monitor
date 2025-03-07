import { computed, ref, watch } from 'vue';
import $http from '@/api';
import useStore from '@/hooks/use-store';
import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);

  const { search_mode, addition, keyword } = route.query;

  // 此时说明来自旧版URL，同时带有 addition 和 keyword
  // 这种情况下需要将 addition 转换为 keyword 进行查询合并
  // 同时设置 search_mode 为 sql
  if (!search_mode && addition?.length > 4 && keyword?.length > 0) {
    // 这里不好做同步请求，所以直接设置 search_mode 为 sql
    router.push({ query: { ...route.query, search_mode: 'sql', addition: '[]' } });
    const resolver = new RouteUrlResolver({ route, resolveFieldList: ['addition'] });
    const target = resolver.convertQueryToStore();

    if (target.addition?.length) {
      $http
        .request('retrieve/generateQueryString', {
          data: {
            addition: target.addition,
          },
        })
        .then(res => {
          if (res.result) {
            const newKeyword = `${keyword} AND ${res.data?.querystring}`;
            router.replace({ query: { ...route.query, keyword: newKeyword, addition: [] } });
            store.commit('updateIndexItemParams', { keyword: newKeyword });
          }
        })
        .catch(err => {
          console.log(err);
        });
    }
  }

  // 解析默认URL为前端参数
  // 这里逻辑不要动，不做解析会导致后续前端查询相关参数的混乱
  store.dispatch('updateIndexItemByRoute', { route, list: [] });

  const setDefaultIndexsetId = () => {
    if (!route.params.indexId) {
      const routeParams = store.getters.retrieveParams;

      const resolver = new RetrieveUrlResolver({
        ...routeParams,
        datePickerValue: store.state.indexItem.datePickerValue,
      });

      if (store.getters.isUnionSearch) {
        router.replace({ query: { ...route.query, ...resolver.resolveParamsToUrl() } });
        return;
      }

      if (store.state.indexId) {
        router.replace({
          params: { indexId: store.state.indexId },
          query: {
            ...route.query,
            ...resolver.resolveParamsToUrl(),
          },
        });
      }
    }
  };

  /**
   * 拉取索引集列表
   */
  const getIndexSetList = () => {
    store.dispatch('retrieve/getIndexSetList', { spaceUid: spaceUid.value, bkBizId: bkBizId.value }).then(resp => {
      // 拉取完毕根据当前路由参数回填默认选中索引集
      store.dispatch('updateIndexItemByRoute', { route, list: resp[1] }).then(() => {
        setDefaultIndexsetId();
        store.dispatch('requestIndexSetFieldInfo').then(() => {
          store.dispatch('requestIndexSetQuery');
        });
      });
    });
  };

  const handleSpaceIdChange = () => {
    store.commit('resetIndexsetItemParams');
    store.commit('updateIndexId', '');
    store.commit('updateUnionIndexList', []);
    getIndexSetList();
    store.dispatch('requestFavoriteList');
  };

  handleSpaceIdChange();

  watch(spaceUid, () => {
    handleSpaceIdChange();
    const routeQuery = route.query ?? {};

    if (routeQuery.spaceUid !== spaceUid.value) {
      const resolver = new RouteUrlResolver({ route });

      router.replace({
        params: {
          indexId: undefined,
        },
        query: {
          ...resolver.getDefUrlQuery(),
          spaceUid: spaceUid.value,
          bizId: bkBizId.value,
        },
      });
    }
  });
};
