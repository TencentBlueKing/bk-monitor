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

import { defineComponent, ref, computed, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';
import { useRoute } from 'vue-router/composables';
import useStore from '@/hooks/use-store';

import { useOperation } from '../../hook/useOperation';
import BaseInfo from '../business-comp/step2/base-info';
import $http from '@/api';

import './step2-custom-report.scss';

export default defineComponent({
  name: 'StepCustomReport',
  props: {
    isEdit: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const { cardRender } = useOperation();
    const baseInfoRef = ref();
    const loading = ref(false);
    const configData = ref({
      collector_config_name_en: '',
      custom_type: 'log',
      retention: 7,
      allocation_min_days: 0,
      storage_replies: 1,
      description: '',
      es_shards: 3,
      parent_index_set_ids: [],
    });
    const globalsData = computed(() => store.getters['globals/globalsData']);
    /**
     * 当前采集id
     */
    const collectorId = computed(() => route.params.collectorId);
    const defaultRetention = computed(() => {
      const { storage_duration_time } = globalsData.value;

      return storage_duration_time?.filter(item => item.default === true)[0].id;
    });

    // 防止重复调用的标志
    const isInitializing = ref(false);

    onMounted(() => {
      // this.containerLoading = true;
      initFormData();
    });
    const initFormData = async () => {
      console.log(' isInitializing.value', isInitializing.value);
      // 防止重复调用：如果正在初始化，直接返回
      if (isInitializing.value) {
        return;
      }
      isInitializing.value = true;
      if (props.isEdit) {
        loading.value = true;
        const res = await $http.request('collect/details', {
          params: {
            collector_config_id: collectorId.value,
          },
        });
        loading.value = false;
        const { collector_config_name } = res?.data;
        configData.value = {
          ...configData.value,
          ...res?.data,
          index_set_name: collector_config_name,
        };
        store.commit('collect/setCurCollect', res.data);
      } else {
        const { retention } = configData.value;
        Object.assign(configData.value, {
          retention: retention ? `${retention}` : defaultRetention.value,
        });
      }
      isInitializing.value = false;
    };

    /** 基本信息 */
    const renderBaseInfo = () => (
      <BaseInfo
        ref={baseInfoRef}
        data={configData.value}
        typeKey='custom'
        isEdit={props.isEdit}
        on-change={data => {
          configData.value = { ...configData.value, ...data };
        }}
      />
    );

    const cardConfig = [
      {
        title: t('基础信息'),
        key: 'baseInfo',
        renderFn: renderBaseInfo,
      },
    ];
    return () => (
      <div
        class='operation-step2-custom-report'
        v-bkloading={{ isLoading: loading.value }}
      >
        {cardRender(cardConfig)}
        <div class='classify-btns'>
          {!props.isEdit && (
            <bk-button
              class='mr-8'
              on-click={() => {
                emit('prev');
              }}
            >
              {t('上一步')}
            </bk-button>
          )}
          <bk-button
            class='width-88 mr-8'
            theme='primary'
            on-click={() => {
              baseInfoRef.value
                .validate()
                .then(() => {
                  console.log('configData.value', configData.value);
                  emit('next', configData.value);
                })
                .catch(() => {
                  console.log('error');
                });
            }}
          >
            {t('下一步')}
          </bk-button>
          <bk-button
            on-click={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
