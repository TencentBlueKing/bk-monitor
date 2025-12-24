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

import { defineComponent, ref, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useOperation } from '../../../../hook/useOperation';
import InfoTips from '../../../common-comp/info-tips';
import TableComponent from '../../../common-comp/table-component';
import $http from '@/api';
import type {
  TimeFieldType,
  TimeFieldUnit,
  ITimeField,
  ITimeIndex,
  IEsIndexItem,
  IEsIndexConfigData,
  IEsSelectFormData,
  IEsIndexTableDataItem,
  ITimeUnitOption,
  IEsIndexAdaptRequest,
  IApiResponse,
} from '../../../../type';

import './es-select-dialog.scss';

/**
 * ES索引选择对话框组件
 * 用于在第三方日志采集场景下，选择并添加新的ES索引
 */
export default defineComponent({
  name: 'EsSelectDialog',
  props: {
    /** 是否显示对话框 */
    isShowDialog: {
      type: Boolean,
      default: false,
    },
    /** 配置数据，包含存储集群ID和已有索引列表 */
    configData: {
      type: Object as PropType<IEsIndexConfigData>,
      default: () => ({}),
    },
    /** 场景ID */
    scenarioId: {
      type: String,
      default: '',
    },
    /** 已有索引的时间字段配置（用于校验时间字段一致性） */
    timeIndex: {
      type: Object as PropType<ITimeIndex | null>,
      default: () => null,
    },
  },

  emits: ['cancel', 'selected', 'timeIndex'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const { handleMultipleSelected, tableLoading } = useOperation();

    /**
     * 表格数据：匹配到的索引列表
     */
    const tableData = ref<IEsIndexTableDataItem[]>([]);
    /**
     * 确认按钮加载状态
     */
    const confirmLoading = ref(false);
    /**
     * 搜索按钮加载状态
     */
    const searchLoading = ref(false);
    /**
     * 匹配到的索引ID列表（与 tableData 相同，保留用于兼容）
     */
    const matchedTableIds = ref<IEsIndexTableDataItem[]>([]);
    /**
     * 时间字段列表（仅包含 date 和 long 类型的字段）
     */
    const timeFields = ref<ITimeField[]>([]);
    /**
     * 基础信息加载状态（获取字段列表时）
     */
    const basicLoading = ref(false);
    /**
     * 业务ID
     */
    const bkBizId = computed(() => store.getters.bkBizId);
    /**
     * 表单数据
     */
    const formData = ref<IEsSelectFormData>({
      resultTableId: '',
      time_field_type: undefined,
    });
    /**
     * 表单引用
     */
    const formRef = ref(null);

    /**
     * 时间精度单位选项列表
     */
    const timeUnits: ITimeUnitOption[] = [
      { name: t('秒（second）'), id: 'second' },
      { name: t('毫秒（millisecond）'), id: 'millisecond' },
      { name: t('微秒（microsecond）'), id: 'microsecond' },
    ];

    /**
     * 表单验证规则
     */
    const formRules = {
      resultTableId: [
        {
          required: true,
          message: t('请输入索引名称'),
          trigger: 'blur',
        },
        {
          validator: (val: string) => {
            if (!val) return false;
            // 不允许只输入单个通配符 *
            if (val === '*') {
              return false;
            }
            return true;
          },
          message: t('索引名称不能仅为通配符 *'),
          trigger: 'blur',
        },
      ],
      time_field: [
        {
          required: true,
          message: t('请选择时间字段'),
          trigger: 'change',
        },
        {
          validator: (val: string) => {
            /**
             * 如果已有索引配置，需要校验时间字段是否一致
             */
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
          message: t('请选择时间精度'),
          trigger: 'change',
        },
      ],
    };

    /**
     * 获取索引列表
     * 根据输入的结果表ID（支持通配符）查询匹配的索引列表
     * @returns {Promise<IEsIndexTableDataItem[]>} 匹配到的索引列表
     */
    const fetchList = async (): Promise<IEsIndexTableDataItem[]> => {
      try {
        const res = (await $http.request('/resultTables/list', {
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
            storage_cluster_id: props.configData.storage_cluster_id,
            result_table_id: formData.value.resultTableId,
          },
        })) as IApiResponse<IEsIndexTableDataItem[]>;

        return res.data || [];
      } catch (e) {
        console.error('获取索引列表失败:', e);
        return [];
      }
    };

    /**
     * 获取字段列表
     * 根据选中的结果表ID获取其字段信息，并筛选出时间相关字段（date 和 long 类型）
     * @returns {Promise<ITimeField[]>} 时间字段列表
     */
    const fetchInfo = async (): Promise<ITimeField[]> => {
      if (!formData.value.resultTableId?.trim()) {
        return [];
      }

      basicLoading.value = true;
      try {
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

        const result = await handleMultipleSelected(param, false, (res) => {
          /**
           * 筛选出时间相关字段（date 和 long 类型）
           * 并进行类型校验，确保字段结构正确
           */
          const responseData = res.data as { fields?: ITimeField[] } | undefined;
          const fields = (responseData?.fields || [])
            .filter((item: ITimeField) => {
              return (
                item?.field_name
                && item?.field_type
                && (item.field_type === 'date' || item.field_type === 'long')
              );
            })
            .map((item: ITimeField) => ({
              field_name: item.field_name,
              field_type: item.field_type as TimeFieldType,
            }));

          /**
           * 如果已有索引配置，且找到对应的时间字段，则回填表单数据（禁止更改字段名）
           */
          if (props.timeIndex && fields.length > 0) {
            const find = fields.find(item => item.field_name === props.timeIndex?.time_field);
            if (find) {
              Object.assign(formData.value, {
                time_field: props.timeIndex.time_field,
                time_field_type: props.timeIndex.time_field_type,
                time_field_unit: props.timeIndex.time_field_unit,
              });
            }
          }

          return fields;
        });

        // 类型转换：将 IFieldInfo[] 转换为 ITimeField[]
        return (result as ITimeField[]) || [];
      } catch (e) {
        console.error('获取字段列表失败:', e);
        return [];
      } finally {
        basicLoading.value = false;
      }
    };

    /**
     * 处理搜索操作
     * 验证表单后，并行获取索引列表和字段列表
     */
    const handleSearch = async (): Promise<void> => {
      if (!formRef.value) {
        return;
      }

      try {
        await formRef.value.validate();
        searchLoading.value = true;
        tableLoading.value = true;

        try {
          /**
           * 并行获取索引列表和字段列表
           */
          const [idRes, fieldRes] = await Promise.all([fetchList(), fetchInfo()]);

          matchedTableIds.value = idRes;
          tableData.value = idRes;
          timeFields.value = fieldRes;
        } catch (e) {
          console.log('搜索失败:', e);
        } finally {
          searchLoading.value = false;
          tableLoading.value = false;
        }
      } catch (err) {
        console.log('表单验证失败:', err);
      }
    };

    /**
     * 处理时间字段选择
     * 当用户选择时间字段时，自动设置对应的字段类型
     * @param {string} fieldName - 选中的字段名称
     */
    const handleSelectedTimeField = (fieldName: string): void => {
      if (!fieldName) {
        return;
      }

      const selectedField = timeFields.value.find(item => item.field_name === fieldName);
      if (selectedField) {
        formData.value = {
          ...formData.value,
          time_field: fieldName,
          time_field_type: selectedField.field_type,
          /**
           * 如果是 long 类型，保留原有的时间精度单位；如果是 date 类型，清空时间精度单位
           */
          time_field_unit: selectedField.field_type === 'long' ? formData.value.time_field_unit : undefined,
        };
      }
    };

    /**
     * 关闭对话框
     * 重置表单数据和相关状态
     */
    const handleCancel = (): void => {
      // 重置表单数据
      formData.value = {
        resultTableId: '',
        time_field_type: undefined,
      };
      // 清空表格数据和时间字段列表
      tableData.value = [];
      timeFields.value = [];
      matchedTableIds.value = [];
      emit('cancel', false);
    };

    /**
     * 处理确认操作
     * 调用适配接口，将新索引添加到现有索引集合中，并触发选中事件
     */
    const handleConfirm = async (): Promise<void> => {
      if (!formRef.value) {
        return;
      }

      try {
        /**
         * 验证表单
         */
        await formRef.value.validate();
      } catch (e) {
        console.warn('表单验证失败:', e);
        return;
      }

      // 类型校验：确保必要字段存在
      if (!formData.value.time_field || !formData.value.time_field_type) {
        return;
      }

      // 如果是 long 类型，必须提供时间精度单位
      if (formData.value.time_field_type === 'long' && !formData.value.time_field_unit) {
        return;
      }

      try {
        confirmLoading.value = true;

        /**
         * 构建适配请求数据
         */
        const data: IEsIndexAdaptRequest = {
          scenario_id: props.scenarioId,
          bk_biz_id: bkBizId.value,
          storage_cluster_id: props.configData.storage_cluster_id,
          /**
           * 已有索引列表，使用新的时间字段配置
           */
          basic_indices: (props.configData.indexes || []).map((item: IEsIndexItem) => ({
            index: item.result_table_id,
            time_field: formData.value.time_field || '',
            time_field_type: formData.value.time_field_type || 'date',
          })),
          /**
           * 新增的索引
           */
          append_index: {
            index: formData.value.resultTableId,
            time_field: formData.value.time_field,
            time_field_type: formData.value.time_field_type,
          },
        };

        /**
         * 调用适配接口
         */
        await $http.request('/resultTables/adapt', { data });

        /**
         * 触发选中事件
         */
        emit('selected', {
          bk_biz_id: bkBizId.value,
          result_table_id: formData.value.resultTableId,
        });

        /**
         * 触发时间索引配置事件
         */
        emit('timeIndex', {
          time_field: formData.value.time_field,
          time_field_type: formData.value.time_field_type,
          time_field_unit: formData.value.time_field_unit,
        });

        /**
         * 关闭对话框
         */
        handleCancel();
      } catch (e) {
        console.error('添加索引失败:', e);
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
          ref={formRef}
          {...{
            props: {
              model: formData.value,
              rules: formRules,
            },
          }}
        >
          <bk-form-item
            label={t('索引')}
            property='resultTableId'
            required
          >
            <bk-input
              class='input-box'
              placeholder='log_search_*'
              value={formData.value.resultTableId}
              on-input={(val: string) => {
                formData.value.resultTableId = val;
              }}
            />
            <bk-button
              disabled={!formData.value.resultTableId?.trim()}
              loading={searchLoading.value}
              on-click={handleSearch}
            >
              {t('搜索')}
            </bk-button>
            <InfoTips tips={t('支持" * "匹配，不支持其他特殊符号')} />
          </bk-form-item>

          <bk-form-item class='table-item-box mt-12'>
            {tableData.value.length > 0 && (
              <div class='result-tips'>
                <i class='bk-icon icon-check-circle-shape' />
                {t('成功匹配 {x} 条索引', { x: tableData.value.length })}
              </div>
            )}
            <TableComponent
              key={String(props.isShowDialog)}
              height={320}
              loading={tableLoading.value}
              data={tableData.value}
              skeletonConfig={{
                columns: 2,
                rows: 4,
                widths: ['50%', '50%'],
              }}
              columns={[
                {
                  title: t('索引'),
                  colKey: 'result_table_id',
                  ellipsis: true,
                },
              ]}
            />
          </bk-form-item>
          <bk-form-item
            label={t('时间字段')}
            property='time_field'
            required
          >
            <bk-select
              clearable={false}
              loading={basicLoading.value}
              value={formData.value.time_field}
              searchable
              disabled={timeFields.value.length === 0}
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
                on-selected={(val: TimeFieldUnit) => {
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
