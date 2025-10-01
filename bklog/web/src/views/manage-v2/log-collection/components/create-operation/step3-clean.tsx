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

import { defineComponent, ref, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useOperation } from '../../hook/useOperation';
import CollectIssuedSlider from '../business-comp/step3/collect-issued-slider';
import FieldList from '../business-comp/step3/field-list';
import ReportLogSlider from '../business-comp/step3/report-log-slider';
import InfoTips from '../common-comp/info-tips';
import { tableFieldData } from './detail';
import { log } from './log';
import $http from '@/api';
// // 使用 webpack 的 require.context 预加载该目录下的所有 png 资源
// const iconsContext = (require as any).context('@/images/log-collection', false, /\.png$/);

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
  },

  emits: ['next', 'prev', 'cancel'],

  setup(props, { emit }) {
    const store = useStore();
    const testConfigData = {
      collector_config_id: 3240,
      collector_config_name: 'win-0930-2',
      bk_data_id: 1577598,
      subscription_id: 33579,
      task_id_list: ['29033233'],
    };
    const { t } = useLocale();
    const defaultRegex = '(?P<request_ip>[\d\.]+)[^[]+\[(?P<request_time>[^]]+)\]';
    const { cardRender } = useOperation();
    const showCollectIssuedSlider = ref(false);
    const showReportLogSlider = ref(false);
    const jsonText = ref({});
    const pathExample = ref('');
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
      // {
      //   label: t('高级清洗'),
      //   value: 'advanced',
      // },
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
    const defaultParticipleStr = ref('@&()=\'",;:<>[]{}/ \\n\\t\\r\\\\');

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
    const isUnmodifiable = ref(false);
    const params = ref({
      // 此处为可以变动的数据，如果调试成功，则将此条件保存至formData，保存时还需要对比此处与formData是否有差异
      etl_config: 'bk_log_text',
      etl_params: {
        separator_regexp: '',
        separator: '',
      },
    });

    const fieldsObjectData = ref([]);
    onMounted(() => {
      getDetail();
    });

    // 获取详情
    const getDetail = () => {
      console.log(store.getters['collect/curCollect'], '===');
      // const tsStorageId = this.formData.storage_cluster_id;
      // const {
      //   table_id,
      //   storage_cluster_id,
      //   table_id_prefix,
      //   etl_config,
      //   etl_params: etlParams,
      //   fields,
      //   index_set_id,
      // } = this.curCollect;
      // const option = { time_zone: '', time_format: '' };
      // const copyFields = fields ? structuredClone(fields) : [];
      // // biome-ignore lint/complexity/noForEach: <explanation>
      // copyFields.forEach(row => {
      //   row.value = '';
      //   if (row.is_delete) {
      //     const copyRow = Object.assign(structuredClone(rowTemplate.value), structuredClone(row));
      //     Object.assign(row, copyRow);
      //   }
      //   if (row.option) {
      //     row.option = { ...option, ...(row.option || {}) };
      //   } else {
      //     row.option = { ...option };
      //   }
      // });
      // params.value.etl_config = etl_config;
      // Object.assign(params.value.etl_params, {
      //   separator_regexp: etlParams?.separator_regexp || '',
      //   separator: etlParams?.separator || '',
      // });
      // isUnmodifiable.value = !!(table_id || storage_cluster_id);
      // cleaningMode.value = etl_config || 'bk_log_text';
      // Object.assign(formData.value, {
      //   table_id,
      //   // storage_cluster_id,
      //   table_id_prefix,
      //   etl_config: cleaningMode.value,
      //   etl_params: {
      //     retain_original_text: true,
      //     separator_regexp: '',
      //     separator: '',
      //     retain_extra_json: false,
      //     original_text_is_case_sensitive: false,
      //     original_text_tokenize_on_chars: '',
      //     enable_retain_content: true,
      //     path_regexp: '',
      //     metadata_fields: [],
      //     ...(etlParams
      //       ? {
      //           ...structuredClone(etlParams),
      //           metadata_fields: etlParams.metadata_fields || [],
      //         }
      //       : {}),
      //   },
      //   fields: copyFields.filter(item => !item.is_built_in),
      // });

      // if (!copyBuiltField.value.length) {
      //   copyBuiltField.value = copyFields.filter(item => item.is_built_in);
      // }
      // if (this.curCollect.etl_config && this.curCollect.etl_config !== 'bk_log_text') {
      //   this.formatResult = true;
      // }
      // requestFields(index_set_id);
    };

    const addChildrenToBuiltField = (builtFieldList, item, name) => {
      const field_name = name.split('.')[0].replace(/^_+|_+$/g, '');
      // biome-ignore lint/complexity/noForEach: <explanation>
      builtFieldList.forEach(builtField => {
        if (builtField.field_type === 'object' && field_name === builtField.field_name?.split('.')[0]) {
          if (!Array.isArray(builtField.children)) {
            builtField.children = [];
            builtField.expand = false;
            // this.$set(builtField, 'expand', false);
          }
          builtField.children.push(item);
        }
      });
    };

    /** 获取fields */
    const requestFields = async (indexSetId: number) => {
      if (!indexSetId) {
        return;
      }
      const typeConversion = {
        keyword: 'string',
        long: 'string',
      };
      try {
        const res = await $http.request('retrieve/getLogTableHead', {
          params: {
            index_set_id: indexSetId,
          },
        });
        fieldsObjectData.value = res.data.fields.filter(item => item.field_name.includes('.'));
        // biome-ignore lint/complexity/noForEach: <explanation>
        fieldsObjectData.value.forEach(item => {
          const name = item.field_name.split('.')[0];
          item.field_type = typeConversion[item.field_type];
          item.is_objectKey = true;
          item.is_delete = false;

          addChildrenToBuiltField(copyBuiltField.value, item, name);
          addChildrenToBuiltField(formData.value.fields, item, name);
        });
      } catch (err) {
        console.warn(err);
      }
    };

    //  获取采样状态
    const getDataLog = type => {
      console.log('type', type, props.configData);
      // this.refresh = false;
      // if (type === 'init') {
      //   this.basicLoading = true;
      // } else if (type === 'logOriginRefresh') {
      //   this.logOriginalLoding = true;
      // } else if (type === 'pathRefresh') {
      //   this.pathExampleLoading = true;
      // }
      $http
        .request('source/dataList', {
          params: {
            collector_config_id: props.configData.collector_config_id || testConfigData.collector_config_id,
          },
        })
        .then(res => {
          if (res.data?.length) {
            copyText.value = Object.assign(res.data[0].etl, res.data[0].etl.items[0]) || {};
            const data = res.data[0];
            jsonText.value = data.origin || {};
            pathExample.value = jsonText.value.filename;
            logOriginal.value = data.etl.data || '';
            if (logOriginal.value) {
              // this.requestEtlPreview(isInit);
            }
            // biome-ignore lint/complexity/noForEach: <explanation>
            copyBuiltField.value.forEach(item => {
              const fieldName = item.field_name;
              if (fieldName) {
                if (Object.hasOwn(item, 'value')) {
                  item.value = copyText.value[fieldName];
                } else {
                  // this.$set(item, 'value', copyText.value[fieldName]);
                }
              }
            });
          }
        })
        .catch(() => {})
        .finally(() => {
          // if (type === 'init') {
          //   this.basicLoading = false;
          // } else if (type === 'logOriginRefresh') {
          //   this.logOriginalLoding = false;
          // } else if (type === 'pathRefresh') {
          //   this.pathExampleLoading = false;
          // }
          // this.refresh = true;
        });
    };
    /** 根据清洗模式，渲染不同的内容 */
    const renderCleaningMode = () => {
      if (cleaningMode.value === 'bk_log_json') {
        return <bk-button class='clean-btn'>{t('清洗')}</bk-button>;
      }
      if (cleaningMode.value === 'bk_log_delimiter') {
        return (
          <div class='separator-box select-group'>
            <div class='select-item'>
              <span class='select-title'>{t('分隔符')}</span>
              <bk-select class='select-box' />
            </div>
            <bk-button class='clean-btn'>{t('调试')}</bk-button>
          </div>
        );
      }
      if (cleaningMode.value === 'bk_log_regexp') {
        return (
          <div class='regex-box-main'>
            <div class='title'>
              {t('正则表达式')}
              <i
                class='bk-icon icon-info-circle tips-icon'
                v-bk-tooltips={{
                  placement: 'right',
                  content: `${t('正则表达式(golang语法)需要匹配日志全文，如以下DEMO将从日志内容提取请求时间与内容')}<br />${t(' - 日志内容：[2006-01-02 15:04:05] content')}<br /> ${t(' - 表达式：')} \[(?P<request_time>[^]]+)\] (?P<content>.+)`,
                }}
              />
            </div>
            <bk-input
              placeholder={'(?P<request_ip>[d.]+)[^[]+[(?P<request_time>[^]]+)]'}
              type='textarea'
            />
            <bk-button class='clean-btn'>{t('调试')}</bk-button>
          </div>
        );
      }
    };
    /** 应用模版下拉框 */
    const renderTemplateSelect = () => (
      <bk-select
        class='template-select'
        ext-popover-cls={'template-select-popover'}
        searchable
        // on-selected={handleAddSortFields}
      >
        <span
          class='form-link'
          slot='trigger'
        >
          <i class='bklog-icon bklog-app-store link-icon' />
          {t('应用模板')}
        </span>
        {[
          { id: 1, name: '模板名称' },
          { id: 2, name: '模板名称' },
        ].map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            name={item.name}
          >
            <div class='template-option'>
              <span class='option-name'>{item.name}</span> <span class='option-btn'>{t('应用')}</span>
            </div>
          </bk-option>
        ))}
      </bk-select>
    );

    /** 选择清洗模式 */
    const handleChangeCleaningMode = mode => {
      cleaningMode.value = mode.value;
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
              on-change={val => {
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
          <div class='form-box'>
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
                on-click={getDataLog}
              >
                <i class='bklog-icon bklog-refresh2 link-icon' />
                {t('刷新')}
              </span>
              <InfoTips
                class='ml-12'
                tips={t('作为清洗调试的原始数据')}
              />
            </div>
            <bk-input type='textarea' />
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
              data={tableFieldData.fields}
              selectEtlConfig={cleaningMode.value}
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
                  />
                </div>
                <div class='select-item'>
                  <span class='select-title'>{t('时间格式')}</span>
                  <bk-select
                    class='select-box'
                    value={formData.value.time_format}
                  />
                </div>
                <div class='select-item'>
                  <span class='select-title'>{t('时区选择')}</span>
                  <bk-select
                    class='select-box'
                    value={formData.value.time_zone}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('失败日志')}</span>
          <bk-radio-group
            class='form-box'
            value={formData.value.etl_params.enable_retain_content}
            on-change={val => {
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
              on-change={val => {
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
            <div class='form-box mt-5'>
              <div class='url-demo-box'>
                <bk-input class='input-box' />
                <i class='bklog-icon bklog-refresh-icon icons' />
              </div>
            </div>
          </div>
        )}
        {enableMetaData.value && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集路径分割正则')}</span>
            <div class='form-box mt-5'>
              <div class='url-demo-box'>
                <bk-input
                  class='input-box'
                  placeholder={defaultRegex}
                  value={formData.value.etl_params.path_regexp}
                  on-input={val => {
                    formData.value.etl_params.path_regexp = val;
                  }}
                />
                <bk-button class='debug-btn'>{t('调试')}</bk-button>
              </div>
              <div class='debug-box'>
                <bk-input
                  class='first-input'
                  disabled
                />
                <span class='symbol'>:</span>
                <bk-input disabled />
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
    return () => (
      <div class='operation-step3-clean'>
        <div
          class='status-box loading'
          on-Click={() => {
            showCollectIssuedSlider.value = true;
          }}
        >
          <span class='status-icon-box' />
          <i class='bklog-icon bklog-caijixiafazhong status-icon' />
          {/* <i class='bklog-icon bklog-circle-correct-filled status-icon' /> */}
          {/* <i class='bklog-icon bklog-shanchu status-icon' /> */}
          <span class='status-txt'>{t('采集下发中...')}</span>
        </div>
        {cardRender(cardConfig)}
        <CollectIssuedSlider
          data={log}
          isShow={showCollectIssuedSlider.value}
          on-change={value => {
            showCollectIssuedSlider.value = value;
          }}
        />
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
            on-click={() => {
              emit('next');
            }}
          >
            {t('下一步')}
          </bk-button>
          <bk-button class='template-btn'>{t('另存为模板')}</bk-button>
          <bk-button class='mr-8'>{t('重置')}</bk-button>
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
