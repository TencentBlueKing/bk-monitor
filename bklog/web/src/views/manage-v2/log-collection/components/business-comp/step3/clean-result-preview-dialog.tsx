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

import { defineComponent, ref, computed, watch, onBeforeUnmount, onMounted, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { isFieldTypeDisabled, judgeNumber } from '@/common/util';
import $http from '@/api';
import tippy, { type Instance } from 'tippy.js';
import TableComponent from '../../common-comp/table-component';
import InfoTips from '../../common-comp/info-tips';

import './clean-result-preview-dialog.scss';

/** 模板字段项（来自选择模板的 etl_fields） */
type TemplateFieldItem = {
  field_name: string;
  field_type: string;
  value?: unknown;
  is_delete: boolean;
  is_built_in: boolean;
  is_analyzed: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars?: string;
  [key: string]: unknown;
};

/** 选中清洗模板 */
type CleanTemplate = {
  clean_template_id: number;
  name: string;
  clean_type: 'bk_log_json' | 'bk_log_delimiter' | 'bk_log_regexp';
  etl_params: Record<string, unknown>;
  etl_fields: TemplateFieldItem[];
  description?: string;
  bk_biz_id?: number;
  [key: string]: unknown;
};

/** 预览确认后可直接回填清洗表单的完整模板数据 */
type CleanTemplateFormData = CleanTemplate & {
  etl_config: CleanTemplate['clean_type'];
};

/** 预览弹窗内部的字段行 */
type PreviewFieldRow = TemplateFieldItem & {
  /** 后端推断的字段类型 */
  inferredType: string | null;
  /** 字段值（调试返回） */
  value: unknown;
  /** 是否空值冲突 */
  empty: boolean;
  /** 是否类型不匹配冲突 */
  typeErr: boolean;
  /** 解析状态：'success' | 'error' */
  status: 'success' | 'error';
  /** 后端返回的冲突类型 */
  errorType: null | 'TYPE_MISMATCH' | 'EMPTY_VALUE';
  /** 后端返回的冲突说明 */
  errorMessage: string;
};

/** 已保存模板预览接口的字段数据 */
type DebugFieldItem = {
  field_name: string;
  field_type: string;
  inferred_field_type: string | null;
  value: unknown;
  error_type: null | 'TYPE_MISMATCH' | 'EMPTY_VALUE';
  error_message: string;
};

type DebugPreviewData = {
  fields: DebugFieldItem[];
  match_rate: number;
  normal_count: number;
  abnormal_count: number;
};

/** 用于判断模板字段配置是否发生净变化的可编辑字段快照 */
type EditableFieldSnapshot = Pick<
  TemplateFieldItem,
  'field_name' | 'field_type' | 'is_analyzed' | 'is_case_sensitive' | 'tokenize_on_chars'
>;

/** 数值字段类型（无调试值时按模板既定类型推断 verdict 使用） */
const NUMERIC_FIELD_TYPES = ['int', 'long', 'double', 'float'];

/** 分词设置选项（tippy 弹窗内使用） */
const participleList = [
  {
    id: 'default',
    name: '自然语言分词',
  },
  {
    id: 'custom',
    name: '自定义',
  },
];

/**
 * @file 清洗结果预览弹窗
 */
export default defineComponent({
  name: 'CleanResultPreviewDialog',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    bkBizId: {
      type: [Number, String],
      default: '',
    },
    /** 选中的清洗模板（来自选择清洗模板弹窗） */
    template: {
      type: Object as () => CleanTemplate | null,
      default: null,
    },
    /** 采集项 ID（用于 collect/getEtlPreview 接口） */
    collectorConfigId: {
      type: [Number, String],
      default: '',
    },
    /** 日志样例（默认带入父组件中的 logOriginal） */
    logExample: {
      type: String,
      default: '',
    },
    /** 日志样例刷新加载中 */
    logExampleLoading: {
      type: Boolean,
      default: false,
    },
    /** 是否为清洗模板编辑模式（用于判断调哪个接口） */
    isTempField: {
      type: Boolean,
      default: false,
    },
    /** 自定义分词符的默认值（切换到自定义时填入） */
    originalTextTokenizeOnChars: {
      type: String,
      default: '',
    },
    /** 当前采集项的下发状态 */
    collectStatus: {
      type: String,
      default: '',
    },
  },
  emits: ['close', 'confirm', 'refresh'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    /** 字段类型选项：与 FieldList 一致，取自 global 接口（globals.field_data_type） */
    const fieldTypeOptions = computed(() => store.getters['globals/globalsData']?.field_data_type || []);
    /** 当前字段类型是否禁用（与 FieldList 一致，基于字段预览值判断） */
    const isTypeDisabled = (row: PreviewFieldRow, option: { id: string }) => {
      // 无调试结果（template 回填）时没有真实预览值，不做类型禁用，对齐 FieldList 新增行
      if (previewMode.value !== 'debug') return false;
      return isFieldTypeDisabled({ verdict: judgeNumber(row.value), value: row.value }, option);
    };

    /** 当前显示的日志样例（可编辑） */
    const logExampleText = ref(props.logExample || '');
    /** 表格数据 */
    const tableData = ref<PreviewFieldRow[]>([]);
    /** 当前调试结果对应的模板字段配置快照 */
    const initialEditableFieldsSnapshot = ref('[]');
    /** 调试加载中 */
    const isDebugLoading = ref(false);
    /** 解析成功率（保留 1 位小数） */
    const successRate = ref(0);
    /** 冲突字段数（用于 UI 显示） */
    const errorFieldCount = ref(0);
    /** 正常字段数（用于 UI 显示） */
    const normalFieldCount = ref(0);
    /** 是否已有数据（首次调试后展示统计卡片等） */
    const hasLoaded = ref(false);
    /** 当前表格数据来源：'debug' 调试结果 | 'template' 模板回填（无调试样例）| 'template-error' 模板回填（调试接口报错） */
    const previewMode = ref<'debug' | 'template' | 'template-error'>('debug');
    /** tippy 实例列表（分词弹窗） */
    let tippyInstances: Instance[] = [];
    let menuInitTimer: ReturnType<typeof setTimeout> | null = null;
    let isDestroyed = false;
    /** 当前分词符弹窗选中的类型 */
    const currentParticipleState = ref('default');
    /** 分词符弹窗内的缓存数据 */
    const cacheData = ref({
      is_analyzed: false,
      tokenize_on_chars: '',
      is_case_sensitive: false,
    });
    /** 当前选中的模板的 etl_fields（用于对比） */
    const templateFieldMap = computed(() => {
      const map = new Map<string, TemplateFieldItem>();
      if (!props.template?.etl_fields) return map;
      for (const f of props.template.etl_fields) {
        if (f.field_name) {
          map.set(f.field_name, f);
        }
      }
      return map;
    });

    // 同步 prop.logExample 变化
    watch(
      () => props.logExample,
      (val: string) => {
        logExampleText.value = val || '';
      },
    );

    // 同步 prop.visible：打开时初始化一次调试
    watch(
      () => props.visible,
      (val: boolean) => {
        if (val) {
          // 打开时以 prop.logExample 为初始值
          logExampleText.value = props.logExample || '';
          // 自动触发一次调试（如果模板存在 + 样例非空）
          if (props.template && logExampleText.value) {
            handleDebug();
          } else if (props.template) {
            // 没有调试样例时，使用模板字段数据回填表格（不显示解析状态列与统计卡片）
            previewMode.value = 'template';
            buildTableFromTemplate(false);
          } else {
            // 无模板时不初始化表格，显示暂无数据
            tableData.value = [];
            initialEditableFieldsSnapshot.value = '[]';
          }
        } else {
          // 关闭时清空数据
          hasLoaded.value = false;
          previewMode.value = 'debug';
          tableData.value = [];
          initialEditableFieldsSnapshot.value = '[]';
        }
      },
      { immediate: true },
    );

    // 表格数据或展示模式变化时，重新初始化 tippy 弹窗。
    watch(
      () => [tableData.value, previewMode.value],
      () => {
        nextTick(() => {
          scheduleInitMenuPop(600);
        });
      },
    );

    onMounted(() => {
      nextTick(() => {
        scheduleInitMenuPop();
      });
    });

    onBeforeUnmount(() => {
      isDestroyed = true;
      if (menuInitTimer) {
        clearTimeout(menuInitTimer);
        menuInitTimer = null;
      }
      destroyTippyInstances();
      tableData.value = [];
      initialEditableFieldsSnapshot.value = '[]';
    });

    /** 提取并序列化表格中的可编辑模板配置 */
    const serializeEditableFields = (rows: PreviewFieldRow[]): string => {
      const editableFields: EditableFieldSnapshot[] = rows.map(row => ({
        field_name: row.field_name || '',
        field_type: row.field_type || '',
        is_analyzed: !!row.is_analyzed,
        is_case_sensitive: !!row.is_case_sensitive,
        tokenize_on_chars: row.tokenize_on_chars || '',
      }));
      return JSON.stringify(editableFields);
    };

    /** 更新本次调试结果的字段配置比较基线 */
    const updateEditableFieldsSnapshot = (rows: PreviewFieldRow[]) => {
      initialEditableFieldsSnapshot.value = serializeEditableFields(rows);
    };

    /**
     * 重新调试
     * 使用已保存模板预览接口，解析配置和字段匹配结果均来自后端。
     */
    const handleDebug = () => {
      if (!props.template) return;
      const data = {
        data: logExampleText.value,
      };

      isDebugLoading.value = true;

      $http
        .request('clean/getTemplateEtlPreview', {
          params: {
            clean_template_id: props.template.clean_template_id,
          },
          data,
        })
        .then((res: any) => {
          previewMode.value = 'debug';
          buildTableFromDebug(res?.data);
          hasLoaded.value = true;
        })
        .catch((err: unknown) => {
          console.warn('清洗结果预览调试失败', err);
          // 调试接口报错时，使用模板字段数据回填表格，解析状态全部标记为空值异常
          previewMode.value = 'template-error';
          buildTableFromTemplate(true);
        })
        .finally(() => {
          isDebugLoading.value = false;
        });
    };

    /**
     * 根据调试结果构建表格
     * 初始字段类型、推断类型和冲突状态均以后端返回为准。
     */
    const buildTableFromDebug = (previewData?: DebugPreviewData) => {
      const list: PreviewFieldRow[] = (previewData?.fields || []).map(item => {
        const templateField = templateFieldMap.value.get(item.field_name);
        const empty = item.error_type === 'EMPTY_VALUE';
        const typeErr = item.error_type === 'TYPE_MISMATCH';
        return {
          ...structuredClone(templateField ?? {}),
          field_name: item.field_name || '',
          field_type: item.field_type || 'string',
          inferredType: item.inferred_field_type,
          value: item.value,
          is_delete: templateField?.is_delete ?? false,
          is_built_in: templateField?.is_built_in ?? false,
          is_analyzed: templateField?.is_analyzed ?? false,
          is_case_sensitive: templateField?.is_case_sensitive ?? false,
          tokenize_on_chars: templateField?.tokenize_on_chars ?? '',
          empty,
          typeErr,
          status: item.error_type ? 'error' : 'success',
          errorType: item.error_type,
          errorMessage: item.error_message || '',
        };
      });
      tableData.value = list;
      updateEditableFieldsSnapshot(list);
      successRate.value = Number(previewData?.match_rate ?? 0);
      errorFieldCount.value = Number(previewData?.abnormal_count ?? 0);
      normalFieldCount.value = Number(previewData?.normal_count ?? 0);
    };

    /**
     * 无调试结果时，使用模板字段数据构建表格
     * withError 为 true（调试接口报错）时，解析状态全部标记为空值异常并按全部异常展示统计；
     * 为 false（无调试样例）时，无冲突标记、不展示统计卡片。
     */
    const buildTableFromTemplate = (withError: boolean) => {
      if (!props.template) return;
      const list: PreviewFieldRow[] = (props.template.etl_fields ?? [])
        .filter(item => !item.is_delete)
        .map(item => ({
          ...structuredClone(item),
          inferredType: null,
          value: null,
          empty: withError,
          typeErr: false,
          status: withError ? 'error' : 'success',
          errorType: withError ? 'EMPTY_VALUE' : null,
          errorMessage: '',
        }));
      tableData.value = list;
      updateEditableFieldsSnapshot(list);
      if (withError) {
        // 调试报错时按全部字段异常展示统计
        successRate.value = 0;
        errorFieldCount.value = list.length;
        normalFieldCount.value = 0;
        hasLoaded.value = true;
      } else {
        hasLoaded.value = false;
      }
    };

    /** 编辑字段名 */
    const handleFieldNameChange = (row: PreviewFieldRow, value: string) => {
      row.field_name = value;
    };

    /** 编辑字段类型 */
    const handleTypeChange = (row: PreviewFieldRow, value: string) => {
      row.field_type = value;
      if (row.errorType === 'TYPE_MISMATCH' && row.inferredType) {
        row.typeErr = value !== row.inferredType;
        row.status = row.typeErr ? 'error' : 'success';
      }
    };

    /** 分词类型变更（tippy 弹窗内） */
    const handleChangeParticipleState = (state: string) => {
      currentParticipleState.value = state;
      cacheData.value.tokenize_on_chars = state === 'custom' ? props.originalTextTokenizeOnChars : '';
    };

    /** 关闭分词符 tippy 弹窗 */
    const handleWordBreakerCancelClick = () => {
      tippyInstances.forEach(i => i?.hide());
    };

    /** 渲染分词设置列（点击通过 tippy 弹窗打开） */
    const renderWordBreaker = (row: PreviewFieldRow) => {
      return (
        <div class='word-breaker'>
          <span
            class='word-breaker-edit'
            data-field-name={row.field_name}
          >
            {row.is_analyzed ? (
              <div class='analyzed-box'>
                <div>{row.tokenize_on_chars || t('自然语言分词')}</div>
                <div>
                  {t('大小写敏感')}: {row.is_case_sensitive ? t('是') : t('否')}
                </div>
              </div>
            ) : (
              <span>{t('不分词')}</span>
            )}
            <i class='select-angle bk-icon icon-angle-down' />
          </span>
          <div
            style={{ display: 'none' }}
            class='word-breaker-popover'
          >
            <div class='word-breaker-menu-content'>
              <div class='menu-item'>
                <span class='menu-item-label'>{t('分词')}</span>
                <bk-switcher
                  theme='primary'
                  value={cacheData.value.is_analyzed}
                  on-change={(value: boolean) => {
                    cacheData.value.is_analyzed = value;
                  }}
                />
              </div>
              <div class='menu-item'>
                <span class='menu-item-label'>{t('分词符')}</span>
                <div class='bk-button-group'>
                  {participleList.map(option => (
                    <bk-button
                      key={option.id}
                      class={{
                        'participle-btn': true,
                        'is-selected': currentParticipleState.value === option.id,
                      }}
                      disabled={!cacheData.value.is_analyzed}
                      size='small'
                      on-click={() => handleChangeParticipleState(option.id)}
                    >
                      {t(option.name)}
                    </bk-button>
                  ))}
                </div>
                {currentParticipleState.value === 'custom' && (
                  <bk-input
                    class='custom-input'
                    disabled={!cacheData.value.is_analyzed}
                    value={cacheData.value.tokenize_on_chars}
                    on-change={(value: string) => {
                      cacheData.value.tokenize_on_chars = value;
                    }}
                  />
                )}
              </div>
              <div class='menu-item'>
                <span class='menu-item-label'>{t('大小写敏感')}</span>
                <bk-switcher
                  disabled={!cacheData.value.is_analyzed}
                  theme='primary'
                  value={cacheData.value.is_case_sensitive}
                  on-change={(value: boolean) => {
                    cacheData.value.is_case_sensitive = value;
                  }}
                />
              </div>
              <div class='menu-footer'>
                <bk-button
                  size='small'
                  theme='primary'
                  on-click={() => {
                    handleWordBreakerCancelClick();
                    row.is_analyzed = cacheData.value.is_analyzed;
                    row.tokenize_on_chars = cacheData.value.tokenize_on_chars;
                    row.is_case_sensitive = cacheData.value.is_case_sensitive;
                  }}
                >
                  {t('确定')}
                </bk-button>
                <bk-button
                  size='small'
                  on-click={handleWordBreakerCancelClick}
                >
                  {t('取消')}
                </bk-button>
              </div>
            </div>
          </div>
        </div>
      );
    };

    /** 初始化分词符 tippy 弹窗 */
    const initMenuPop = () => {
      if (isDestroyed) return;
      destroyTippyInstances();

      const targets = document.querySelectorAll('.preview-fields-table .t-table__body .word-breaker-edit');
      if (!targets.length) return;

      const instances = tippy(targets as unknown as HTMLElement[], {
        trigger: 'click',
        placement: 'top',
        theme: 'light word-breaker-theme-popover',
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
        onShow(instance) {
          const reference = instance.reference as HTMLElement;
          reference.classList.add('is-hover');

          const fieldName = reference.dataset.fieldName;
          const currentRow = tableData.value.find(item => item.field_name === fieldName);

          if (currentRow) {
            cacheData.value = {
              is_analyzed: currentRow.is_analyzed,
              tokenize_on_chars: currentRow.tokenize_on_chars || '',
              is_case_sensitive: currentRow.is_case_sensitive,
            };
            currentParticipleState.value = currentRow.tokenize_on_chars ? 'custom' : 'default';
          }

          const container = reference.nextElementSibling as HTMLElement | null;
          const contentNode = container?.querySelector('.word-breaker-menu-content') as HTMLElement | null;
          if (contentNode) {
            instance.setContent(contentNode);
          }
        },
        onHide(instance) {
          (instance.reference as HTMLElement).classList.remove('is-hover');
        },
        onHidden(instance) {
          const reference = instance.reference as HTMLElement;
          const container = reference.nextElementSibling as HTMLElement | null;
          if (container) {
            const tippyContentEl = instance.popper?.querySelector('.tippy-content');
            const menuContent = tippyContentEl?.querySelector('.word-breaker-menu-content') as HTMLElement | null;
            if (menuContent && menuContent.parentElement !== container) {
              container.appendChild(menuContent);
            }
          }
          instance.setContent(document.createElement('div'));
        },
        content: document.createElement('div'),
      });

      tippyInstances = Array.isArray(instances) ? instances : [instances];
    };

    /** 延时初始化 tippy */
    const scheduleInitMenuPop = (delay = 0) => {
      if (menuInitTimer) {
        clearTimeout(menuInitTimer);
        menuInitTimer = null;
      }
      menuInitTimer = setTimeout(() => {
        menuInitTimer = null;
        initMenuPop();
      }, delay);
    };

    /** 销毁所有 tippy 实例 */
    const destroyTippyInstances = () => {
      tippyInstances.forEach(i => {
        try {
          i.hide();
          i.destroy();
        } catch {
          // Ignore errors from instances that have already been destroyed.
        }
      });
      tippyInstances = [];
    };

    /** 格式化值用于显示 */
    const formatDisplayValue = (value: unknown): string => {
      if (value === null || value === undefined) return '';
      if (Array.isArray(value)) return `[ ${value.join(', ')} ]`;
      if (typeof value === 'object') return JSON.stringify(value);
      return String(value);
    };

    /** 关闭弹窗 */
    const handleClose = () => {
      emit('close');
    };

    /** 监听 dialog value 变化 */
    const handleDialogValueChange = (val: boolean) => {
      if (!val) {
        handleClose();
      }
    };

    /** 忽略冲突并返回包含预览字段修改的完整模板 */
    const handleConfirm = () => {
      if (!props.template || tableData.value.length === 0) return;

      // 预览表格中已出现的字段名集合，用于合并模板隐藏字段时去重
      const previewedFieldNames = new Set(tableData.value.map(item => item.field_name));

      // 调试接口不返回模板中被隐藏（is_delete）的字段，需从模板中合并回结果，避免确认填入后丢失
      const deletedFields = (props.template.etl_fields ?? []).filter(
        item => item.is_delete && !previewedFieldNames.has(item.field_name),
      );

      const templateData: CleanTemplateFormData = {
        ...props.template,
        etl_config: props.template.clean_type,
        etl_fields: [
          ...tableData.value.map(
            ({
              inferredType: _inferredType,
              empty: _empty,
              typeErr: _typeErr,
              status: _status,
              errorType: _errorType,
              errorMessage: _errorMessage,
              ...field
            }) =>
              ({
                ...field,
                // 生成 verdict 供 FieldList 类型禁用判断：有调试结果按真实值；无调试结果按模板既定类型推断（非数值类型禁选数值类型）
                verdict:
                  previewMode.value === 'debug'
                    ? judgeNumber(field.value)
                    : !NUMERIC_FIELD_TYPES.includes(field.field_type),
              }) as TemplateFieldItem,
          ),
          ...deletedFields.map(item => ({
            ...item,
            verdict: !NUMERIC_FIELD_TYPES.includes(item.field_type),
          })),
        ],
      };
      emit('confirm', templateData, logExampleText.value, hasTemplateConfigModified.value);
    };

    /** 是否存在冲突 */
    const hasException = computed(() => tableData.value.some(row => row.status === 'error'));

    /** 模板字段配置是否相对本次调试结果发生净变化 */
    const hasTemplateConfigModified = computed(
      () => serializeEditableFields(tableData.value) !== initialEditableFieldsSnapshot.value,
    );

    /** 仅在采集下发中且尚无调试样例时显示提示 */
    const showCollectingTip = computed(() => props.collectStatus === 'running' && !logExampleText.value);

    /** 刷新日志样例：emit 给父组件调用接口获取日志数据 */
    const handleRefresh = () => {
      emit('refresh');
    };

    // 表格列定义（使用 TableComponent/tdesign-vue 的 title + cell 方式）
    const columns = computed(() => [
      {
        title: '#',
        colKey: 'row_index',
        width: 30,
        className: () => 'preview-disabled-column',
        cell: (_h: any, { rowIndex }: { rowIndex: number }) => (
          <div class='serial-cell'>
            <span class='cell-index'>{rowIndex + 1}</span>
          </div>
        ),
      },
      {
        title: t('解析状态'),
        colKey: 'status',
        width: 90,
        className: () => 'preview-disabled-column',
        cell: (_h: any, { row }: { row: PreviewFieldRow }) => {
          // 构建冲突原因 tooltip 内容
          const buildStatusErrorTips = () => {
            const reasons: string[] = [];
            if (row.empty) {
              reasons.push(t('未从样例中匹配到有效值'));
            }
            if (row.typeErr) {
              reasons.push(t('字段类型不匹配'));
            }
            return reasons.length > 0
              ? { content: reasons.join('；'), placement: 'top' }
              : { content: '', placement: 'top' };
          };

          return (
            <div
              class={['status-cell', row.status === 'error' ? 'is-error' : 'is-success']}
              v-bk-tooltips={row.status === 'error' ? buildStatusErrorTips() : false}
            >
              <span class='status-dot' />
              <span>{row.status === 'error' ? t('冲突') : t('成功')}</span>
            </div>
          );
        },
      },
      {
        title: t('字段名'),
        colKey: 'field_name',
        width: 160,
        className: () => 'preview-editable-column',
        cell: (_h: any, { row }: { row: PreviewFieldRow }) => (
          <div class='field-name-cell'>
            <bk-input
              class='field-name-input'
              behavior='simplicity'
              value={row.field_name}
              on-change={(val: string) => handleFieldNameChange(row, val)}
            />
          </div>
        ),
      },
      {
        title: t('字段类型'),
        colKey: 'field_type',
        width: 130,
        className: () => 'preview-editable-column',
        cell: (_h: any, { row }: { row: PreviewFieldRow }) => (
          <div class='type-cell'>
            <bk-select
              class='type-select'
              clearable={false}
              value={row.field_type}
              on-change={(val: string) => handleTypeChange(row, val)}
            >
              {fieldTypeOptions.value.map(opt => (
                <bk-option
                  key={opt.id}
                  id={opt.id}
                  disabled={isTypeDisabled(row, opt)}
                  name={opt.name}
                />
              ))}
            </bk-select>
            {row.typeErr && (
              <i
                class='bk-icon icon-exclamation-circle-shape type-error-icon'
                v-bk-tooltips={{ content: t('字段类型不匹配'), placement: 'top' }}
              />
            )}
          </div>
        ),
      },
      {
        title: t('分词设置'),
        colKey: 'is_analyzed',
        width: 180,
        className: () => 'preview-editable-column',
        cell: (_h: any, { row }: { row: PreviewFieldRow }) => renderWordBreaker(row),
      },
      {
        title: t('值'),
        colKey: 'value',
        className: () => 'preview-disabled-column',
        cell: (_h: any, { row }: { row: PreviewFieldRow }) => (
          <div class='value-cell'>
            {row.empty ? (
              <span class='value-empty'>{t('空值')}</span>
            ) : (
              <span
                class='value-text'
                title={formatDisplayValue(row.value)}
              >
                {formatDisplayValue(row.value)}
              </span>
            )}
            {row.empty && (
              <i
                class='bk-icon icon-exclamation-circle-shape value-empty-icon'
                v-bk-tooltips={{ content: t('未从样例中匹配到有效值'), placement: 'top' }}
              />
            )}
          </div>
        ),
      },
    ]);

    return () => (
      <bk-dialog
        value={props.visible}
        width={960}
        title={t('清洗结果预览')}
        header-position='left'
        show-footer={true}
        mask-close={false}
        on-value-change={handleDialogValueChange}
        on-closed={handleClose}
        scopedSlots={{
          footer: () => (
            <div>
              {hasTemplateConfigModified.value ? (
                <bk-popconfirm
                  width={288}
                  content={t(
                    '您已修改过模板配置，确认后将和模板解除绑定关系，本次清洗配置将保存并单独生效该索引集，是否确认。',
                  )}
                  trigger='click'
                  on-confirm={handleConfirm}
                >
                  <bk-button
                    class='mr-8'
                    theme='primary'
                    disabled={tableData.value.length === 0}
                  >
                    {hasException.value ? t('忽略冲突并继续填入') : t('确认并填入')}
                  </bk-button>
                </bk-popconfirm>
              ) : (
                <bk-button
                  class='mr-8'
                  theme='primary'
                  disabled={tableData.value.length === 0}
                  on-click={handleConfirm}
                >
                  {hasException.value ? t('忽略冲突并继续填入') : t('确认并填入')}
                </bk-button>
              )}
              <bk-button on-click={handleClose}>{t('取消')}</bk-button>
            </div>
          ),
        }}
      >
        <div
          class='clean-result-preview-dialog'
          v-bkloading={{ isLoading: isDebugLoading.value, size: 'mini' }}
        >
          {/* 调试样例 */}
          <div
            class='log-example-section'
            v-bkloading={{ isLoading: props.logExampleLoading, size: 'mini' }}
          >
            <div class='section-label'>
              <span class='section-label-text'>
                {t('调试样例')}
                <span class='required-mark'>*</span>
              </span>
              {showCollectingTip.value && (
                <span class='collecting-tip'>
                  <InfoTips
                    class='collecting-tip-text'
                    tips={t('采集下发暂未完成，预计需要 1min; 您可以手动填写调试样例或者等待后')}
                  />
                  <span
                    class='refresh-link-text'
                    on-click={handleRefresh}
                  >
                    {t('刷新')}
                  </span>
                </span>
              )}
              <span
                class='refresh-link'
                on-click={handleRefresh}
              >
                <i class='bklog-icon bklog-refresh2' />
              </span>
            </div>
            <bk-input
              class='log-example-textarea'
              type='textarea'
              rows={4}
              value={logExampleText.value}
              on-change={(val: string) => {
                logExampleText.value = val;
              }}
            />
            <bk-button
              class='re-debug-btn'
              disabled={!logExampleText.value || isDebugLoading.value}
              on-click={handleDebug}
            >
              {t('重新调试')}
            </bk-button>
          </div>

          {/* 三个统计卡片 */}
          {hasLoaded.value && (
            <div class='stat-cards'>
              <div class='stat-card'>
                <div class='stat-label'>{t('匹配度')}</div>
                <div class='stat-value is-success'>{successRate.value}%</div>
              </div>
              <div class='stat-card'>
                <div class='stat-label'>{t('冲突字段')}</div>
                <div class='stat-value is-error'>{errorFieldCount.value}</div>
              </div>
              <div class='stat-card'>
                <div class='stat-label'>{t('正常字段')}</div>
                <div class='stat-value is-success'>{normalFieldCount.value}</div>
              </div>
            </div>
          )}

          {/* 冲突说明 alert */}
          <bk-alert
            class='exception-alert'
            type='warning'
          >
            <div
              slot='title'
              class='exception-title'
            >
              <div class='exception-header'>
                {t('如果在下方列表编辑了内容，将自动脱离模板，转为手动配置清洗规则。')}
              </div>
            </div>
          </bk-alert>

          {/* 字段表格 */}
          <TableComponent
            class='preview-fields-table'
            loading={isDebugLoading.value}
            data={tableData.value}
            bordered={true}
            columns={
              previewMode.value === 'template' ? columns.value.filter(col => col.colKey !== 'status') : columns.value
            }
            maxHeight={300}
            skeletonConfig={
              previewMode.value === 'template'
                ? {
                    columns: 5,
                    rows: 2,
                    widths: ['5%', '18%', '15%', '15%', '47%'],
                  }
                : {
                    columns: 6,
                    rows: 2,
                    widths: ['5%', '10%', '18%', '15%', '15%', '37%'],
                  }
            }
          />
        </div>
      </bk-dialog>
    );
  },
});
