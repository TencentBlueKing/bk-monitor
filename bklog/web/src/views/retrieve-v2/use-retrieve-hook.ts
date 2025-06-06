import RouteUrlResolver, { RetrieveUrlResolver } from '../../store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import { ConsitionItem } from '../../store/store.type';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  /**
   * 用于处理
   * @param { search_mode, addition, keyword }
   * @param ignoreKeywodLength 是否忽略 keyword 长度，如果忽略，则不进行 keyword 的长度校验, 默认为 false
   * @returns
   */
  const resolveQueryParams = ({ search_mode, addition, keyword }, ignoreKeywodLength = false) => {
    // 此时说明来自旧版URL，同时带有 addition 和 keyword
    // 这种情况下需要将 addition 转换为 keyword 进行查询合并
    // 同时设置 search_mode 为 sql
    if (!search_mode && addition?.length > 0 && (ignoreKeywodLength || keyword?.length > 0)) {
      // 这里不好做同步请求，所以直接设置 search_mode 为 sql
      router.push({ query: { ...route.query, search_mode: 'sql', addition: '[]' } });
      const resolver = new RouteUrlResolver({ route, resolveFieldList: ['addition'] });
      const target = Array.isArray(addition)
        ? { addition }
        : resolver.convertQueryToStore<{ addition: ConsitionItem[] }>();

      if (target.addition?.length) {
        return $http
          .request('retrieve/generateQueryString', {
            data: {
              addition: target.addition,
            },
          })
          .then(res => {
            if (res.result) {
              let newKeyword = [keyword, res.data?.querystring]
                .filter(item => item.length > 0 && item !== '*')
                .join(' AND ');
              if (newKeyword.length === 0) {
                newKeyword = '*';
              }

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
