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

import { defineComponent, ref, reactive, watch, computed, onMounted, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import type { IContainerConfigItem } from '../../../../type';
import $http from '@/api';
import './workload-selection.scss';

export default defineComponent({
  name: 'WorkloadSelection',
  props: {
    conItem: {
      type: Object as PropType<IContainerConfigItem>,
      required: true,
    },
    container: {
      type: Object as PropType<IContainerConfigItem['container']>,
      required: true,
    },
    bcsClusterId: {
      type: String,
      required: true,
    },
  },
  emits: ['update'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const formData = reactive({
      workload_type: '',
      workload_name: '',
      container_name: '',
    });
    const nameListLoading = ref(false);
    const typeList = ref<IContainerConfigItem['typeList']>([]);

    const timer = ref(null);
    const isOptionOpen = ref(false);
    const nameCannotClick = ref(false);
    const nameList = ref<Array<{ id: string; name: string }>>([]);
    // const placeHolderStr = ref(`${t('请输入应用名称')}, ${t('支持正则匹配')}`);

    const bkBizId = computed(() => store.getters.bkBizId);

    const typeListIDStrList = computed(() => typeList.value.map(item => item.id));

    // 初始化表单数据
    Object.assign(formData, props.container);

    onMounted(() => {
      getWorkLoadTypeList();
    });

    // 监听工作负载类型变化
    watch(
      () => formData.workload_type,
      (val: string) => {
        if (val) {
          getWorkLoadNameList();
        } else {
          nameList.value = [];
        }
      },
    );

    // 监听命名空间变化
    watch(
      () => props.conItem.noQuestParams.namespaceStr,
      (str: string) => {
        if (str) {
          if (timer.value) {
            clearTimeout(timer.value);
          }
          timer.value = setTimeout(() => {
            getWorkLoadNameList();
          }, 1000);
        }
      },
      { immediate: true },
    );

    // 监听表单数据变化，同步到父组件
    watch(
      formData,
      val => {
        emit('update', val);
      },
      { deep: true },
    );

    // 获取工作负载类型列表
    const getWorkLoadTypeList = async () => {
      try {
        const res = await $http.request('container/getWorkLoadType');
        if (res.code === 0) {
          typeList.value = res.data.map((item: string) => ({ id: item, name: item }));
        }
      } catch (err) {
        console.log(err);
      }
    };

    // 获取工作负载名称列表
    const getWorkLoadNameList = () => {
      if (!typeListIDStrList.value.includes(formData.workload_type)) {
        return;
      }
      nameListLoading.value = true;

      nameCannotClick.value = true;
      const query = {
        type: formData.workload_type,
        bk_biz_id: bkBizId.value,
        namespace: props.conItem.noQuestParams.namespaceStr,
        bcs_cluster_id: props.bcsClusterId,
      };

      $http
        .request('container/getWorkLoadName', { query })
        .then(res => {
          if (res.code === 0) {
            nameList.value = res.data.map(item => ({ id: item, name: item }));
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          nameCannotClick.value = false;
          nameListLoading.value = false;
        });
    };

    return () => (
      <div class='workload-selection-box'>
        <div class='flex-space-box'>
          <span class='space-item-label'>{t('应用类型')}</span>
          <bk-select
            ref='typeSelectRef'
            class='workload-type-select'
            value={formData.workload_type}
            clearable
            searchable
            on-selected={(val: string) => {
              formData.workload_type = val;
            }}
          >
            {typeList.value.map((option, index) => (
              <bk-option
                id={option.id}
                key={index}
                class='space-type-select'
                name={option.name}
              />
            ))}
          </bk-select>
        </div>

        <div class='flex-space-item'>
          <span class='space-item-label'>{t('应用名称')}</span>
          <bk-select
            ref='loadSelectRef'
            class={[
              'workload-name-select',
              formData.workload_name ? 'application' : '',
              nameCannotClick.value ? 'no-click' : '',
            ].join(' ')}
            loading={nameListLoading.value}
            // placeholder={placeHolderStr.value}
            value={formData.workload_name}
            searchable
            on-selected={(val: string) => {
              formData.workload_name = val;
            }}
            onToggle={(status: boolean) => {
              isOptionOpen.value = status;
            }}
          >
            {nameList.value.map((option, index) => (
              <bk-option
                id={option.id}
                key={`${option.name}_${index}`}
                name={option.name}
              />
            ))}
          </bk-select>
          {/* <span class={['bk-icon', 'icon-angle-down', isOptionOpen.value ? 'angle-rotate' : ''].join(' ')} /> */}
        </div>
      </div>
    );
  },
});
