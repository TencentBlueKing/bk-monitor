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
import { deepEqual } from '@/common/util';

import { useOperation } from '../../hook/useOperation';
import BaseInfo from '../business-comp/step2/base-info';
import DragTag from '../common-comp/drag-tag';
import InfoTips from '../common-comp/info-tips';
import $http from '@/api';
import { showMessage } from '../../utils';
import type { ISubmitOptions } from '../../type';

import './step2-custom-report.scss';

export default defineComponent({
  name: 'StepCustomReport',
  props: {
    isEdit: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['next', 'prev', 'cancel', 'detail'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const { cardRender } = useOperation();
    const baseInfoRef = ref();
    const loading = ref(false);
    const submitLoading = ref(false);
    const bkBizId = computed(() => store.state.bkBizId);
    /**
     * 初始表单数据快照，用于对比是否有变更
     */
    const initialFormData = ref(null);
    /**
     * 保存初始表单数据快照
     */
    const saveInitialFormData = () => {
      initialFormData.value = structuredClone(configData.value);
    };
    /**
     * 判断配置是否有变更
     */
    const hasConfigChanged = () => {
      return !deepEqual(configData.value, initialFormData.value);
    };
    const configData = ref({
      collector_config_name_en: '',
      custom_type: 'log',
      retention: 7,
      allocation_min_days: 0,
      storage_replies: 1,
      description: '',
      es_shards: 3,
      parent_index_set_ids: [],
      target_fields: [],
      sort_fields: [],
      index_set_id: '',
    });
    /** 目标字段选择列表 */
    const targetFieldSelectList = ref<{ id: string; name: string }[]>([]);
    const targetFieldSelectMap = computed(() => new Set(targetFieldSelectList.value.map(item => item.id)));
    /**
     * 接口详情中的 target_fields 可能已经不在当前字段列表中。
     * 这里把已选但缺失的字段补充为临时 option，确保 select tag 可以展示并支持删除。
     */
    const targetFieldOptions = computed(() => {
      const options = [...targetFieldSelectList.value];
      const optionSet = new Set(options.map(item => item.id));

      for (const field of configData.value.target_fields || []) {
        if (field && !optionSet.has(field)) {
          optionSet.add(field);
          options.push({
            id: field,
            name: field,
          });
        }
      }

      return options;
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
        const { collector_config_name, index_set_id, target_fields, sort_fields } = res?.data;
        configData.value = {
          ...configData.value,
          ...res?.data,
          index_set_name: collector_config_name,
          target_fields: target_fields || [],
          sort_fields: sort_fields || [],
          index_set_id: index_set_id || '',
        };
        store.commit('collect/setCurCollect', res.data);
        // 保存初始表单数据快照
        saveInitialFormData();
        emit('detail', configData.value);
        // 编辑模式下初始化字段选择列表
        if (index_set_id) {
          initTargetFieldSelectList(index_set_id);
        }
      } else {
        const { retention } = configData.value;
        Object.assign(configData.value, {
          retention: retention ? `${retention}` : defaultRetention.value,
        });
      }
      isInitializing.value = false;
    };

    /**
     * 初始化字段选择列表
     * 通过 index_set_id 获取字段表头信息
     */
    const initTargetFieldSelectList = async (indexSetId: string | number) => {
      try {
        const res = await $http.request('retrieve/getLogTableHead', {
          params: {
            index_set_id: indexSetId,
          },
          query: {
            is_realtime: 'True',
          },
        });
        targetFieldSelectList.value = (res?.data?.fields || []).map(item => ({
          id: item.field_name,
          name: item.field_name,
        }));
      } catch (error) {
        console.log('初始化字段选择列表失败:', error);
        targetFieldSelectList.value = [];
      }
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

    /** 字段设置 */
    const renderFieldSetting = () => (
      <div class='field-setting-box'>
        <bk-alert
          class='field-setting-alert'
          title={t('未匹配到对应字段，请手动指定字段后提交。')}
          type='warning'
        />
        {/* 目标字段选择 */}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('目标字段')}</span>
          <div class='form-box'>
            <bk-select
              class='select-sort'
              clearable={false}
              value={configData.value.target_fields}
              collapse-tag
              display-tag
              multiple
              allow-create
              searchable
              on-selected={(value: string[]) => {
                configData.value.target_fields = value;
              }}
            >
              {targetFieldOptions.value.map(option => (
                <bk-option
                  class={{ 'is-missing-target-field': !targetFieldSelectMap.value.has(option.id) }}
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            <InfoTips
              class='block'
              tips={t('用于标识日志文件来源及唯一性')}
            />
          </div>
        </div>
        {/* 排序字段设置 */}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('排序字段')}</span>
          <div class='form-box'>
            <DragTag
              addType='select'
              selectList={targetFieldSelectList.value}
              value={configData.value.sort_fields}
              on-change={(value: string[]) => {
                configData.value.sort_fields = value;
              }}
            />
            <InfoTips
              class='block'
              tips={t('用于控制日志排序的字段')}
            />
          </div>
        </div>
      </div>
    );

    /**
     * 保存按钮
     * @param options 保存选项配置
     * @param options.action 操作类型: 'next'(默认) | 'back' | 'saveOnly'
     * @param options.callback 保存完成后的回调函数
     */
    const handleSubmitSave = async ({
      action = 'saveOnly',
      callback,
    }: ISubmitOptions = {}) => {
      // 表单校验
      try {
        await baseInfoRef.value?.validate();
      } catch {
        return;
      }

      submitLoading.value = true;

      const {
        collector_config_name,
        collector_config_name_en,
        index_set_name,
        bk_data_id,
        custom_type,
        retention,
        allocation_min_days,
        storage_replies,
        category_id,
        description,
        storage_cluster_id,
        es_shards,
        parent_index_set_ids,
        storage_cluster_type,
      } = configData.value as { [key: string]: unknown };

      const submitData = {
        bk_data_id,
        custom_type,
        storage_cluster_id,
        retention: Number(retention),
        allocation_min_days: Number(allocation_min_days),
        storage_replies: Number(storage_replies),
        category_id,
        description,
        es_shards: Number(es_shards),
        parent_index_set_ids,
        collector_config_name_en,
        collector_config_name: collector_config_name || index_set_name,
        bk_biz_id: Number(bkBizId.value),
        target_fields: configData.value.target_fields || [],
        sort_fields: configData.value.sort_fields || [],
      };

      // 根据 storage_cluster_type 判断是否需要移除字段
      if (storage_cluster_type === 'doris') {
        delete submitData.es_shards;
        delete submitData.storage_replies;
        delete submitData.allocation_min_days;
      }

      $http
        .request('custom/setCustom', {
          params: {
            collector_config_id: collectorId.value,
          },
          data: submitData,
        })
        .then((res) => {
          if (res.result) {
            showMessage(t('保存成功'));
            callback?.(true);
            if (action === 'saveOnly') {
              // 只保存，不跳转
              return;
            }
            emit('cancel');
          }
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };

    const cardConfig = computed(() => {
      const cards = [
        {
          title: t('基础信息'),
          key: 'baseInfo',
          renderFn: renderBaseInfo,
        },
      ];
      // 编辑模式下显示字段设置
      if (props.isEdit) {
        cards.push({
          title: t('字段设置'),
          key: 'fieldSetting',
          renderFn: renderFieldSetting,
        });
      }
      return cards;
    });

    expose({
      hasConfigChanged,
      handleSubmitSave,
    });

    return () => (
      <div
        class='operation-step2-custom-report'
        v-bkloading={{ isLoading: loading.value }}
      >
        {cardRender(cardConfig.value)}
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
            loading={submitLoading.value}
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
          {props.isEdit && (
            <bk-button
              class='width-88 mr-8'
              theme='primary'
              loading={submitLoading.value}
              on-click={() => {
                handleSubmitSave({ action: 'back' });
              }}
            >
              {t('提交')}
            </bk-button>
          )}
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
