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

import { defineComponent, ref, computed, onBeforeUnmount, onMounted, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import tippy, { type Instance } from 'tippy.js';

import './field-list.scss';
export type FieldItem = {
  field_index: number;
  field_name: string;
  alias_name?: string;
  alias_name_show?: boolean;
  field_type: string;
  previous_type?: string;
  description?: string;
  value?: any;
  is_built_in: boolean;
  is_add_in: boolean;
  is_objectKey: boolean;
  is_delete: boolean;
  is_time: boolean;
  is_analyzed: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars?: string;
  participleState: 'custom' | 'default';
  children?: FieldItem[];
  expand?: boolean;
  verdict?: boolean;
  fieldErr?: string;
  typeErr?: boolean;
  aliasErr?: boolean | string;
  fieldAliasErr?: string;
  btnShow?: boolean;
  width?: number;
};

// 全局配置类型
export type GlobalsData = {
  field_data_type: Array<{ id: string; name: string }>;
  field_built_in: Array<{ id: string }>;
  retain_extra_json?: boolean;
};

// Props类型定义
export type Props = {
  isEditJson?: boolean;
  tableType: 'edit' | 'preview';
  extractMethod: 'bk_log_delimiter' | 'bk_log_json' | 'bk_log_regexp';
  deletedVisible: boolean;
  fields: FieldItem[];
  isTempField: boolean;
  isExtracting: boolean;
  originalTextTokenizeOnChars: string;
  retainExtraJson: boolean;
  builtFieldShow: boolean;
  selectEtlConfig: 'bk_log_delimiter' | 'bk_log_json' | 'bk_log_regexp';
  isSetDisabled: boolean;
};
/**
 * @file 字段列表
 */
export default defineComponent({
  name: 'FieldList',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
    tableType: {
      type: String,
      default: 'edit',
      validator: (v: string) => ['edit', 'preview'].includes(v),
    },
    originalTextTokenizeOnChars: {
      type: String,
      default: '',
    },
    retainExtraJson: {
      type: Boolean,
      default: false,
    },
    builtFieldShow: {
      type: Boolean,
      default: false,
    },
    selectEtlConfig: {
      type: String,
      default: 'bk_log_json',
      validator: (v: string) => ['bk_log_json', 'bk_log_delimiter', 'bk_log_regexp'].includes(v),
    },
    isSetDisabled: {
      type: Boolean,
      default: false,
    },
    extractMethod: {
      type: String,
      default: 'bk_log_json',
      validator: (v: string) => ['bk_log_json', 'bk_log_delimiter', 'bk_log_regexp'].includes(v),
    },
  },
  emits: [''],

  setup(props) {
    // 最大 int 类型值
    const MAX_INT_VALUE = 2_147_483_647;
    const { t } = useLocale();
    const store = useStore();
    const typeKey = ref('visible');
    const showBuiltIn = ref(false);
    let tippyInstances: Instance[] = [];
    const formData = ref({ tableList: [] as FieldItem[] });
    // 获取全局数据
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const isPreviewMode = computed(() => props.tableType === 'preview');
    const isAdd = computed(() => props.selectEtlConfig === 'bk_log_json');
    const currentParticipleState = ref('default');
    const currentTokenizeOnChars = ref('');
    // 分词选项列表
    const participleList = [
      {
        id: 'default',
        name: t('自然语言分词'),
        placeholder: t('自然语言分词，按照日常语法习惯进行分词'),
      },
      {
        id: 'custom',
        name: t('自定义'),
        placeholder: t('支持自定义分词符，可按需自行配置符号进行分词'),
      },
    ];
    /**
     * 来源render
     * @param row
     * @returns
     */
    const renderSource = (row: any) => {
      const info = row.is_add_in
        ? { label: t('添加'), class: 'source-add' }
        : { label: t('调试'), class: 'source-debug' };
      const sourceInfo = row.is_built_in ? { label: t('内置'), class: 'source-built' } : info;

      return <span class={`source-box ${sourceInfo.class}`}>{sourceInfo.label}</span>;
    };

    /**
     * 分词类型变更
     * @param state
     */
    const handleChangeParticipleState = (state: string) => {
      currentParticipleState.value = state;
      currentTokenizeOnChars.value = state === 'custom' ? props.originalTextTokenizeOnChars : '';
    };
    /**
     * 取消分词符popover
     */
    const handleWordBreakerCancelClick = () => {
      // 关闭 tippy
      tippyInstances.forEach(i => i?.hide());
    };
    /**
     * 分词符render
     * @param row
     * @returns
     */
    const renderWordBreaker = (row: any) => {
      if (row.field_type === 'string' && !row.is_built_in) {
        return (
          <span>
            <span class='word-breaker word-breaker-edit'>
              {row.word_breaker}
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
                    // v-model={currentIsAnalyzed.value}
                    // disabled={getCustomizeDisabled(props.row, 'analyzed')}
                    theme='primary'
                    // on-change={handelChangeAnalyzed}
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
                        data-test-id={`fieldExtractionBox_button_filterMethod${option.id}`}
                        size='small'
                        // disabled={getCustomizeDisabled(props.row)}
                        on-click={() => handleChangeParticipleState(option.id)}
                      >
                        {option.name}
                      </bk-button>
                    ))}
                  </div>
                  {currentParticipleState.value === 'custom' && (
                    <bk-input
                      class='custom-input'
                      // v-model={currentTokenizeOnChars.value}
                      // disabled={getCustomizeDisabled(props.row)}
                    />
                  )}
                </div>
                <div class='menu-item'>
                  <span class='menu-item-label'>{t('大小写敏感')}</span>
                  <bk-switcher
                    // v-model={currentIsCaseSensitive.value}
                    // disabled={getCustomizeDisabled(props.row)}
                    theme='primary'
                  />
                </div>
                <div class='menu-footer'>
                  <bk-button
                    size='small'
                    theme='primary'
                  >
                    {t('确定')}
                  </bk-button>
                  <bk-button
                    size='small'
                    onClick={handleWordBreakerCancelClick}
                  >
                    {t('取消')}
                  </bk-button>
                </div>
              </div>
            </div>
          </span>
        );
      }
      return <span class='disabled-work'>{t('无需设置')}</span>;
    };
    /**
     * 值 render
     * @param row
     * @returns
     */
    const renderValue = (row: any) => {
      if (!row.is_built_in) {
        return <span class='word-breaker bg-gray'>{String(row.is_built_in)}</span>;
      }
      return <span class='disabled-work'>{t('暂无预览')}</span>;
    };
    /**
     * 渲染分词符的popover
     * @returns
     */
    const initMenuPop = () => {
      // 销毁旧实例，避免重复绑定
      destroyTippyInstances();

      const targets = document.querySelectorAll('.fields-table-box .bk-table-body-wrapper .word-breaker-edit');
      if (!targets.length) {
        return;
      }

      const instances = tippy(targets as unknown as HTMLElement[], {
        trigger: 'click',
        placement: 'top',
        theme: 'light word-breaker-theme-popover',
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
        onShow(instance) {
          (instance.reference as HTMLElement).classList.add('is-hover');
        },
        onHide(instance) {
          (instance.reference as HTMLElement).classList.remove('is-hover');
        },
        content(reference) {
          const btn = reference as HTMLElement;
          // 约定：内容紧跟在按钮后的兄弟元素中
          const container = btn.nextElementSibling as HTMLElement | null;
          const contentNode = container?.querySelector('.word-breaker-menu-content') as HTMLElement | null;
          return (contentNode ?? container ?? document.createElement('div')) as unknown as Element;
        },
      });

      // tippy 返回单个或数组，这里统一转为数组
      tippyInstances = Array.isArray(instances) ? instances : [instances];
    };
    /** 销毁所有tippy */
    const destroyTippyInstances = () => {
      // biome-ignore lint/complexity/noForEach: <explanation>
      tippyInstances.forEach(i => {
        try {
          i.hide();
          i.destroy();
        } catch (_) {}
      });
      tippyInstances = [];
    };
    onMounted(() => {
      nextTick(() => {
        initMenuPop();
      });
    });
    onBeforeUnmount(() => {
      destroyTippyInstances();
    });
    /**
     * 刷新值
     */
    const handleFreshValue = () => {
      console.log('刷新值');
    };

    /**
     * 当前字段类型是否禁用
     * @param row
     * @param option
     * @returns
     */
    const isTypeDisabled = (row, option) => {
      if (row.verdict) {
        // 不是数值，相关数值类型选项被禁用
        return ['int', 'long', 'double', 'float'].includes(option.id);
      }
      // 是数值，如果值大于 MAX_INT_VALUE 即 2^31 - 1，int 选项被禁用
      return option.id === 'int' && row.value > MAX_INT_VALUE;
    };

    /**
     * 展开/折叠对象字段
     * @param row
     * @param show
     */
    const expandObject = (row: FieldItem, show: boolean) => {
      row.expand = show;
      const index = formData.value.tableList.findIndex(item => item.field_name === row.field_name);

      if (show && index !== -1) {
        formData.value.tableList.splice(index + 1, 0, ...(row.children || []));
      } else if (!show && index !== -1) {
        const childrenCount = row.children?.length || 0;
        formData.value.tableList.splice(index + 1, childrenCount);
      }
    };

    /**
     * 检查字段编辑是否禁用
     * @param row
     * @returns
     */
    const getFieldEditDisabled = (row: FieldItem) => {
      if (row.is_delete || row.is_built_in || row.field_type === 'object') {
        return true;
      }
      if (props.selectEtlConfig === 'bk_log_json') {
        return false;
      }
      return props.extractMethod !== 'bk_log_delimiter' || !!props.isSetDisabled;
    };
    /**
     * 字段名render
     * @param row
     * @returns
     */
    const renderFieldName = row => {
      console.log('row', row);
      if (isPreviewMode.value || row.is_objectKey) {
        return (
          <div
            class='overflow-tips-field-name'
            v-bk-tooltips={{ content: row.field_name, placement: 'top' }}
          >
            {row.is_objectKey && <span class='ext-btn bklog-icon bklog-subnode' />}
            <span>{row.field_name}</span>
          </div>
        );
      }
      return (
        <div
          class={{
            'is-required is-error': row.fieldErr,
            'disable-background': row.is_built_in,
            'participle-form-item': true,
          }}
        >
          {row.field_type === 'object' && row.children?.length && !row.expand && (
            <span
              class='ext-btn rotate bklog-icon bklog-arrow-down-filled'
              on-click={() => expandObject(row, true)}
            />
          )}
          {row.field_type === 'object' && row.children?.length && row.expand && (
            <span
              class='ext-btn bklog-icon bklog-arrow-down-filled'
              on-click={() => expandObject(row, false)}
            />
          )}

          {row.is_built_in && row.alias_name ? (
            <bk-input
              class='participle-field-name-input-pl5'
              value={row.field_name}
              // disabled={() => getFieldEditDisabled(row)}
              // on-blur={() => checkFieldNameItem(row)}
            />
          ) : (
            <bk-input
              class={{
                'participle-field-name-input': row.alias_name || row.alias_name_show,
                // 'participle-field-name-input-pl5': true,
              }}
              value={row.field_name}
              // disabled={() => getFieldEditDisabled(row)}
              // on-blur={() => checkFieldNameItem(row)}
            />
          )}
          {(row.alias_name || row.alias_name_show) && !row.is_built_in && (
            <span class={{ 'participle-icon': true, 'participle-icon-color': getFieldEditDisabled(row) }}>
              <i
                style='color: #3a84ff;'
                class='bk-icon bklog-icon bklog-yingshe'
              />
            </span>
          )}
          {(row.alias_name || row.alias_name_show) && !row.is_built_in && (
            <bk-input
              class='participle-alias-name-input'
              // disabled={() => getFieldEditDisabled(row)}
              placeholder={t('请输入映射名')}
              value={row.alias_name}
              // on-blur={() => checkAliasNameItem(row)}
            />
          )}

          {row.fieldErr && !row.btnShow && (
            <i
              style='right: 8px'
              class='bk-icon icon-exclamation-circle-shape tooltips-icon'
              v-bk-tooltips={{ content: row.fieldErr, placement: 'top' }}
            />
          )}

          {props.selectEtlConfig === 'bk_log_json' && row.fieldAliasErr && !row.alias_name && !row.alias_name_show && (
            // {props.selectEtlConfig === 'bk_log_json' && (
            <bk-button
              class='tooltips-btn'
              // on-click={() => handlePopoverRename(row)}
              v-bk-tooltips={{
                width: row.width,
                content: row.fieldAliasErr || t('点击定义字段名映射'),
                placement: 'top',
              }}
              theme='danger'
            >
              {t('字段映射')}
            </bk-button>
          )}
        </div>
      );
      // return (
      //   <bk-input
      //     disabled={row.is_built_in}
      //     value={row.field_name}
      //   />
      // );
    };

    /**
     * 绘制表头
     * @param h
     * @param param1
     * @param item
     * @returns
     */
    const renderHeader = (h, { column }, item) => {
      if (item.key === 'value') {
        return (
          <span class='header-text'>
            {item.label}
            <span
              class='header-text-link'
              on-click={handleFreshValue}
            >
              <i class='bklog-icon bklog-refresh2 link-icon' />
              {t('刷新')}
            </span>
          </span>
        );
      }
      return <span class='header-text'>{column.label}</span>;
    };

    const columns = ref([
      {
        label: t('来源'),
        prop: 'collector_config_name',
        align: 'center',
        width: 62,
        renderFn: renderSource,
      },
      {
        label: t('字段名'),
        prop: 'field_name',
        renderFn: renderFieldName,
      },
      // {
      //   label: t('别名'),
      //   prop: 'alias_name',
      //   renderFn: (row: any) => (
      //     <bk-input
      //       disabled={row.is_built_in}
      //       value={row.alias_name}
      //     />
      //   ),
      // },
      {
        label: t('类型'),
        prop: 'field_type',
        renderFn: (row: any) => (
          <bk-select
            clearable={false}
            disabled={row.is_built_in}
            value={row.field_type}
          >
            {(globalsData.value.field_data_type || []).map(option => (
              <bk-option
                id={option.id}
                key={option.id}
                // disabled={() => isTypeDisabled(row, option)}
                name={option.name}
              />
            ))}
          </bk-select>
        ),
      },
      {
        label: t('分词符'),
        prop: 'collector_config_name',
        renderFn: renderWordBreaker,
      },
      {
        label: t('值'),
        key: 'value',
        prop: 'is_built_in',
        renderFn: renderValue,
      },
    ]);
    const handleType = (type: string) => {
      typeKey.value = type;
    };

    const renderTab = () => (
      <div class='tab-list'>
        <span
          class={{
            'tab-item': true,
            'is-selected': typeKey.value === 'visible',
          }}
          on-Click={() => handleType('visible')}
        >
          {t('可见字段')}
          {` (${visibleData.value.length})`}
        </span>
        <span
          class={{
            'tab-item': true,
            'is-selected': typeKey.value === 'invisible',
          }}
          on-Click={() => handleType('invisible')}
        >
          {t('被隐藏字段')}
          {` (${invisibleData.value.length})`}
        </span>
      </div>
    );
    /**
     * 可见字段
     */
    const visibleData = computed(() => {
      return props.data.filter(item => !item.is_delete);
    });
    /**
     * 被隐藏字段
     */
    const invisibleData = computed(() => {
      return props.data.filter(item => item.is_delete);
    });
    const showData = computed(() => {
      return typeKey.value === 'visible' ? visibleData.value : invisibleData.value;
    });

    /**
     * 是否显示内置字段
     */
    const showTableList = computed(() => {
      return showBuiltIn.value ? showData.value : showData.value.filter(item => !item.is_built_in);
    });

    const handleShowBuiltIn = () => {
      showBuiltIn.value = !showBuiltIn.value;
    };
    /**
     * 删除字段
     * @param row 行数据
     */
    const deleteField = row => {
      console.log(row);
    };
    /**
     * 字段表格
     * @returns
     */
    const renderTable = () => (
      <div class='fields-table'>
        <bk-table
          ext-cls='fields-table-box'
          data={showTableList.value}
          col-border
        >
          {columns.value.map((item, ind) => (
            <bk-table-column
              key={`${item.prop}_${ind}`}
              width={item.width}
              scopedSlots={{
                default: ({ row }) => {
                  /** 自定义 */
                  if (item?.renderFn) {
                    return (item as any)?.renderFn(row);
                  }
                  return row[item.prop] ?? '--';
                },
              }}
              align={item.align || 'left'}
              class-name={item?.renderFn ? 'fields-table-column' : ''}
              label={item.label}
              prop={item.prop}
              renderHeader={(h, { column, $index }: any) => renderHeader(h, { column, $index }, item)}
            />
          ))}
          <bk-table-column
            width={70}
            scopedSlots={{
              default: ({ row }) => {
                return (
                  <div class='table-operation'>
                    <i
                      class={`bklog-icon bklog-${row.is_delete ? 'visible' : 'invisible'} icons`}
                      v-bk-tooltips={row.is_delete ? t('复原') : t('隐藏')}
                    />
                    {row.is_add_in && (
                      <i
                        class='bklog-icon bklog-log-delete icons del-icon'
                        v-bk-tooltips={t('删除')}
                        on-click={() => deleteField(row)}
                      />
                    )}
                  </div>
                );
              },
            }}
            label={t('操作')}
          />
        </bk-table>
      </div>
    );
    /**
     * 新增字段
     */
    const handleAddField = () => {
      console.log('新增字段', showTableList.value);
    };

    return () => (
      <div class='field-list-main-box'>
        <div class='tab-box'>
          {renderTab()}
          <span class='checkbox-box'>
            <bk-checkbox
              class='mr-5'
              value={showBuiltIn.value}
              on-change={handleShowBuiltIn}
            />
            {t('显示内置字段')}
          </span>
        </div>
        {renderTable()}
        {isAdd.value && (
          <div class='example-box'>
            <span
              class='form-link'
              on-click={handleAddField}
            >
              <i class='bk-icon icon-plus link-icon add-btn' />
              {t('新增字段')}
            </span>
          </div>
        )}
      </div>
    );
  },
});
