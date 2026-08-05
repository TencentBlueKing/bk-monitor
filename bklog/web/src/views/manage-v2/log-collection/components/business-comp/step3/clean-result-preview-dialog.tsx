/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import { defineComponent, ref, computed, watch, onBeforeUnmount, onMounted, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
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
};

/** 预览弹窗内部的字段行 */
type PreviewFieldRow = TemplateFieldItem & {
  /** 前端推断的字段类型（基于 value 推断） */
  inferredType: string;
  /** 字段值（调试返回） */
  value: unknown;
  /** 是否空值异常 */
  empty: boolean;
  /** 是否类型不匹配异常 */
  typeErr: boolean;
  /** 解析状态：'success' | 'error' */
  status: 'success' | 'error';
};

/** 调试接口的字段数据（只有 field_name + value） */
type DebugFieldItem = {
  field_name: string;
  value: unknown;
};

/** int 类型最大值（与父组件保持一致） */
const MAX_INT_VALUE = 2_147_483_647;

/**
 * 根据 value 推断字段类型
 * 规则：
 *  - number 整数 > MAX_INT_VALUE => long，否则 int
 *  - number 非整数 => double
 *  - 纯对象（非数组） => object
 *  - 其他 => string
 */
const detectFieldType = (value: unknown): string => {
  if (typeof value === 'number') {
    if (Number.isInteger(value)) {
      return value > MAX_INT_VALUE ? 'long' : 'int';
    }
    return 'double';
  }
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return 'object';
  }
  return 'string';
};

/** 是否为空值（视为空值异常） */
const isEmptyValue = (value: unknown): boolean => {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  return false;
};

/** 字段类型选项（与原 FieldList 保持一致） */
const FIELD_TYPE_OPTIONS = [
  { id: 'string', name: 'string' },
  { id: 'int', name: 'int' },
  { id: 'long', name: 'long' },
  { id: 'double', name: 'double' },
  { id: 'object', name: 'object' },
];

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
    /** 是否为编辑模式（用于判断是否显示采集下发提示） */
    isEdit: {
      type: Boolean,
      default: false,
    },
    /** 是否为 clone 模式（用于判断是否显示采集下发提示） */
    isClone: {
      type: Boolean,
      default: false,
    },
    /** 是否从清洗列表进入（用于判断是否显示采集下发提示） */
    isCleanField: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['close', 'confirm', 'refresh'],
  setup(props, { emit }) {
    const { t } = useLocale();

    /** 当前显示的日志样例（可编辑） */
    const logExampleText = ref(props.logExample || '');
    /** 表格数据 */
    const tableData = ref<PreviewFieldRow[]>([]);
    /** 调试加载中 */
    const isDebugLoading = ref(false);
    /** 解析成功率（保留 1 位小数） */
    const successRate = ref(0);
    /** 异常字段数（用于 UI 显示） */
    const errorFieldCount = ref(0);
    /** 正常字段数（用于 UI 显示） */
    const normalFieldCount = ref(0);
    /** 是否已有数据（首次调试后展示统计卡片等） */
    const hasLoaded = ref(false);
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
          } else {
            // 没有调试样例时不初始化表格，显示暂无数据
            tableData.value = [];
          }
        } else {
          // 关闭时清空数据
          hasLoaded.value = false;
          tableData.value = [];
        }
      },
      { immediate: true },
    );

    // 模板变化时（如切换父组件模板），同步重建表格
    watch(
      () => props.template?.clean_template_id,
      () => {
        if (props.visible) {
          if (props.template && logExampleText.value) {
            handleDebug();
          } else {
            tableData.value = [];
          }
        }
      },
    );

    // 表格数据变化时，重新初始化 tippy 弹窗
    watch(
      () => tableData.value.length,
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
    });

    /** 仅基于模板初始化表格（不发起调试） */
    const initFromTemplate = () => {
      if (!props.template) {
        tableData.value = [];
        return;
      }
      const rows: PreviewFieldRow[] = (props.template.etl_fields || []).map((f) => {
        const inferredType = f.field_type || 'string';
        return {
          ...f,
          inferredType,
          value: f.value,
          empty: isEmptyValue(f.value),
          typeErr: false,
          status: 'success',
        };
      });
      tableData.value = rows;
      updateStatistics();
    };

    /** 根据调试结果更新统计 */
    const updateStatistics = () => {
      const total = tableData.value.length;
      const errCount = tableData.value.filter(r => r.status === 'error').length;
      const normal = total - errCount;
      errorFieldCount.value = errCount;
      normalFieldCount.value = normal;
      successRate.value = total > 0 ? Number(((normal / total) * 100).toFixed(1)) : 0;
    };

    /**
     * 重新调试
     * - etl_config 取自选中模板的 clean_type
     * - etl_params 按模板类型组装
     * - 返回的字段只有 field_name / value，前端推断类型
     */
    const handleDebug = () => {
      if (!props.template) return;
      const { clean_type, etl_params } = props.template;
      const data: Record<string, unknown> = {
        etl_config: clean_type,
        etl_params: {} as Record<string, unknown>,
        data: logExampleText.value,
      };
      // 按清洗类型组装 etl_params
      if (clean_type === 'bk_log_delimiter') {
        data.etl_params = {
          ...(etl_params || {}),
          separator: (etl_params as any)?.separator ?? '',
        };
      } else if (clean_type === 'bk_log_regexp') {
        data.etl_params = {
          ...(etl_params || {}),
          separator_regexp: (etl_params as any)?.separator_regexp ?? '',
        };
        // 正则模式按父组件逻辑加 bk_biz_id
        data.bk_biz_id = props.bkBizId;
      } else {
        // JSON：直接透传模板的 etl_params
        data.etl_params = { ...(etl_params || {}) };
      }

      isDebugLoading.value = true;
      const urlParams: Record<string, unknown> = {};
      if (!props.isTempField && props.collectorConfigId) {
        urlParams.collector_config_id = props.collectorConfigId;
      }
      const requestUrl = props.isTempField ? 'clean/getEtlPreview' : 'collect/getEtlPreview';

      $http
        .request(requestUrl, { params: urlParams, data })
        .then((res: any) => {
          const dataFields: DebugFieldItem[] = res?.data?.fields || [];
          buildTableFromDebug(dataFields);
          hasLoaded.value = true;
        })
        .catch((err: unknown) => {
          console.warn('清洗结果预览调试失败', err);
          // 失败时使用模板字段回退
          initFromTemplate();
        })
        .finally(() => {
          isDebugLoading.value = false;
        });
    };

    /**
     * 根据调试结果构建表格
     *  - 空值：empty = true（空值异常）
     *  - 类型不匹配：typeErr = true（前端推断类型 vs 模板中字段类型不一致）
     *  - 解析状态：有异常 = error，否则 success
     */
    const buildTableFromDebug = (dataFields: DebugFieldItem[]) => {
      const list: PreviewFieldRow[] = dataFields.map((item) => {
        const inferredType = detectFieldType(item.value);
        const templateField = templateFieldMap.value.get(item.field_name);
        const templateType = templateField?.field_type;
        const empty = isEmptyValue(item.value);
        const typeErr = !!templateType && templateType !== inferredType;
        const status: 'success' | 'error' = empty || typeErr ? 'error' : 'success';
        return {
          field_name: item.field_name || '',
          field_type: templateType || inferredType,
          inferredType,
          value: item.value,
          is_delete: false,
          is_built_in: false,
          is_analyzed: templateField?.is_analyzed ?? false,
          is_case_sensitive: templateField?.is_case_sensitive ?? false,
          tokenize_on_chars: templateField?.tokenize_on_chars ?? '',
          empty,
          typeErr,
          status,
        };
      });
      tableData.value = list;
      updateStatistics();
    };

    /** 编辑字段名 */
    const handleFieldNameChange = (row: PreviewFieldRow, value: string) => {
      row.field_name = value;
    };

    /** 编辑字段类型 */
    const handleTypeChange = (row: PreviewFieldRow, value: string) => {
      row.field_type = value;
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
                <div>{t('大小写敏感')}: {row.is_case_sensitive ? t('是') : t('否')}</div>
              </div>
            ) : (
              <span>{t('不分词')}</span>
            )}
            <i class='select-angle bk-icon icon-angle-down' />
          </span>
          <div style={{ display: 'none' }} class='word-breaker-popover'>
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
                      disabled={!cacheData.value.is_analyzed && option.id === 'custom'}
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
                <bk-button size='small' on-click={handleWordBreakerCancelClick}>
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
        } catch (_) {}
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

    /** 忽略异常并继续填入 */
    const handleConfirm = () => {
      const resultFields = tableData.value.map(row => ({
        field_name: row.field_name,
        field_type: row.field_type,
        value: row.value,
        is_delete: row.is_delete,
        is_built_in: row.is_built_in,
        is_analyzed: row.is_analyzed,
        is_case_sensitive: row.is_case_sensitive,
        tokenize_on_chars: row.tokenize_on_chars,
      }));
      emit('confirm', resultFields, logExampleText.value);
    };

    /** 是否存在异常（用于控制异常 alert 显示） */
    const hasException = computed(() => errorFieldCount.value > 0);

    /** 是否显示"采集下发暂未完成"提示：编辑/克隆/清洗列表进入 且 尚无调试样例 */
    const showCollectingTip = computed(
      () => (props.isEdit || props.isClone || props.isCleanField) && !logExampleText.value,
    );

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
          // 构建异常原因 tooltip 内容
          const buildStatusErrorTips = () => {
            const reasons: string[] = [];
            if (row.empty) {
              reasons.push(t('message 捕获组未命中 key=value 片段'));
            }
            if (row.typeErr) {
              reasons.push(t('类型不匹配'));
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
              <span>{row.status === 'error' ? t('异常') : t('成功')}</span>
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
              {FIELD_TYPE_OPTIONS.map(opt => (
                <bk-option
                  key={opt.id}
                  id={opt.id}
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
            {row.empty
              ? <span class='value-empty'>{t('空值')}</span>
              : <span class='value-text'>{formatDisplayValue(row.value)}</span>}
            {row.empty && (
              <i
                class='bk-icon icon-exclamation-circle-shape value-empty-icon'
                v-bk-tooltips={{ content: t('message 捕获组未命中 key=value 片段'), placement: 'top' }}
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
        ok-text={hasException.value ? t('忽略异常并继续填入') : t('确认并填入')}
        on-value-change={handleDialogValueChange}
        on-confirm={handleConfirm}
        on-closed={handleClose}
      >
        <div
          class='clean-result-preview-dialog'
          v-bkloading={{ isLoading: isDebugLoading.value, size: 'mini' }}
        >
          {/* 调试样例 */}
          <div class='log-example-section'>
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
                <div class='stat-label'>{t('异常字段')}</div>
                <div class='stat-value is-error'>{errorFieldCount.value}</div>
              </div>
              <div class='stat-card'>
                <div class='stat-label'>{t('正常字段')}</div>
                <div class='stat-value is-success'>{normalFieldCount.value}</div>
              </div>
            </div>
          )}

          {/* 异常说明 alert */}
          {hasException.value && (
            <bk-alert
              class='exception-alert'
              type='warning'
            >
              <div
                slot='title'
                class='exception-title'
              >
                <div class='exception-header'>{t('如果在下方列表编辑了内容，将自动脱离模版，转为手动配置清洗规则。')}</div>
              </div>
            </bk-alert>
          )}

          {/* 字段表格 */}
          <TableComponent
            class='preview-fields-table'
            loading={isDebugLoading.value}
            data={tableData.value}
            bordered={true}
            columns={columns.value}
            maxHeight={300}
            skeletonConfig={{
              columns: 6,
              rows: 2,
              widths: ['5%', '10%', '18%', '15%', '15%', '37%'],
            }}
          />
        </div>
      </bk-dialog>
    );
  },
});
