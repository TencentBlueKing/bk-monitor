import { computed, onBeforeUnmount, ref, watch } from 'vue';
import $http from '@/api';
import useStore from '@/hooks/use-store';
import RouteUrlResolver, { RetrieveUrlResolver } from '@/store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';
import RetrieveHelper, { RetrieveEvent } from '../retrieve-helper';
import useScroll from '../../hooks/use-scroll';
import useResizeObserve from '../../hooks/use-resize-observe';

export default () => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();
  const searchBarHeight = ref(0);
  const leftFieldSettingWidth = ref(0);
  const favoriteWidth = ref(RetrieveHelper.favoriteWidth);
  const isFavoriteShown = ref(RetrieveHelper.isFavoriteShown);

  RetrieveHelper.setScrollSelector('.v3-bklog-root');

  RetrieveHelper.on(RetrieveEvent.SEARCHBAR_HEIGHT_CHANGE, height => {
    searchBarHeight.value = height;
  });

  RetrieveHelper.on(RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE, width => {
    leftFieldSettingWidth.value = width;
  });

  RetrieveHelper.on(RetrieveEvent.FAVORITE_WIDTH_CHANGE, width => {
    favoriteWidth.value = width;
  });

  RetrieveHelper.on(RetrieveEvent.FAVORITE_SHOWN_CHANGE, isShown => {
    isFavoriteShown.value = isShown;
  });

  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);
  const stickyStyle = computed(() => {
    return {
      '--top-searchbar-height': `${searchBarHeight.value}px`,
      '--left-field-setting-width': `${leftFieldSettingWidth.value}px`,
      '--left-collection-width': `${isFavoriteShown.value ? favoriteWidth.value : 0}px`,
    };
  });

  /**
   * 用于处理收藏夹宽度变化
   * 当收藏夹展开时，需要将内容宽度设置为减去收藏夹宽度
   */
  const contentStyle = computed(() => {
    if (isFavoriteShown.value) {
      return { width: `calc(100% - ${favoriteWidth.value}px)` };
    }

    return { width: '100%' };
  });

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

  /** 开始处理滚动容器滚动时，收藏夹高度 */

  // 顶部二级导航高度，这个高度是固定的
  const subBarHeight = ref(64);
  const paddingTop = ref(0);
  // 滚动容器高度
  const scrollContainerHeight = ref(0);

  useScroll(RetrieveHelper.getScrollSelector(), event => {
    const scrollTop = (event.target as HTMLElement).scrollTop;
    paddingTop.value = scrollTop > subBarHeight.value ? subBarHeight.value : scrollTop;
  });

  useResizeObserve(
    RetrieveHelper.getScrollSelector(),
    entry => {
      scrollContainerHeight.value = (entry.target as HTMLElement).offsetHeight;
    },
    0,
  );

  const isStickyTop = computed(() => {
    return paddingTop.value === subBarHeight.value;
  });

  /*** 结束计算 ***/

  onBeforeUnmount(() => {
    RetrieveHelper.destroy();
  });

  return {
    isStickyTop,
    stickyStyle,
    contentStyle,
    isFavoriteShown,
  };
};
