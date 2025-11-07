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

import { defineComponent, ref, computed } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useOperation } from '../../../../hook/useOperation';
import InfoTips from '../../../common-comp/info-tips';
import $http from '@/api';

import './es-select-dialog.scss';

export default defineComponent({
  name: 'EsSelectDialog',
  props: {
    isShowDialog: {
      type: Boolean,
      default: false,
    },
    configData: {
      type: Object,
      default: () => ({}),
    },
    scenarioId: {
      type: String,
      default: '',
    },
    timeIndex: {
      type: Object,
      default: () => ({}),
    },
  },

  emits: ['cancel', 'selected', 'timeIndex'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const tableData = ref([]);
    const { handleMultipleSelected, tableLoading } = useOperation();
    // const tableLoading = ref(false);
    const confirmLoading = ref(false);
    const searchLoading = ref(false);
    const matchedTableIds = ref([]);
    const timeFields = ref([]);
    const basicLoading = ref(false);
    const bkBizId = computed(() => store.getters.bkBizId);
    const formData = ref({
      resultTableId: '',
      time_field_type: '',
    });
    const timeUnits = [
      { name: t('秒（second）'), id: 'second' },
      { name: t('毫秒（millisecond）'), id: 'millisecond' },
      { name: t('微秒（microsecond）'), id: 'microsecond' },
    ];

    const formRules = {
      resultTableId: [
        {
          required: true,
          trigger: 'blur',
        },
        {
          validator: val => val && val !== '*',
          trigger: 'blur',
        },
      ],
      time_field: [
        {
          required: true,
          trigger: 'change',
        },
        {
          validator: val => {
            if (!props.timeIndex) {
              return true;
            }
            return props.timeIndex.time_field === val;
          },
          message: t('时间字段需要保持一致'),
          trigger: 'change',
        },
      ],
      time_field_unit: [
        {
          required: true,
          trigger: 'change',
        },
      ],
    };

    const fetchList = async () => {
      try {
        const res = await $http.request('/resultTables/list', {
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
            storage_cluster_id: props.configData.storage_cluster_id,
            result_table_id: formData.value.resultTableId,
          },
        });
        return res.data;
      } catch (e) {
        console.warn(e);
        // this.indexErrorText += e.message;
        // this.emptyType = '500';
        return [];
      }
    };

    const fetchInfo = async () => {
      basicLoading.value = true;
      const param = {
        params: {
          result_table_id: formData.value.resultTableId,
        },
        query: {
          scenario_id: props.scenarioId,
          bk_biz_id: bkBizId.value,
          storage_cluster_id: props.configData.storage_cluster_id,
        },
      };
      const result = await handleMultipleSelected(param, false, res => {
        basicLoading.value = false;
        const fields = res.data.fields.filter(item => item.field_type === 'date' || item.field_type === 'long');
        // 如果已经添加了索引，回填三个字段（禁止更改字段名）
        if (props.timeIndex) {
          const find = fields.find(item => item.field_name === props.timeIndex.time_field);
          if (find) {
            Object.assign(formData.value, props.timeIndex);
          }
        }
        return fields;
      });
      return result;
    };

    const handleSearch = async () => {
      searchLoading.value = true;
      tableLoading.value = true;
      const [idRes, fieldRes] = await Promise.all([fetchList(), fetchInfo()]);
      matchedTableIds.value = idRes;
      tableData.value = idRes;
      timeFields.value = fieldRes as any;
      searchLoading.value = false;
      tableLoading.value = false;
    };

    // 选择时间字段
    const handleSelectedTimeField = fieldName => {
      const timeFieldType = timeFields.value.find(item => item.field_name === fieldName)?.field_type;
      formData.value = {
        ...formData.value,
        time_field_type: timeFieldType,
        time_field: fieldName,
      };
      console.log(formData.value);
    };
    /**
     * 关闭新增索引弹窗
     */
    const handleCancel = () => {
      emit('cancel', false);
    };

    const handleConfirm = async () => {
      try {
        // await this.$refs.formRef.validate();
        confirmLoading.value = true;
        const data = {
          scenario_id: props.scenarioId,
          storage_cluster_id: props.configData.storage_cluster_id,
          basic_indices: props.configData.indexes.map(item => ({
            index: item.result_table_id,
            time_field: formData.value.time_field,
            time_field_type: formData.value.time_field_type,
          })),
          append_index: {
            index: formData.value.resultTableId,
            time_field: formData.value.time_field,
            time_field_type: formData.value.time_field_type,
          },
        };
        console.log(data, 'data');
        await $http.request('/resultTables/adapt', { data });
        emit('selected', {
          bk_biz_id: bkBizId.value,
          result_table_id: formData.value.resultTableId,
        });
        emit('timeIndex', {
          time_field: formData.value.time_field,
          time_field_type: formData.value.time_field_type,
          time_field_unit: formData.value.time_field_unit,
        });
        handleCancel();
      } catch (e) {
        console.warn(e);
      } finally {
        confirmLoading.value = false;
      }
    };
    return () => (
      <bk-dialog
        width={680}
        ext-cls='es-select-dialog'
        header-position={'left'}
        mask-close={false}
        ok-text={t('添加')}
        theme='primary'
        title={t('新增索引')}
        value={props.isShowDialog}
        on-cancel={handleCancel}
      >
        <bk-form
          label-width={80}
          {...{
            props: {
              model: formData.value,
              rules: formRules,
            },
          }}
        >
          <bk-form-item
            label={t('索引')}
            property={'resultTableId'}
            required={true}
          >
            <bk-input
              class='input-box'
              placeholder='log_search_*'
              value={formData.value.resultTableId}
              on-input={val => {
                formData.value.resultTableId = val;
              }}
            />
            <bk-button
              disabled={!formData.value.resultTableId}
              on-click={handleSearch}
            >
              {t('搜索')}
            </bk-button>
            <InfoTips tips={t('支持“ * ”匹配，不支持其他特殊符号')} />
          </bk-form-item>

          <bk-form-item class='table-item-box mt-12'>
            {tableData.value.length > 0 && (
              <div class='result-tips'>
                <i class='bk-icon icon-check-circle-shape' />
                {t('成功匹配 {x} 条索引', { x: tableData.value.length })}
              </div>
            )}
            <bk-table
              key={props.isShowDialog}
              height={320}
              v-bkloading={{ isLoading: tableLoading.value }}
              data={tableData.value}
            >
              <bk-table-column
                label={t('索引')}
                prop='result_table_id'
              />
            </bk-table>
          </bk-form-item>
          <bk-form-item
            label={t('时间字段')}
            property={'name'}
            required={true}
          >
            <bk-select
              clearable={false}
              loading={basicLoading.value}
              value={formData.value.time_field}
              searchable
              on-selected={handleSelectedTimeField}
            >
              {(timeFields.value || []).map(item => (
                <bk-option
                  id={item.field_name}
                  key={item.field_name}
                  name={item.field_name}
                />
              ))}
            </bk-select>
          </bk-form-item>
          {formData.value.time_field_type === 'long' && (
            <bk-form-item
              label={t('时间精度')}
              property='time_field_unit'
              required
            >
              <bk-select
                clearable={false}
                value={formData.value.time_field_unit}
                searchable
                on-selected={val => {
                  formData.value.time_field_unit = val;
                }}
              >
                {timeUnits.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
              </bk-select>
            </bk-form-item>
          )}
        </bk-form>
        <div slot='footer'>
          <bk-button
            class='mr-8'
            disabled={!(formData.value.resultTableId && formData.value.time_field)}
            loading={confirmLoading.value}
            theme='primary'
            on-click={handleConfirm}
          >
            {t('添加')}
          </bk-button>
          <bk-button on-click={handleCancel}>{t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  },
});
