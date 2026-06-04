/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { computed, defineComponent, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router/composables';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import ContextLog from './index';
import { decodeContextRoutePayload, type IContextRetrieveParams } from './context-route';

export default defineComponent({
  name: 'ContextLogPage',
  setup() {
    const route = useRoute();
    const store = useStore();
    const { t } = useLocale();
    const ready = ref(false);

    const payload = computed(() => decodeContextRoutePayload(String(route.query.payload ?? '')));
    const normalizedPayload = computed(() => {
      const currentPayload = payload.value;
      if (!currentPayload) {
        return null;
      }

      const retrieveParams: IContextRetrieveParams = {
        addition: [],
        keyword: '*',
        search_mode: 'ui',
        ...(currentPayload.retrieveParams || {}),
      };

      return {
        ...currentPayload,
        retrieveParams,
        logParams: currentPayload.logParams || {},
        targetFields: currentPayload.targetFields || [],
        backRoute: currentPayload.backRoute || {},
      };
    });

    onMounted(async () => {
      if (!normalizedPayload.value) {
        ready.value = true;
        return;
      }

      const indexSetId = Number(normalizedPayload.value.indexSetId) || 0;
      if (!indexSetId) {
        ready.value = true;
        return;
      }

      try {
        store.commit('updateIndexItemParams', {
          ids: [indexSetId],
          start_time: normalizedPayload.value.retrieveParams?.start_time,
          end_time: normalizedPayload.value.retrieveParams?.end_time,
          format: normalizedPayload.value.retrieveParams?.format,
        });

        if (!store.state.indexFieldInfo.fields?.length) {
          await store.dispatch('requestIndexSetFieldInfo');
        }
      } finally {
        ready.value = true;
      }
    });

    return () => {
      if (!normalizedPayload.value) {
        return (
          <bk-exception
            style='margin-top: 120px'
            scene='part'
            type='empty'
          >
            <span>{t('暂无数据')}</span>
          </bk-exception>
        );
      }

      if (!ready.value) {
        return (
          <div
            style='height: 100vh'
            v-bkloading={{ isLoading: true, opacity: 0.4 }}
          />
        );
      }

      return (
        <ContextLog
          mode='page'
          isShow
          indexSetId={Number(normalizedPayload.value.indexSetId) || 0}
          logParams={normalizedPayload.value.logParams}
          retrieveParams={normalizedPayload.value.retrieveParams || {}}
          targetFields={normalizedPayload.value.targetFields}
          rowIndex={Number(normalizedPayload.value.rowIndex) || 0}
          backRoute={normalizedPayload.value.backRoute}
        />
      );
    };
  },
});
