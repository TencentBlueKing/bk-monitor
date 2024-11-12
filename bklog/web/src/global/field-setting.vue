<template>
  <div>
    <div
      @click="handleOpenSidebar"
      class="field-setting-wrap"
    >
      <span class="bklog-icon bklog-setting"></span>{{ t('字段配置') }}
    </div>
    <bk-sideslider
      :is-show.sync="showSlider"
      :quick-close="true"
      :title="$t('字段配置')"
      :width="640"
      @hidden="handleCloseSlider"
    >
      <div slot="header">
        {{ t('字段配置') }}
        <bk-button
          v-if="!isEdit"
          class="mt10 fr"
          data-test-id="fieldSettingSlider_button_edit"
          theme="default"
          @click="handleEdit"
        >
          {{ $t('编辑') }}
        </bk-button>
      </div>
      <template #content>
        <div
          class="field-slider-content"
          v-bkloading="{ isLoading: sliderLoading }"
        >
          <bk-form
            v-if="!sliderLoading"
            ref="validateForm"
            class="field-setting-form"
            :class="!isEdit ? 'field-preview-form' : ''"
            :label-width="100"
            :model="formData"
            :rules="basicRules"
          >
            <div class="add-collection-title">{{ $t('基础信息') }}</div>
            <bk-form-item
              ext-cls="en-bk-form"
              :icon-offset="120"
              :label="$t('采集名')"
              :property="'collector_config_name'"
              :required="isEdit"
              :rules="basicRules.collector_config_name"
            >
              <bk-input
                v-if="isEdit"
                class="w520"
                v-model="formData.collector_config_name"
                maxlength="50"
                show-word-limit
              >
              </bk-input>
              <div v-else>
                {{ formData.collector_config_name }}
              </div>
            </bk-form-item>
            <bk-form-item
              ext-cls="en-bk-form"
              :icon-offset="120"
              :label="$t('数据名')"
              :property="'collector_config_name_en'"
              :required="isEdit"
              :rules="basicRules.collector_config_name_en"
            >
              <div class="en-name-box">
                <bk-input
                  v-if="isEdit"
                  class="w520"
                  v-model="formData.collector_config_name_en"
                  disabled
                  show-word-limit
                >
                </bk-input>
                <div v-else>{{ formData.collector_config_name_en }}</div>
              </div>
            </bk-form-item>
            <bk-form-item
              ext-cls="en-bk-form"
              :label="$t('数据ID')"
              :property="'bk_data_id'"
              :required="isEdit"
              :rules="basicRules.bk_data_id"
            >
              <bk-input
                v-if="isEdit"
                class="form-input"
                v-model="formData.bk_data_id"
                disabled
              >
              </bk-input>
              <div v-else>{{ formData.bk_data_id }}</div>
            </bk-form-item>
            <div class="add-collection-title">{{ $t('存储配置') }}</div>
            <bk-form-item
              ext-cls="en-bk-form"
              :label="$t('集群名称')"
              :property="'storage_cluster_id'"
              :required="isEdit"
              :rules="basicRules.storage_cluster_id"
            >
              <bk-select
                v-if="isEdit"
                v-model="formData.storage_cluster_id"
                :popover-min-width="160"
              >
                <bk-option
                  v-for="option in storageList"
                  :id="option.storage_cluster_id"
                  :key="option.storage_cluster_id"
                  :name="option.storage_cluster_name"
                >
                </bk-option>
              </bk-select>
              <div v-else>{{ formData.storage_cluster_name }}</div>
            </bk-form-item>
            <bk-form-item
              ext-cls="en-bk-form"
              :label="$t('日志保存天数')"
              :property="'retention'"
              :required="isEdit"
              :rules="basicRules.retention"
            >
              <bk-input
                v-if="isEdit"
                v-model="formData.retention"
              >
                <template slot="append">
                  <div>{{ $t('天') }}</div>
                </template>
              </bk-input>
              <div v-else>
                {{ formData.retention }}
              </div>
            </bk-form-item>
            <div class="add-collection-title">{{ $t('索引配置') }}</div>
            <div class="setting-title">{{ $t('原始日志配置') }}</div>
            <setting-table
              v-if="formData.etl_params.retain_original_text"
              ref="originfieldTable"
              :table-type="'originLog'"
              :is-preview-mode="!isEdit"
              :extract-method="cleanType"
              :fields="originBuiltFields"
            >
            </setting-table>
            <div
              v-else
              class="setting-desc"
            >
              {{ $t('暂未保留原始日志') }}
              <span
                class="field-add-btn"
                @click="batchAddField"
              >
                {{ $t('前往配置') }}<span class="bklog-icon bklog-jump"></span>
              </span>
            </div>

            <div class="setting-title">{{ $t('索引字段配置') }}</div>
            <setting-table
              ref="indexfieldTable"
              :table-type="'indexLog'"
              :is-preview-mode="!isEdit"
              :extract-method="cleanType"
              :fields="tableField"
              :collector-config-id="collectorConfigId"
              :built-fields="indexBuiltField"
            >
            </setting-table>
            <div
              v-if="isShowAddFields"
              class="add-field-container"
            >
              <div
                class="text-btn"
                @click="addNewField"
              >
                <i class="icon bk-icon icon-plus push"></i>
                <span class="text">{{ $t('新增字段') }}</span>
              </div>
            </div>
          </bk-form>
          <div class="submit-container">
            <bk-button
              v-if="isEdit"
              class="king-button mr10"
              :loading="confirmLoading"
              data-test-id="fieldSettingSlider_button_confirm"
              theme="primary"
              @click.stop.prevent="submit"
            >
              {{ $t('提交') }}
            </bk-button>
            <bk-button
              v-if="isEdit"
              data-test-id="fieldSettingSlider_button_cancel"
              @click="handleCancel"
              >{{ $t('取消') }}</bk-button
            >
          </div>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, nextTick } from 'vue';
  import useStore from '@/hooks/use-store';
  import useLocale from '@/hooks/use-locale';
  import { useRoute,useRouter } from 'vue-router/composables';
  import http from '@/api';
  import { deepClone } from '@/common/util';

  import settingTable from './setting-table.vue';
  import * as authorityMap from '../common/authority-map';

  const { t } = useLocale();
  const store = useStore();
  const route = useRoute();
  const router = useRouter();

  const showSlider = ref(false);
  const sliderLoading = ref(false);
  const isEdit = ref(false);
  const tableField = ref([]);
  const cleanType = ref('');
  const collectorConfigId = ref('');

  const formData = ref({
    data_link_id: '',
    bk_biz_id: '',
    collector_config_name: '',
    collector_config_name_en: '',
    bk_data_id: '',
    storage_cluster_name: '',
    storage_cluster_id: '',
    retention: '',
    etl_params: {
      retain_original_text: false,
      original_text_tokenize_on_chars: '',
      original_text_is_case_sensitive: '',
    },
    etl_config: '',
  });

  /** 添加字段的基础数据 */
  const baseFieldObj = ref({
    value: '',
    option: {
      time_zone: '',
      time_format: '',
    },
    is_time: false,
    verdict: false,
    is_delete: false,
    alias_name: '',
    field_name: '',
    field_type: '',
    description: '',
    is_case_sensitive: false,
    is_analyzed: false,
    is_built_in: false,
    is_dimension: false,
    previous_type: '',
    tokenize_on_chars: '',
    participleState: 'default',
    is_edit: true,
  });

  const maxRetention = ref(0);

  const basicRules = ref({
    collector_config_name: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
    collector_config_name_en: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
    bk_data_id: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
    storage_cluster_id: [
      {
        required: true,
        trigger: 'blur',
      },
    ],
    retention: [
      {
        required: true,
        trigger: 'blur',
      },
      {
        validator: () => {
          return formData.value.storage_cluster_id;
        },
        message: t('请先选择集群'),
        trigger: 'blur',
      },
      {
        validator: val => {
          if (val) {
            const currentStorageCluster = storageList.value.find(
              item => item.storage_cluster_id === formData.value.storage_cluster_id,
            );
            maxRetention.value = currentStorageCluster?.setup_config?.retention_days_max || 30;
            return val <= maxRetention.value;
          }
        },
        message: function () {
          return t(`超出集群最大可保存天数，当前最大可保存${maxRetention.value}天`);
        },
        trigger: 'blur',
      },
    ],
  });

  const isShowAddFields = computed(() => {
    return cleanType.value === 'bk_log_json';
  });

  const indexfieldTable = ref(null);
  const addNewField = () => {
    const fields = deepClone(tableField.value);
    const newBaseFieldObj = {
      ...baseFieldObj.value,
      field_index: tableField.value.length + 1,
    };
    // 获取table表格编辑的数据 新增新的字段对象
    tableField.value.splice(0, fields.length, ...[...indexfieldTable.value.getData(), newBaseFieldObj]);
  };

  const handleEdit = () => {
    isEdit.value = true;
  };

  const handleCancel = () => {
    isEdit.value = false;
  };

  const handleOpenSidebar = async () => {
    showSlider.value = true;
    sliderLoading.value = true;
    await initFormData();
    getStorage();
  };
  const originBuiltFields = ref([]);
  const indexBuiltField = ref([]);

  const initFormData = async () => {
    const indexSetList = store.state.retrieve.indexSetList;
    const indexSetId = route.params?.indexId;
    const currentIndexSet = indexSetList.find(item => item.index_set_id == indexSetId);
    if (!currentIndexSet.collector_config_id) return;
    collectorConfigId.value = currentIndexSet.collector_config_id;
    await http
      .request('collect/details', {
        params: {
          collector_config_id: currentIndexSet.collector_config_id,
        },
      })
      .then(res => {
        const collectData = res?.data || {};
        formData.value = collectData;
        cleanType.value = collectData?.etl_config;
        indexBuiltField.value = collectData?.fields.filter(item => item.is_built_in && item.field_name !== 'data');
        originBuiltFields.value = collectData?.fields?.filter(item => item.is_built_in && item.field_name === 'data');
      });

    await http
      .request('clean/getCleanStash', {
        params: {
          collector_config_id: currentIndexSet.collector_config_id,
        },
      })
      .then(res => {
        tableField.value = res?.data?.etl_fields.filter(item => !item.is_built_in && !item.is_delete);
      });
    sliderLoading.value = false;
  };

  const storageList = ref([]);
  const getStorage = async () => {
    try {
      const res = await http.request('collect/getStorage', {
        query: {
          bk_biz_id: formData.value.bk_biz_id,
          data_link_id: formData.value.data_link_id,
        },
      });
      if (res.data) {
        // 根据权限排序
        const s1 = [];
        const s2 = [];
        for (const item of res.data) {
          if (item.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH]) {
            s1.push(item);
          } else {
            s2.push(item);
          }
        }
        storageList.value = s1.concat(s2);
      }
    } catch (error) {
      console.log(error, 'error');
    }
  };

  const validateForm = ref(null);
  const confirmLoading = ref(false);
  // 字段表格校验
  const checkFieldsTable = () => {
    return formData.value.etl_config === 'bk_log_json' ? indexfieldTable.value.validateFieldTable() : [];
  };

  const originfieldTable = ref(null);

  const submit = () => {
    validateForm.value.validate().then(res => {
      if (res) {
        const promises = [];
        if (formData.value.etl_config === 'bk_log_json') {
          promises.splice(1, 0, ...checkFieldsTable());
        }
        Promise.all(promises).then(
          async () => {
            confirmLoading.value = true;

            const originfieldTableData = originfieldTable.value.getData();
            const data = {
              collector_config_name: formData.value.collector_config_name,
              storage_cluster_id: formData.value.storage_cluster_id,
              retention: formData.value.retention,
              etl_params: {
                ...formData.value.etl_params,
                original_text_is_case_sensitive: originfieldTableData?.length
                  ? originfieldTableData[0].is_case_sensitive
                  : '',
                original_text_tokenize_on_chars: originfieldTableData?.length
                  ? originfieldTableData[0].tokenize_on_chars
                  : '',
              },
              etl_config: formData.value.etl_config,
              fields: indexfieldTable.value.getData(),
            };
            await http
              .request('collect/fastUpdateCollection', {
                params: {
                  collector_config_id: collectorConfigId.value,
                },
                data,
              })
              .then(res => {
                if (res.code === 0) {
                  window.mainComponent.messageSuccess(t('保存成功'));
                  nextTick(() => {
                    showSlider.value = false;
                  });
                }
              })
              .finally(() => {
                confirmLoading.value = false;
              });
          },
          validator => {
            console.warn('保存失败', validator);
          },
        );
      }
    });
  };
  const batchAddField = () => {
    console.log(collectorConfigId.value, 'collectorConfigId');
        if (!collectorConfigId.value) return;
        router.replace({
          name: 'collectField',
          params: {
            collectorId: collectorConfigId.value,
          },
          query: {
            spaceUid: store.state.spaceUid,
          },
        });
  }
  // 关闭侧边栏后退出编辑模式
  const handleCloseSlider = () => {
    isEdit.value = false;
  }
</script>

<style lang="scss" scoped>
  .field-setting-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 108px;
    height: 32px;
    margin-left: 10px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;

    span {
      margin: 3px 6px 0 0;
    }
  }

  .field-slider-content {
    min-height: 394px;
    overflow-y: auto;

    .add-collection-title {
      width: 100%;
      padding-top: 18px;
      margin-bottom: 12px;
      font-size: 14px;
      font-weight: 700;
      color: #313238
    }

    .setting-title {
      padding-top: 10px;
      font-size: 12px;
      font-weight: 600;
      color: #63656e;
    }

    .setting-desc {
      padding: 10px 0;
      color: #EA3636;

      .field-add-btn{
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .field-setting-form {
      padding: 16px 36px 36px;

      .form-flex-container {
        display: flex;
        align-items: center;
        // height: 32px;
        font-size: 12px;
        color: #63656e;

        .icon-info {
          margin: 0 8px 0 24px;
          font-size: 14px;
          color: #3a84ff;
        }
      }

      .bk-form-item {
        margin-top: 18px;
      }

      .source-item {
        display: flex;
      }

      .add-field-container {
        display: flex;
        align-items: center;
        height: 40px;
        padding-left: 4px;
        border: 1px solid #dcdee5;
        border-top: none;
        border-bottom: 1.5px solid #dcdee5;
        border-radius: 0 0 2px 2px;
        transform: translateY(-1px);

        .text-btn {
          display: flex;
          align-items: center;
          cursor: pointer;

          .text,
          .icon {
            font-size: 22px;
            color: #3a84ff;
          }

          .text {
            font-size: 12px;
          }
        }
      }
    }

    .field-preview-form {
      .bk-form-item {
        margin-top: 0;
      }
    }

    .submit-container {
      padding: 16px 36px 36px;
    }
  }
</style>
