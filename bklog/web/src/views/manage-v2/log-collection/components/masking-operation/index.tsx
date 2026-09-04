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

import { computed, defineComponent, onMounted, ref } from 'vue';

import $http from '@/api';
import MaskingField from '@/components/log-masking/masking-field';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';

import './index.scss';

type IndexSetId = number | string;

interface IMaskingCollectData {
  index_set_id?: IndexSetId;
  [key: string]: unknown;
}

export default defineComponent({
  name: 'V2MaskingOperation',

  setup() {
    const { t } = useLocale();
    const route = useRoute();
    const router = useRouter();
    const store = useStore();
    const maskingFieldRef = ref<any>(null);
    const loading = ref(false);
    const submitLoading = ref(false);
    const collectData = ref<IMaskingCollectData>({
      index_set_id: route.params.indexSetId || route.params.collectorId,
    });

    const typeKey = computed(() => String(route.query.typeKey || ''));
    const isCollectMaskingRoute = computed(() => route.name === 'collectMasking');
    const useIndexSetParam = computed(() => {
      return !isCollectMaskingRoute.value || ['bkdata', 'es'].includes(typeKey.value);
    });
    const isCollectMasking = computed(() => {
      return isCollectMaskingRoute.value && !['bkdata', 'es', 'custom_report'].includes(typeKey.value);
    });
    const isHiddenSyncNum = computed(() => {
      return (
        ['bkdata-index-set-masking', 'es-index-set-masking'].includes(String(route.name))
        || ['bkdata', 'es'].includes(typeKey.value)
      );
    });

    const goBack = () => {
      const { backRoute, ...query } = route.query;
      if (backRoute) {
        router.push({
          name: String(backRoute),
          query: {
            ...query,
            spaceUid: store.state.spaceUid,
          },
        });
        return;
      }
      router.go(-1);
    };

    const setIndexSetData = () => {
      collectData.value = {
        index_set_id: route.params.indexSetId || route.params.collectorId,
      };
    };

    const setCollectData = async () => {
      const collectorId = route.params.collectorId;
      if (!collectorId) {
        setIndexSetData();
        return;
      }

      loading.value = true;
      try {
        const res = await $http.request('collect/details', {
          params: { collector_config_id: collectorId },
        });
        collectData.value = res?.data || collectData.value;
        store.commit('collect/setCurCollect', collectData.value);
      } catch (err) {
        console.log('获取采集配置详情失败:', err);
      } finally {
        loading.value = false;
      }
    };

    const initData = async () => {
      if (!store.getters.isShowMaskingTemplate) {
        router.replace({ name: 'retrieve' });
        return;
      }

      if (useIndexSetParam.value) {
        setIndexSetData();
        return;
      }

      await setCollectData();
    };

    const submitSelectRule = async (stepChange = false) => {
      const data = maskingFieldRef.value?.getQueryConfigParams?.();
      const isUpdate = maskingFieldRef.value?.isUpdate;
      if (!(data?.field_configs?.length || isUpdate)) {
        goBack();
        return;
      }

      let requestStr = isUpdate ? 'updateDesensitizeConfig' : 'createDesensitizeConfig';
      if (!data.field_configs.length && isUpdate) {
        requestStr = 'deleteDesensitizeConfig';
      }

      try {
        submitLoading.value = true;
        const res = await $http.request(`masking/${requestStr}`, {
          params: { index_set_id: collectData.value?.index_set_id },
          data,
        });
        if (res.result && stepChange) {
          window.mainComponent.$bkMessage({
            theme: 'success',
            message: t('操作成功'),
          });
          goBack();
        }
      } catch (err) {
        console.log('保存脱敏配置失败:', err);
      } finally {
        submitLoading.value = false;
      }
    };

    onMounted(initData);

    return () => (
      <div
        class='v2-masking-operation'
        v-bkloading={{ isLoading: loading.value }}
      >
        <div class='masking-field-box'>
          <MaskingField
            ref={maskingFieldRef}
            collect-data={collectData.value}
            is-hidden-sync-num={isHiddenSyncNum.value}
            is-index-set-masking={isCollectMasking.value}
            onChangeData={() => submitSelectRule()}
          />
        </div>
        <div class='submit-content'>
          <bk-button
            loading={submitLoading.value}
            theme='primary'
            onClick={() => submitSelectRule(true)}
          >
            {t('应用')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={goBack}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
