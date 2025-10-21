<template>
  <div @click="hideSingleConfigInput">
    <div
      class="bklog-v3 field-setting-wrap"
      @click="handleOpenSidebar"
    >
      <span class="bklog-icon bklog-setting" v-bk-tooltips.top="t('索引配置')"></span> 
      <span class='field-settin-text'>{{ t('索引配置') }}</span>
    </div>
    <bk-sideslider
      :is-show.sync="showSlider"
      :quick-close="true"
      :title="$t('索引配置')"
      :transfer="true"
      :width="800"
      @animation-end="closeSlider"
    >
      <template #header>
        <div>
          {{ t('索引配置') }}
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
      </template>
      <template #content>
        <div
          class="bklog-v3 field-slider-content"
          v-bkloading="{ isLoading: sliderLoading }"
        >
          <bk-form
            v-if="!sliderLoading"
            ref="validateForm"
            class="field-setting-form"
            :class="!isEdit ? 'field-preview-form' : ''"
            :label-width="labelWidth"
            :model="formData"
            :rules="basicRules"
          >
            <div class="add-collection-title">{{ $t('基础信息') }}</div>
            <bk-form-item
              ext-cls="en-bk-form"
              :icon-offset="120"
              :label="formLableFormatter($t('采集名'))"
              :property="'collector_config_name'"
              :required="isEdit || isEditConfigName"
              :rules="basicRules.collector_config_name"
            >
              <div @click.stop="() => ({})">
                <bk-input
                  v-if="isEdit || isEditConfigName"
                  class="w520"
                  v-model="formData.collector_config_name"
                  maxlength="50"
                  show-word-limit
                >
                </bk-input>
                <div v-else>
                  {{ formData.collector_config_name }}
                  <!-- <i
                    :class="['bk-icon icon-edit-line icons']"
                    @click="isEditConfigName = true"
                  ></i> -->
                </div>
              </div>
            </bk-form-item>
            <bk-form-item
              ext-cls="en-bk-form"
              :icon-offset="120"
              :label="formLableFormatter($t('数据名'))"
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
              :label="formLableFormatter($t('数据ID'))"
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
              :label="formLableFormatter($t('集群名称'))"
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
              :label="formLableFormatter($t('日志保存天数'))"
              :property="'retention'"
              :required="isEdit || isEditRetention"
              :rules="basicRules.retention"
            >
              <div @click.stop="() => ({})">
                <bk-input
                  v-if="isEdit || isEditRetention"
                  v-model="formData.retention"
                >
                  <template #append>
                    <div
                      style="
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 40px;
                        height: 100%;
                        font-size: 12px;
                        background-color: #f2f4f8;
                      "
                    >
                      {{ $t('天') }}
                    </div>
                  </template>
                </bk-input>
                <div v-else>
                  {{ formData.retention }}
                  <!-- <i
                    :class="['bk-icon icon-edit-line icons']"
                    @click="isEditRetention = true"
                  ></i> -->
                </div>
              </div>
            </bk-form-item>
            <div class="add-collection-title">{{ $t('索引配置') }}</div>
            <div class="setting-title">{{ $t('原始日志配置') }}</div>
            <setting-table
              v-if="isOriginTableSaved"
              ref="originfieldTable"
              :extract-method="cleanType"
              :fields="originBuiltFields"
              :is-preview-mode="!isEdit"
              :original-text-tokenize-on-chars="defaultParticipleStr"
              :table-type="'originLog'"
            >
            </setting-table>
            <div
              v-else
              class="setting-desc"
              @click="batchAddField"
            >
              {{ $t('暂未保留原始日志') }}<span style="margin-left: 8px; color: #3a84ff">{{ $t('前往配置') }}</span
              ><span
                style="color: #3a84ff"
                class="bklog-icon bklog-jump"
              ></span>
            </div>

            <div class="setting-title">{{ $t('索引字段配置') }}</div>
            <setting-table
              ref="indexfieldTable"
              :built-fields="indexBuiltField"
              :collector-config-id="collectorConfigId"
              :extract-method="cleanType"
              :fields="tableField"
              :is-preview-mode="!isEdit"
              :original-text-tokenize-on-chars="defaultParticipleStr"
              :table-type="'indexLog'"
            >
            </setting-table>
            <div
              v-if="isShowAddFields && isEdit"
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

  import { builtInInitHiddenList } from '@/const/index.js';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { useRoute, useRouter } from 'vue-router/composables';

  import * as authorityMap from '../common/authority-map';
  import settingTable from './setting-table.vue';
  import http from '@/api';
  import { RetrieveEvent } from '@/views/retrieve-helper'
  import useRetrieveEvent from '@/hooks/use-retrieve-event';

  const { t } = useLocale();
  const store = useStore();
  const route = useRoute();
  const router = useRouter();
  const showSlider = ref(false);
  const sliderLoading = ref(false);

  const tableField = ref([]);
  const cleanType = ref('');
  const collectorConfigId = ref('');
  const defaultParticipleStr = ref('@&()=\'",;:<>[]{}/ \\n\\t\\r\\\\');

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
      path_regexp: '',
      metadata_fields: [],
    },
    etl_config: '',
    fields: [],
  });
  const formDataCopy = ref({});
  const fieldsCopy = ref([]);
  const isEdit = ref(false);
  const isEditConfigName = ref(false);
  const isEditRetention = ref(false);

  const hideSingleConfigInput = () => {
    isEditConfigName.value = false;
    isEditRetention.value = false;
  };
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
  const batchAddField = () => {
    if (!collectorConfigId.value) return;
    // router.replace({
    //   name: 'clean-edit',
    //   params: {
    //     collectorId: collectorConfigId.value,
    //   },
    //   query: {
    //     spaceUid: store.state.spaceUid,
    //   },
    // });
    const newURL = router.resolve({
      name: 'clean-edit',
      params: {
        collectorId: collectorConfigId.value,
      },
      query: {
        spaceUid: store.state.spaceUid,
      },
    });
    window.open(newURL.href, '_blank');
  };
  const maxRetention = ref(0);

  const basicRules = ref({
    collector_config_name: [
      {
        required: true,
        trigger: 'blur',
        validator: val => {
          if (val) {
            isEditConfigName.value = false;
          }
          return val;
        },
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
            if (val <= maxRetention.value) {
              isEditRetention.value = false;
            }
            return val <= maxRetention.value;
          }
        },
        message: function () {
          return t(`超出集群最大可保存天数，当前最大可保存{n}天`, { n: maxRetention.value });
        },
        trigger: 'blur',
      },
    ],
  });

  const isShowAddFields = computed(() => {
    return cleanType.value === 'bk_log_json';
  });
  const labelWidth = computed(() => {
      return store.state.isEnLanguage ?  130 : 94;
    });
  const indexfieldTable = ref(null);
  const addNewField = () => {
    const fields = structuredClone(indexfieldTable.value.getData());
    const newBaseFieldObj = {
      ...baseFieldObj.value,
      field_index: tableField.value.length + 1,
    };
    // 获取table表格编辑的数据 新增新的字段对象
    tableField.value.splice(0, fields.length, ...[...indexfieldTable.value.getData(), newBaseFieldObj]);
  };

  const { addEvent } = useRetrieveEvent();
  addEvent(RetrieveEvent.INDEX_CONFIG_OPEN, () => {
    hideSingleConfigInput();
    handleOpenSidebar();
    nextTick(() => {
      handleEdit()
    });
  });
  
  function formLableFormatter(label) {
    return `${label} :`;
  }

  const handleEdit = () => {
    formDataCopy.value = structuredClone(formData.value);
    fieldsCopy.value = structuredClone(indexfieldTable.value.getData());
    isEdit.value = true;
  };

  const handleCancel = async() => {
    formData.value = structuredClone(formDataCopy.value);
    tableField.value = structuredClone(fieldsCopy.value);
    nextTick(() => {
      isEdit.value = false;
    });
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
    const indexSetList = store.state.retrieve.flatIndexSetList;
    const indexSetId = route.params?.indexId;
    const currentIndexSet = indexSetList.find(item => item.index_set_id === `${indexSetId}`);
    if (!currentIndexSet?.collector_config_id) return;
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
        indexBuiltField.value = collectData?.fields.filter(
          item =>
            builtInInitHiddenList.includes(item.field_name) ||
            (builtInInitHiddenList.includes(item.alias_name) && item.field_name !== 'data'),
        );
        originBuiltFields.value = collectData?.fields?.filter(item => item.is_built_in && item.field_name === 'data');
      });

    await http
      .request('clean/getCleanStash', {
        params: {
          collector_config_id: currentIndexSet.collector_config_id,
        },
      })
      .then(res => {
        const etlFields = res?.data?.etl_fields || [];
        const existingFields = formData.value.fields || [];
        const existingFieldsMap = new Map(existingFields.map(field => [field.field_name, field]));
        const mergedFields = [];

        // 遍历 etlFields，将其添加到结果数组中
        etlFields.forEach(etlField => {
          mergedFields.push(etlField);
          // 从 existingFieldsMap 中删除已经处理过的 field_name
          existingFieldsMap.delete(etlField.field_name);
        });

        // 遍历 existingFieldsMap 中剩余的项（即那些在 etlFields 中未出现的项），将其添加到结果数组中
        existingFieldsMap.forEach(existingField => {
          mergedFields.push(existingField);
        });

        tableField.value = mergedFields.filter(
          item =>
            !builtInInitHiddenList.includes(item.field_name) &&
            !builtInInitHiddenList.includes(item.alias_name) &&
            !item.is_delete,
        );
        formData.value.etl_params.retain_original_text = res?.data?.etl_params.retain_original_text;
        formData.value.etl_params.path_regexp = res?.data?.etl_params.path_regexp || '';
        formData.value.etl_params.metadata_fields = res?.data?.etl_params.metadata_fields || [];
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
    return indexfieldTable.value.validateFieldTable();
    // return formData.value.etl_config === 'bk_log_json' ? indexfieldTable.value.validateFieldTable() : [];
  };

  const originfieldTable = ref(null);

  const submit = () => {
    validateForm.value.validate().then(res => {
      if (res) {
        const promises = [];
        // if (formData.value.etl_config === 'bk_log_json') {
        promises.splice(1, 0, ...checkFieldsTable());
        // }
        Promise.all(promises).then(
          async () => {
            confirmLoading.value = true;
            sliderLoading.value = true;
            const originfieldTableData = originfieldTable.value?.getData();
            const data = {
              collector_config_name: formData.value.collector_config_name,
              storage_cluster_id: formData.value.storage_cluster_id,
              retention: formData.value.retention,
              etl_params: {
                ...formData.value.etl_params,
                original_text_is_case_sensitive: originfieldTableData?.length
                  ? originfieldTableData[0].is_case_sensitive
                  : false,
                original_text_tokenize_on_chars: originfieldTableData?.length
                  ? originfieldTableData[0].tokenize_on_chars
                  : '',
              },
              etl_config: formData.value.etl_config,
              fields: indexfieldTable.value.getData().filter(item => !item.is_objectKey && !item.is_built_in),
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
                    isEdit.value = false;
                  });
                }
                // 请求成功后刷新页面
                location.reload();
                // store.dispatch('requestIndexSetFieldInfo',)
              })
              .finally(() => {
                confirmLoading.value = false;
                sliderLoading.value = false;
              });
          },
          validator => {
            console.warn('保存失败', validator);
          },
        );
      }
    });
  };
  const closeSlider = () => {
    isEdit.value = false;
  };

  const isOriginTableSaved = computed(() => {
    if (
      Object.prototype.hasOwnProperty.call(formData.value.etl_params ?? {}, 'retain_original_text') &&
      typeof formData.value.etl_params.retain_original_text === 'boolean'
    ) {
      return formData.value.etl_params.retain_original_text;
    }

    return true;
  });

  defineExpose({
    handleShowSlider: () => {
      hideSingleConfigInput();
      handleOpenSidebar();
    },
  });
</script>

<style lang="scss">
  .bklog-v3 {
    &.field-setting-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 90px;
      height: 52px;
      font-size: 12px;
      cursor: pointer;

      .bklog-setting {
        margin: 0px 6px 0 0;
        font-size: 16px;
        // line-height: 20px;
      }
    }
  }
</style>
<style lang="scss">
  .bklog-v3 {
    &.field-slider-content {
      min-height: 394px;
      max-height: calc(-119px + 100vh);
      overflow-y: auto;

      .add-collection-title {
        width: 100%;
        padding-top: 16px;
        font-size: 14px;
        font-weight: 700;
        color: #313238;
      }

      .setting-title {
        padding-top: 10px;
        font-size: 12px;
        color: #63656e;
      }

      .setting-desc {
        padding: 10px 0;
        color: #f00;
        cursor: pointer;
      }

      .field-setting-form {
        padding: 4px 40px 36px;

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
          .bk-label {
            padding-right: 12px;
            color: #4d4f56;
          }

          .bk-form-content {
            font-size: 12px;
            color: #313238;
          }
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
          margin-top: 5px;
        }
      }

      .submit-container {
        position: fixed;
        bottom: 0;
        padding: 16px 36px 16px;
      }
    }
  }
</style>
