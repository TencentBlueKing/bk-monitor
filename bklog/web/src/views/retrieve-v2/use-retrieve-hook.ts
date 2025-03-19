import RouteUrlResolver, { RetrieveUrlResolver } from '../../store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import { ConsitionItem } from '../../store/condition-operator';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const resolveQueryParams = ({ search_mode, addition, keyword }) => {
    // 此时说明来自旧版URL，同时带有 addition 和 keyword
    // 这种情况下需要将 addition 转换为 keyword 进行查询合并
    // 同时设置 search_mode 为 sql
    if (!search_mode && addition?.length > 4 && keyword?.length > 0) {
      // 这里不好做同步请求，所以直接设置 search_mode 为 sql
      router.push({ query: { ...route.query, search_mode: 'sql', addition: '[]' } });
      const resolver = new RouteUrlResolver({ route, resolveFieldList: ['addition'] });
      const target = resolver.convertQueryToStore<{ addition: ConsitionItem[] }>();

      if (target.addition?.length) {
        return $http
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
              return true;
            }

            return false;
          });
      }
    }

    return Promise.resolve(true);
  };

  const resolveCommonParams = ({ search_mode, addition, keyword }) => {
    if (!search_mode) {
      if (keyword?.length > 0 && addition.length < 4) {
        store.commit('updateIndexItemParams', { keyword, search_mode: 'sql' });
        router.replace({ query: { ...route.query, keyword, addition: [] } });
        return;
      }

      if (addition?.length >= 4 && keyword?.length === 0) {
        store.commit('updateIndexItemParams', { addition, search_mode: 'ui' });

        const resolver = new RetrieveUrlResolver({
          addition,
          search_mode: 'ui',
          keyword: '',
        });

        const query = route.query;
        Object.assign(query, resolver.resolveParamsToUrl());

        router.replace({ query });
        return;
      }
    }
  };

  return { resolveQueryParams, resolveCommonParams };
};
