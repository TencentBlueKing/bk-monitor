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

import { defineComponent, ref, onMounted, computed } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';
import { useOperation } from '../../hook/useOperation';
import { showMessage } from '../../utils';
import FieldList from '../business-comp/step3/field-list';
import ReportLogSlider from '../business-comp/step3/report-log-slider';
import InfoTips from '../common-comp/info-tips';
import $http from '@/api';

import type { ISelectItem } from '../../utils';

import './step3-clean.scss';

export default defineComponent({
  name: 'StepClean',
  props: {
    configData: {
      type: Object,
      default: () => ({}),
    },
    scenarioId: {
      type: String,
      default: '',
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为清洗模版
     */
    isTempField: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为clone模式
     */
    isClone: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();
    const route = useRoute();
    const defaultRegex = '(?P<request_ip>[d.]+)[^[]+[(?P<request_time>[^]]+)]';
    const { cardRender } = useOperation();
    const showReportLogSlider = ref(false);
    const jsonText = ref({});
    const fieldListRef = ref();

    const templateDialogVisible = ref(false);
    const templateName = ref('');
    /**
     * 应用模版前缓存之前填写的内容，方便后续重置
     */
    const cacheTemplateData = ref();
    /**
     * 清洗模式 - 分隔符 - 选中的分隔符
     */
    const delimiter = ref();

    const basicLoading = ref(false);
    /**
     * 指定日志时间校验报错信息
     */
    const timeCheckErrContent = ref('');
    /**
     * 路径元数据 - 路径样例
     */
    const pathExample = ref();
    const isDebugLoading = ref(false);
    /**
     * 日志样例
     */
    const logOriginal = ref('');
    const copyBuiltField = ref([]);
    const originParticipleState = ref('default');
    const cleaningModeList = [
      {
        label: t('JSON'),
        value: 'bk_log_json',
      },
      {
        label: t('分隔符'),
        value: 'bk_log_delimiter',
      },
      {
        label: t('正则表达式'),
        value: 'bk_log_regexp',
      },
    ];
    /**
     * 分词列表
     */
    const participleList = [
      {
        id: 'default',
        name: t('自然语言分词'),
      },
      {
        id: 'custom',
        name: t('自定义'),
      },
    ];
    const cleaningMode = ref('bk_log_json');
    const enableMetaData = ref(false);
    const loading = ref(false);
    const logOriginalLoading = ref(false);
    /**
     * 是否刷新值
     */
    const isValueRefresh = ref(false);
    /**
     * 模版列表
     */
    const templateList = ref([]);
    const templateListLoading = ref(false);

    const builtInFieldsList = ref([]);
    const defaultParticipleStr = ref('@&()=\'",;:<>[]{}/ \\n\\t\\r\\\\');
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const curCollect = computed(() => store.getters['collect/curCollect']);
    const bkBizId = computed(() => store.getters.bkBizId);
    /**
     * 分隔符
     */
    const globalDataDelimiter = computed<ISelectItem[]>(() => globalsData.value?.data_delimiter || []);
    /**
     * 时间格式
     */
    const fieldDateFormat = computed(() => globalsData.value?.field_date_format || []);
    /**
     * 时区
     */
    const timeZone = computed(() => (globalsData.value?.time_zone || []).toReversed());

    /**
     * 是否为编辑
     */
    const isUpdate = computed(() => route.name === 'collectEdit' && props.isEdit);

    const formData = ref({
      // 最后一次正确的结果，保存以此数据为准
      table_id: '',
      etl_config: 'bk_log_json',
      etl_params: {
        retain_original_text: true,
        original_text_is_case_sensitive: false,
        original_text_tokenize_on_chars: '',
        separator_regexp: '',
        separator: '',
        retain_extra_json: false,
        enable_retain_content: true, // 保留失败日志
        path_regexp: '', // 采集路径分割的正则
        metadata_fields: [],
      },
      etl_fields: [],
      fields: [],
      visible_type: 'current_biz', // 可见范围单选项
      visible_bk_biz: [], // 多个业务
      log_original: '',
      log_reporting_time: true, // 日志上报时间
      field_name: '',
      time_format: '',
      time_zone: '',
    });
    const copyText = ref({});
    const rowTemplate = ref({
      alias_name: '',
      description: '',
      field_type: '',
      is_case_sensitive: false,
      is_analyzed: false,
      is_built_in: false,
      is_delete: false,
      is_dimension: false,
      is_time: false,
      value: '',
      option: {
        time_format: '',
        time_zone: '',
      },
      // 是否是自定义分词
      tokenize_on_chars: '',
      participleState: 'default',
    });

    const showDebugPathRegexBtn = computed(() => formData.value.etl_params.path_regexp && pathExample.value);

    onMounted(() => {
      setDetail();
      getTemplate();
    });
    /**
     * 获取模版列表
     * @param isSave
     */
    const getTemplate = () => {
      templateListLoading.value = true;
      $http
        .request('clean/cleanTemplate', {
          query: {
            bk_biz_id: bkBizId.value,
          },
        })
        .then(res => {
          templateListLoading.value = false;
          if (res.data) {
            templateList.value = res.data;
          }
        });
    };
    const getCleanStash = async (id: number) => {
      try {
        const res = await $http.request('clean/getCleanStash', {
          params: {
            collector_config_id: id,
          },
        });
        if (res.data) {
          const { etl_fields, clean_type, etl_params } = res.data;
          const timeField = etl_fields?.find(item => item.is_time);
          const logReportingTime = !timeField; // 如果存在is_time为true的字段，则log_reporting_time为false
          const fieldName = timeField?.field_name || '';
          cleaningMode.value = clean_type;
          formData.value = {
            ...formData.value,
            ...res.data,
            log_reporting_time: logReportingTime,
            field_name: fieldName,
          };
          if (cleaningMode.value === 'bk_log_delimiter') {
            delimiter.value = etl_params.separator;
          }
          return;
        }
        formData.value.etl_params.retain_original_text = true;
        formData.value.etl_params.enable_retain_content = true;
      } catch (error) {
        console.log(error);
      }
    };

    // 新建、编辑采集项时获取更新详情
    const setDetail = () => {
      /**
       * 初始化导入的配置
       */
      builtInFieldsList.value = (props.configData.etl_fields || []).filter(item => item.is_built_in);
      const eltField = (props.configData.etl_fields || []).filter(item => !item.is_built_in);
      formData.value = {
        ...formData.value,
        ...props.configData,
        etl_fields: eltField,
      };
      const id = isUpdate.value ? route.params.collectorId : route.query.collectorId;
      if (!id) {
        return;
      }
      basicLoading.value = true;
      $http
        .request('collect/details', {
          params: { collector_config_id: id },
        })
        .then(async res => {
          if (res.data) {
            store.commit('collect/setCurCollect', res.data);
            builtInFieldsList.value = curCollect.value.fields.filter(item => item.is_built_in);
            if (props.isEdit || props.isClone) {
              getDataLog('init');
              await getCleanStash(id);
            }
          }
        })
        .finally(() => {
          basicLoading.value = false;
        });
    };
    /**
     * 路径元数据 - 调试按钮
     */
    const debuggerPathRegex = () => {
      const data = {
        etl_config: 'bk_log_regexp',
        etl_params: {
          separator_regexp: formData.value.etl_params?.path_regexp,
        },
        data: pathExample.value,
      };
      const urlParams = {};
      isDebugLoading.value = true;
      urlParams.collector_config_id = curCollect.value.collector_config_id;
      const updateData = { params: urlParams, data };
      // 先置空防止接口失败显示旧数据
      formData.value.etl_params.metadata_fields = [];
      $http
        .request('collect/getEtlPreview', updateData)
        .then(res => {
          const fields = res.data?.fields || [];
          formData.value.etl_params?.metadata_fields.push(...fields);
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          isDebugLoading.value = false;
        });
    };

    const judgeNumber = val => {
      const { value } = val;
      if (value === 0) {
        return false;
      }

      return value && value !== ' ' ? isNaN(value) : true;
    };
    /**
     * 清洗模式 - 清洗/调试按钮
     */
    const debugHandler = (type = 'default') => {
      const isRefresh = type === 'refresh';
      const { etl_params } = formData.value;
      const data = {
        etl_config: cleaningMode.value,
        etl_params: {},
        data: logOriginal.value,
      };
      if (cleaningMode.value === 'bk_log_delimiter') {
        data.etl_params.separator = delimiter.value;
      }
      if (cleaningMode.value === 'bk_log_regexp') {
        data.etl_params.separator_regexp = etl_params.separator_regexp;
      }
      let requestUrl = 'clean/getEtlPreview';
      const urlParams = {};
      isDebugLoading.value = !isRefresh;
      isValueRefresh.value = isRefresh;
      /**
       * 非刷新场景下才清空表格数据
       */
      if (!isRefresh) {
        formData.value.etl_fields = [];
      }
      // 先置空防止接口失败显示旧数据
      formData.value.etl_params.metadata_fields = [];
      if (props.isTempField) {
        requestUrl = 'clean/getEtlPreview';
      } else {
        urlParams.collector_config_id = curCollect.value.collector_config_id;
        requestUrl = 'collect/getEtlPreview';
      }
      const updateData = { params: urlParams, data };
      $http
        .request(requestUrl, updateData)
        .then(res => {
          const dataFields = res.data.fields;
          const validFieldPattern = /^[A-Za-z_][0-9A-Za-z_]*$/;
          for (const item of dataFields) {
            if (item.field_name && !validFieldPattern.test(item.field_name)) {
              item.field_name = JSON.stringify(item.field_name);
            }
            item.verdict = judgeNumber(item);
          }
          const fields = formData.value.etl_fields;
          const list = dataFields.reduce((arr, item) => {
            const field = { ...structuredClone(rowTemplate.value), ...item };
            arr.push(field);
            return arr;
          }, []);
          /**
           * 当只刷新值的时候，只更新对应字段的值
           */
          if (isRefresh) {
            formData.value.etl_fields = fields.map(item => {
              const info = list.find(ele => ele.field_name === item.field_name);
              return {
                ...item,
                value: info.value,
              };
            });
            return;
          }
          /**
           * 当点击调试/清洗按钮的，更新字段表格里的所有内容
           */
          formData.value.etl_fields = list;
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          isDebugLoading.value = false;
          isValueRefresh.value = false;
        });
    };
    /** 根据清洗模式，渲染不同的内容 */
    const renderCleaningMode = () => {
      /**
       * Json
       */
      if (cleaningMode.value === 'bk_log_json') {
        return (
          <bk-button
            class='clean-btn'
            disabled={!logOriginal.value}
            on-click={debugHandler}
          >
            {t('清洗')}
          </bk-button>
        );
      }
      /**
       * 分隔词
       */
      if (cleaningMode.value === 'bk_log_delimiter') {
        return (
          <div class='separator-box select-group'>
            <div class='select-item'>
              <span class='select-title'>{t('分隔符')}</span>
              <bk-select
                class='select-box'
                clearable={false}
                value={delimiter.value}
                on-change={(val: string) => {
                  delimiter.value = val;
                  formData.value.etl_params.separator = val;
                }}
              >
                {globalDataDelimiter.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </div>
            <bk-button
              class='clean-btn'
              disabled={!logOriginal.value || !delimiter.value}
              on-click={debugHandler}
            >
              {t('调试')}
            </bk-button>
          </div>
        );
      }
      /**
       * 正则表达式
       */
      if (cleaningMode.value === 'bk_log_regexp') {
        return (
          <div class='regex-box-main'>
            <div class='title'>
              {t('正则表达式')}
              <i
                class='bk-icon icon-info-circle tips-icon'
                v-bk-tooltips={{
                  placement: 'right',
                  content: `${t(
                    '正则表达式(golang语法)需要匹配日志全文，如以下DEMO将从日志内容提取请求时间与内容',
                  )}<br />${t(' - 日志内容：[2006-01-02 15:04:05] content')}<br /> ${t(
                    ' - 表达式：',
                  )} \[(?P<request_time>[^]]+)\] (?P<content>.+)`,
                }}
              />
            </div>
            <bk-input
              placeholder={'(?P<request_ip>[d.]+)[^[]+[(?P<request_time>[^]]+)]'}
              type='textarea'
              value={formData.value.etl_params.separator_regexp}
              on-change={(val: string) => {
                formData.value.etl_params.separator_regexp = val;
              }}
            />
            <bk-button
              class='clean-btn'
              disabled={!(logOriginal.value && formData.value.etl_params.separator_regexp)}
              on-click={debugHandler}
            >
              {t('调试')}
            </bk-button>
          </div>
        );
      }
    };

    /**
     * 获取清洗的相关信息，如日志样例、上报日志（origin字段）
     * @param type
     */
    const getDataLog = (type: string) => {
      logOriginalLoading.value = type === 'refresh';
      $http
        .request('source/dataList', {
          params: {
            collector_config_id: curCollect.value.collector_config_id,
          },
        })
        .then(res => {
          if (res.data?.length) {
            copyText.value = Object.assign(res.data[0].etl, res.data[0].etl.items[0]) || {};
            const data = res.data[0];
            jsonText.value = data.origin || {};
            pathExample.value = jsonText.value.filename;
            logOriginal.value = data.etl.data || '';
            // biome-ignore lint/complexity/noForEach: <explanation>
            copyBuiltField.value.forEach(item => {
              const fieldName = item.field_name;
              if (fieldName) {
                item.value = copyText.value[fieldName];
              }
            });
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          logOriginalLoading.value = false;
        });
    };
    /**
     * 应用模版
     * @param item
     */
    const applyTemplate = item => {
      const { etl_params, etl_fields, clean_type } = item;
      cacheTemplateData.value = { ...formData.value };
      formData.value = {
        ...formData.value,
        etl_params,
        etl_fields,
        clean_type,
      };
    };

    /**
     * 另存为模版确认
     *
     */
    const handleTempConfirm = () => {
      if (templateName.value.trim() === '') {
        showMessage(t('请输入模板名称'), 'error');
        return;
      }
      $http
        .request('clean/createTemplate', {
          data: {
            name: templateName.value,
            bk_biz_id: bkBizId.value,
            clean_type: cleaningMode.value,
            etl_params: formData.value.etl_params,
            etl_fields: formData.value.etl_fields,
          },
        })
        .then(res => {
          if (res.result) {
            templateDialogVisible.value = false;
            getTemplate();
            showMessage(t('保存成功'), 'success');
          }
        })
        .catch(() => {
          showMessage(t('保存失败'), 'error');
        });
    };
    /**
     * 应用模版下拉框
     *
     */
    const renderTemplateSelect = () => (
      <bk-select
        class='template-select'
        ext-popover-cls={'template-select-popover'}
        loading={templateListLoading.value}
        searchable
      >
        <span
          class='form-link'
          slot='trigger'
        >
          <i class='bklog-icon bklog-app-store link-icon' />
          {t('应用模板')}
        </span>
        {templateList.value.map(item => (
          <bk-option
            id={item.clean_template_id}
            key={item.clean_template_id}
            name={item.name}
          >
            <div class='template-option'>
              <span class='option-name'>{item.name}</span>{' '}
              <span
                class='option-btn'
                on-click={() => applyTemplate(item)}
              >
                {t('应用')}
              </span>
            </div>
          </bk-option>
        ))}
      </bk-select>
    );

    /** 选择清洗模式 */
    const handleChangeCleaningMode = (mode: string) => {
      cleaningMode.value = mode.value;
    };

    // 对时间格式做校验逻辑
    const requestCheckTime = async () => {
      const { time_format, time_zone, field_name } = formData.value;
      const fieldsData = formData.value.etl_fields;
      const timeValueItem = fieldsData.find(item => field_name === item.field_name);
      let result = false;
      await $http
        .request('collect/getCheckTime', {
          params: {
            collector_config_id: curCollect.value.collector_config_id,
          },
          data: {
            time_format,
            time_zone,
            data: timeValueItem?.value || '',
          },
        })
        .then(res => {
          timeCheckErrContent.value = '';
          result = true;
        })
        .catch(err => {
          timeCheckErrContent.value = err;
          result = false;
        });
      return result;
    };
    /** 清洗设置 */
    const renderSetting = () => (
      <div class='clean-setting'>
        <bk-alert
          class='clean-alert'
          title={t('通过字段清洗，可以格式化日志内容方便检索、告警和分析。')}
          type='info'
        />
        <div class='label-form-box'>
          <span class='label-title'>{t('原始日志')}</span>
          <div class='form-box'>
            <bk-radio-group
              value={formData.value.etl_params.retain_original_text}
              on-change={(val: boolean) => {
                formData.value.etl_params.retain_original_text = val;
              }}
            >
              <bk-radio
                class='mr-24'
                value={true}
              >
                <span v-bk-tooltips={t('确认保留原始日志,会存储在log字段. 其他字段提取内容会进行追加')}>
                  {t('保留')}
                </span>
              </bk-radio>
              <bk-radio value={false}>
                <span
                  v-bk-tooltips={t('不保留将丢弃原始日志，仅展示清洗后日志。请通过字段清洗，调试并输出您关心的日志。')}
                >
                  {t('丢弃')}
                </span>
              </bk-radio>
            </bk-radio-group>
            {formData.value.etl_params.retain_original_text && (
              <div class='select-group'>
                <div class='select-item'>
                  <span class='select-title'>{t('分词符')}</span>
                  <bk-select
                    class='select-box'
                    clearable={false}
                    value={originParticipleState.value}
                    on-selected={val => {
                      originParticipleState.value = val;
                      formData.value.etl_params.original_text_tokenize_on_chars =
                        val === 'custom' ? defaultParticipleStr.value : '';
                    }}
                  >
                    {participleList.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                </div>
                {originParticipleState.value === 'custom' && (
                  <bk-input
                    class='select-input'
                    value={formData.value.etl_params.original_text_tokenize_on_chars}
                    on-input={val => {
                      formData.value.etl_params.original_text_tokenize_on_chars = val;
                    }}
                  />
                )}
                <div class='select-item'>
                  <bk-checkbox
                    class='mr-5'
                    value={formData.value.etl_params.original_text_is_case_sensitive}
                    on-change={val => {
                      formData.value.etl_params.original_text_is_case_sensitive = val;
                    }}
                  />
                  {t('大小写敏感')}
                </div>
              </div>
            )}
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('日志样例')}</span>
          <div
            class='form-box'
            v-bkloading={{ isLoading: logOriginalLoading.value }}
          >
            <div class='example-box mt-5'>
              <span
                class='form-link'
                on-click={() => {
                  showReportLogSlider.value = true;
                }}
              >
                <i class='bklog-icon bklog-audit link-icon' />
                {t('上报日志')}
              </span>
              <span
                class='form-link'
                on-click={() => getDataLog('refresh')}
              >
                <i class='bklog-icon bklog-refresh2 link-icon' />
                {t('刷新')}
              </span>
              <InfoTips
                class='ml-12'
                tips={t('作为清洗调试的原始数据')}
              />
            </div>
            <bk-input
              type='textarea'
              value={logOriginal.value}
              on-change={val => {
                logOriginal.value = val;
              }}
            />
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('清洗模式')}</span>
          <div class='form-box'>
            <div class='example-box'>
              {/* 应用模版 */}
              {renderTemplateSelect()}
              <span class='form-link'>
                <i class='bklog-icon bklog-help link-icon' />
                {t('说明文档')}
              </span>
            </div>
            <div class='bk-button-group'>
              {cleaningModeList.map(mode => (
                <bk-button
                  key={mode.value}
                  class={{ 'is-selected': mode.value === cleaningMode.value }}
                  on-click={() => handleChangeCleaningMode(mode)}
                >
                  {mode.label}
                </bk-button>
              ))}
            </div>
            {renderCleaningMode()}
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('字段列表')}</span>
          <div class='form-box'>
            <FieldList
              ref={fieldListRef}
              builtInFieldsList={builtInFieldsList.value}
              data={formData.value.etl_fields || []}
              extractMethod={cleaningMode.value}
              loading={isDebugLoading.value || basicLoading.value}
              refresh={isValueRefresh.value}
              originalTextTokenizeOnChars={defaultParticipleStr.value}
              selectEtlConfig={cleaningMode.value}
              on-change={data => {
                formData.value.etl_fields = data;
              }}
              on-refresh={() => debugHandler('refresh')}
            />
          </div>
        </div>
      </div>
    );
    /** 高级设置 */
    const renderAdvanced = () => (
      <div class='advanced-setting'>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('指定日志时间')}</span>
          <div class='form-box'>
            <bk-radio-group
              value={formData.value.log_reporting_time}
              on-change={val => {
                formData.value.log_reporting_time = val;
              }}
            >
              <bk-radio
                class='mr-24'
                value={true}
              >
                {t('日志上报时间')}
              </bk-radio>
              <bk-radio value={false}>{t('指定字段为日志时间')}</bk-radio>
            </bk-radio-group>
            {!formData.value.log_reporting_time && (
              <div class='select-group'>
                <div class='select-item'>
                  <span class='select-title'>{t('字段')}</span>
                  <bk-select
                    class='select-box'
                    value={formData.value.field_name}
                    on-selected={val => {
                      formData.value.field_name = val;
                    }}
                  >
                    {formData.value.etl_fields.map(item => (
                      <bk-option
                        id={item.field_name}
                        key={`${item.field_index}${item.field_name}`}
                        name={item.field_name}
                      />
                    ))}
                  </bk-select>
                </div>
                <div class='select-item'>
                  <span class='select-title'>{t('时间格式')}</span>
                  <bk-select
                    class='select-box'
                    value={formData.value.time_format}
                    on-selected={val => {
                      formData.value.time_format = val;
                    }}
                  >
                    {fieldDateFormat.value.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={`${item.name} (${item.description})`}
                      />
                    ))}
                  </bk-select>
                </div>
                <div class='select-item'>
                  <span class='select-title'>{t('时区选择')}</span>
                  <bk-select
                    class='select-box'
                    value={formData.value.time_zone}
                    on-selected={val => {
                      formData.value.time_zone = val;
                    }}
                  >
                    {timeZone.value.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                </div>
              </div>
            )}
          </div>
        </div>
        {timeCheckErrContent.value && <p class='format-error'>{timeCheckErrContent.value}</p>}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('失败日志')}</span>
          <bk-radio-group
            class='form-box'
            value={formData.value.etl_params.enable_retain_content}
            on-change={(val: boolean) => {
              formData.value.etl_params.enable_retain_content = val;
            }}
          >
            <bk-radio
              class='mr-24'
              value={true}
            >
              {t('保留')}
            </bk-radio>
            <bk-radio value={false}>{t('丢弃')}</bk-radio>
          </bk-radio-group>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('路径元数据')}</span>
          <div class='form-box mt-5'>
            <bk-switcher
              size='large'
              theme='primary'
              value={enableMetaData.value}
              on-change={(val: boolean) => {
                enableMetaData.value = val;
              }}
            />
            <InfoTips
              class='ml-12'
              tips={t('定义元数据并补充至日志中，可通过元数据进行过滤筛选')}
            />
          </div>
        </div>
        {enableMetaData.value && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('路径样例')}</span>
            <div class='form-box'>
              <div class='url-demo-box'>
                <bk-input
                  class='input-box'
                  value={pathExample.value}
                  on-change={val => {
                    pathExample.value = val;
                  }}
                />
                <i class='bklog-icon bklog-refresh-icon icons' />
              </div>
            </div>
          </div>
        )}
        {enableMetaData.value && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集路径分割正则')}</span>
            <div class='form-box'>
              <div class='url-demo-box'>
                <bk-input
                  class='input-box'
                  placeholder={defaultRegex}
                  value={formData.value.etl_params.path_regexp}
                  on-input={val => {
                    formData.value.etl_params.path_regexp = val;
                  }}
                />
                <bk-button
                  class='debug-btn'
                  disabled={!showDebugPathRegexBtn.value || isDebugLoading.value}
                  on-click={debuggerPathRegex}
                >
                  {t('调试')}
                </bk-button>
              </div>
              <div class='debug-box'>
                {(formData.value.etl_params.metadata_fields || []).map(item => (
                  <div
                    key={item.field_name}
                    class='metadata-fields-item'
                  >
                    <div
                      class='item-name'
                      title={item.field_name}
                    >
                      {item.field_name}
                    </div>
                    <span class='symbol'>:</span>
                    <div
                      class='item-value'
                      title={item.value}
                    >
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
    const cardConfig = [
      {
        title: t('清洗设置'),
        key: 'cleanSetting',
        renderFn: renderSetting,
      },
      {
        title: t('高级设置'),
        key: 'advancedSetting',
        renderFn: renderAdvanced,
      },
    ];
    /**
     * 保存按钮
     */
    const handleSubmit = async () => {
      loading.value = true;
      // 校验字段表格
      const validatePromises = fieldListRef.value?.validateFieldTable();
      if (validatePromises && validatePromises.length > 0) {
        try {
          await Promise.all(validatePromises);
        } catch (error) {
          loading.value = false;
          return;
        }
      }
      /**
       * 校验时间格式， 校验通过之后，把指定的时间字段的 is_time 设置为 true
       */
      if (!formData.value.log_reporting_time) {
        const res = await requestCheckTime();
        if (!res) {
          loading.value = false;
          return;
        }
        const list = formData.value.etl_fields.map(item => ({
          ...item,
          is_time: item.field_name === formData.value.field_name,
        }));
        formData.value.etl_fields = list;
      }
      const { etl_params, etl_fields } = formData.value;
      const { storage_cluster_id, allocation_min_days, storage_replies, es_shards, table_id, retention } =
        curCollect.value;
      /**
       * 编辑/创建清洗
       * 未完成的情况下，调用创建清洗配置接口 （storage_cluster_id = -1 或者为空，都代表未完成）
       */
      const isNeedCreate = isUpdate.value && !!storage_cluster_id;
      const url = isNeedCreate ? 'collect/fieldCollection' : 'clean/updateCleanStash';
      const data = {
        bk_biz_id: bkBizId.value,
        etl_params,
      };
      const requestData = isNeedCreate
        ? {
            ...data,
            fields: etl_fields,
            storage_cluster_id,
            allocation_min_days,
            storage_replies,
            es_shards,
            table_id,
            retention,
            etl_config: cleaningMode.value,
          }
        : {
            ...data,
            etl_fields,
            clean_type: cleaningMode.value,
          };
      $http
        .request(url, {
          params: {
            collector_config_id: curCollect.value.collector_config_id,
          },
          data: requestData,
        })
        .then(res => {
          loading.value = false;
          if (res?.result) {
            const data = isNeedCreate ? { ...formData.value, ...curCollect.value } : formData.value;
            emit('next', data);
          }
        })
        .catch(() => {
          loading.value = false;
        });
    };
    return () => (
      <div
        class='operation-step3-clean'
        v-bkloading={{ isLoading: basicLoading.value }}
      >
        {cardRender(cardConfig)}
        <ReportLogSlider
          isShow={showReportLogSlider.value}
          jsonText={jsonText.value}
          on-change={value => {
            showReportLogSlider.value = value;
          }}
        />
        <div class='classify-btns-fixed'>
          <bk-button
            class='mr-8'
            on-click={() => {
              emit('prev');
            }}
          >
            {t('上一步')}
          </bk-button>
          <bk-button
            class='width-88 mr-8'
            theme='primary'
            loading={loading.value}
            on-click={handleSubmit}
          >
            {t('下一步')}
          </bk-button>
          <bk-button
            class='template-btn'
            on-click={() => {
              templateDialogVisible.value = true;
            }}
          >
            {t('另存为模板')}
          </bk-button>
          <bk-button
            class='mr-8'
            on-click={() => {
              formData.value = { ...cacheTemplateData.value };
            }}
          >
            {t('重置')}
          </bk-button>
          <bk-button
            on-click={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </bk-button>
        </div>
        {/* 另存为模版弹窗 */}
        <bk-dialog
          width='480'
          draggable={false}
          header-position={'left'}
          mask-close={false}
          title={t('另存为模板')}
          value={templateDialogVisible.value}
          on-confirm={handleTempConfirm}
        >
          <div class='template-content'>
            <span style='color: #63656e'>{t('模板名称')}</span>
            <bk-input
              style='margin-top: 8px'
              value={templateName.value}
              on-change={val => {
                templateName.value = val;
              }}
            />
          </div>
        </bk-dialog>
      </div>
    );
  },
});
