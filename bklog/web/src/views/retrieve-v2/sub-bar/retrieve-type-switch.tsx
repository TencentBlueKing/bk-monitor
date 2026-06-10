/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { computed, defineComponent } from 'vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import http from '@/api';
import { useRoute, useRouter } from 'vue-router/composables';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import { getAllSceneFieldOpKeys } from '../../retrieve-v3/search-bar/scene-filter/scene-config';
import { cancelPendingRetrieveRequests, resetRetrieveData } from '../../retrieve-v3/search-bar/scene-filter/scene-retrieve-utils';
import { SceneType } from '../../retrieve-v3/search-bar/scene-filter/types';
import { BK_LOG_STORAGE } from '@/store/store.type';
import './retrieve-type-switch.scss';

/* eslint-disable no-unused-vars */
export enum RetrieveType {
  Normal = 'normal',
  Scene = 'scene',
}

export default defineComponent({
  name: 'RetrieveTypeSwitch',
  setup() {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const isSceneMode = computed(() => store.getters.isSceneMode);
    const retrieveType = computed(() => (isSceneMode.value ? RetrieveType.Scene : RetrieveType.Normal));

    const sceneConfigs = computed(() => store.getters['retrieve/sceneConfigList']);

    const handleChange = (type: string) => {
      if (retrieveType.value === type) return;

      // 先取消所有进行中的请求，防止旧请求返回覆盖新数据
      cancelPendingRetrieveRequests();

      // 切换检索模式时，关闭常驻筛选面板
      store.commit('retrieve/updateCatchFieldCustomConfig', { fixedFilterAddition: false, filterAddition: [] });

      // 切换检索模式时，清空 keyword 和 addition
      store.commit('updateIndexItemParams', { keyword: '', addition: [] });
      store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: 0 });

      // 切换到常规检索时，清空场景化检索条件
      if (type === RetrieveType.Normal) {
        store.commit('updateIndexItemParams', {
          retrieve_type: type,
          scene_active: '',
          scene_filter_values: {},
        });

        // 清空检索数据后重新请求
        resetRetrieveData(store);
        store.dispatch('requestIndexSetFieldInfo').then((resp) => {
          RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);

          if (resp?.data?.fields?.length) {
            store.dispatch('requestIndexSetQuery');
          }

          if (!resp?.data?.fields?.length) {
            store.commit('updateIndexSetQueryResult', {
              is_error: true,
              exception_msg: 'index-set-field-not-found',
            });
          }
        });

        // 从 URL 中清除场景相关参数及 keyword/addition
        const cleanQuery: Record<string, any> = { ...route.query, retrieve_type: type };
        delete cleanQuery.scene_active;
        delete cleanQuery.keyword;
        delete cleanQuery.addition;
        for (const key of getAllSceneFieldOpKeys(sceneConfigs.value)) {
          delete cleanQuery[key];
        }
        router.replace({
          params: { ...route.params, indexId: store.state.indexId || undefined },
          query: cleanQuery,
        });
      } else {
        store.commit('updateIndexItemParams', {
          retrieve_type: type,
          scene_active: SceneType.Container,
        });

        // 清空检索数据
        resetRetrieveData(store);
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_CLEAR);

        // 获取场景化检索用户自定义配置
        http.request('retrieve/getSceneUserCustomConfig', {
          query: {
            bk_biz_id: store.state.bkBizId,
            scene_id: SceneType.Container,
          },
        }).then((res) => {
          store.commit('retrieve/updateCatchFieldCustomConfig', res.data);
        });

        router.replace({
          query: {
            ...route.query,
            retrieve_type: type,
            scene_active: SceneType.Container,
            keyword: undefined,
            addition: undefined,
          },
        });
      }

      // 切换检索模式时，需要重新获取收藏列表
      RetrieveHelper.fire(RetrieveEvent.FAVORITE_LIST_REFRESH);
    };

    return () => (
      <div class='retrieve-type-switch'>
        <div
          class={['switch-item', { 'is-active': retrieveType.value === RetrieveType.Normal }]}
          onClick={() => handleChange(RetrieveType.Normal)}
        >
          {t('常规检索')}
        </div>
        <div
          class={['switch-item', { 'is-active': retrieveType.value === RetrieveType.Scene }]}
          onClick={() => handleChange(RetrieveType.Scene)}
        >
          {t('场景化检索')}
        </div>
      </div>
    );
  },
});
