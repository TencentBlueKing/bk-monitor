import { ServicesInstance } from '@/platform/services';
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

import { computed, defineComponent, nextTick, ref, watch } from 'vue';

import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import BklogLoading from '@/shared/ui/loading';
import {
  Form,
  FormItem,
  Select,
  Option,
  Input,
  Switch,
  RadioGroup,
  Radio,
  Button,
  MessagePlugin,
} from 'tdesign-vue-next';
import { toWorkerMessage } from '@/shared/lib/worker-message';
import 'tdesign-vue-next/es/style/index.css';
const bkMessage = ({ theme, message }) => MessagePlugin({ theme, content: message });

import { parseTableRowData } from '../../../shared/lib/util';
import { GradeFieldValueType, type GradeSetting } from '../../retrieval/core/interface';

import { retrieveRowCacheService } from '@/platform/persistence/index';

import './grade-option.scss';

const getDefaultGradeOption = () => {
  return {
    disabled: false,
    type: 'normal',
    field: null,
    fieldType: 'string',
    valueType: GradeFieldValueType.VALUE,
    settings: [
      {
        id: 'level_1',
        color: '#D46D5D',
        name: 'fatal',
        regExp: '/\\b(?:FATAL|CRITICAL|EMERGENCY)\\b/i',
        fieldValue: [],
        enable: true,
      },
      {
        id: 'level_2',
        color: '#F59789',
        name: 'error',
        regExp: '/\\b(?:ERROR|ERR|FAIL(?:ED|URE)?)\\b/i',
        fieldValue: [],
        enable: true,
      },
      {
        id: 'level_3',
        color: '#F5C78E',
        name: 'warn',
        regExp: '/\\b(?:WARNING|WARN|ALERT|NOTICE)\\b/i',
        fieldValue: [],
        enable: true,
      },
      {
        id: 'level_4',
        color: '#6FC5BF',
        name: 'info',
        regExp: '/\\b(?:INFO|INFORMATION)\\b/i',
        fieldValue: [],
        enable: true,
      },
      {
        id: 'level_5',
        color: '#92D4F1',
        name: 'debug',
        regExp: '/\\b(?:DEBUG|DIAGNOSTIC)\\b/i',
        fieldValue: [],
        enable: true,
      },
      {
        id: 'level_6',
        color: '#A3B1CC',
        name: 'trace',
        regExp: '/\\b(?:TRACE|TRACING)\\b/i',
        fieldValue: [],
        enable: true,
      },
      {
        id: 'others',
        color: '#DCDEE5',
        name: 'others',
        regExp: '--',
        fieldValue: [],
        enable: true,
      },
    ],
  };
};

export default defineComponent({
  emits: ['change'],
  setup(_, { emit, expose }) {
    const { $t } = useLocale();
    const store = useStore();
    /**
     * 分级类别
     */
    const gradeCategory = ref([
      {
        id: 'normal',
        name: $t('默认配置'),
      },
      {
        id: 'custom',
        name: $t('自定义'),
      },
    ]);

    /**
     * 分级配置表单
     */
    const gradeOptionForm = ref(getDefaultGradeOption());
    const formRef = ref<any>(null);
    const formRules = {
      type: [
        {
          trigger: 'change',
          validator: () => gradeOptionForm.value.disabled || ['normal', 'custom'].includes(gradeOptionForm.value.type),
          message: $t('必填项'),
        },
      ],
      field: [
        {
          trigger: 'change',
          validator: () =>
            gradeOptionForm.value.disabled || gradeOptionForm.value.type !== 'custom' || !!gradeOptionForm.value.field,
          message: $t('必填项'),
        },
      ],
    };

    const isLoading = ref(false);
    const indexedRows = ref<Record<string, any>[]>([]);

    const fieldList = computed(() =>
      store.getters.rawFieldList.filter((f: { es_doc_values: any; field_type: string; }) => f.es_doc_values && f.field_type === 'keyword'),
    );

    const gradeOptionField = computed(() => fieldList.value.find((f: { field_name: null; }) => f.field_name === gradeOptionForm.value.field));

    watch(
      () => [
        store.state.indexSetQueryResult.row_query_key,
        store.state.indexSetQueryResult.cached_count,
        gradeOptionForm.value.field,
        gradeOptionForm.value.valueType,
      ],
      async () => {
        if (gradeOptionForm.value.valueType !== GradeFieldValueType.VALUE || !gradeOptionForm.value.field) {
          indexedRows.value = [];
          return;
        }

        indexedRows.value = await retrieveRowCacheService.getRowsByQuery(
          store.state.indexSetQueryResult.row_query_key,
          0,
          200,
        );
      },
      { immediate: true },
    );

    const fieldSearchValueList = computed(() => {
      if (gradeOptionForm.value.valueType === GradeFieldValueType.VALUE && gradeOptionForm.value.field) {
        const storedValues = gradeOptionForm.value.settings.flatMap(item => item.fieldValue ?? []);
        return Array.from(
          new Set([
            ...indexedRows.value.map(item =>
              parseTableRowData(item, gradeOptionForm.value.field, gradeOptionField.value?.field_type, true),
            ),
            ...storedValues,
          ]),
        ).map(f => ({ id: String(f), name: String(f) }));
      }

      return [];
    });

    const handleSaveGradeSettingClick = async (e: MouseEvent, isSave = true) => {
      if (!isSave) {
        gradeOptionForm.value = getDefaultGradeOption();
        formRef.value?.clearValidate();
        emit('change', { event: e, isSave, data: gradeOptionForm.value });
        return;
      }

      if (isSave && !isLoading.value) {
        try {
          const result = await formRef.value?.validate();
          if (result !== true) return;
        } catch {
          return;
        }
        isLoading.value = true;

        ServicesInstance.retrieve.setIndexSetCustomConfig({
            data: {
              index_set_id: store.state.indexId,
              index_set_ids: store.state.indexItem.ids,
              index_set_type: store.state.indexItem.isUnionIndex ? 'union' : 'single',
              index_set_config: {
                grade_options: gradeOptionForm.value,
              },
            },
          })
          .then(resp => {
            if (resp.result) {
              store.commit('updateIndexSetCustomConfig', {
                grade_options: structuredClone(toWorkerMessage(gradeOptionForm.value)),
              });
              emit('change', { event: e, isSave, data: gradeOptionForm.value });
              return;
            }

            bkMessage({
              theme: 'error',
              message: resp.message,
            });
          })
          .finally(() => {
            isLoading.value = false;
          });
      }
    };

    const updateOptions = (cfg?: { disabled: boolean; type: string; field: null; fieldType: string; valueType: GradeFieldValueType; settings: { id: string; color: string; name: string; regExp: string; fieldValue: never[]; enable: boolean; }[]; }) => {
      const target = cfg ?? getDefaultGradeOption();
      Object.assign(gradeOptionForm.value, structuredClone(toWorkerMessage(target)));
      formRef.value?.clearValidate();
    };

    const handleTypeChange = (type: string) => {
      const target = { ...gradeOptionForm.value, type };
      if (type === 'normal') {
        target.settings = getDefaultGradeOption().settings;
      }
      Object.assign(gradeOptionForm.value, target);
      formRef.value?.clearValidate();
    };

    const handleGradeOptionFormChange = (key: string, value: any) => {
      gradeOptionForm.value[key] = value;
    };

    const handleSettingItemChange = (index: number, key: string, value: any) => {
      gradeOptionForm.value.settings[index][key] = value;
    };

    const handleSettingFieldChange = (value: any) => {
      handleGradeOptionFormChange('field', value);
      formRef.value?.clearValidate();
      nextTick(() => {
        handleGradeOptionFormChange('fieldType', gradeOptionField.value?.field_type);
      });
    };

    expose({
      updateOptions,
    });

    const fieldValueRender = (item: GradeSetting, index: number) => {
      if (item.id === 'others') {
        return '--';
      }

      if (gradeOptionForm.value.type === 'custom' && !gradeOptionForm.value.disabled) {
        if (gradeOptionForm.value.valueType === GradeFieldValueType.VALUE) {
          return (
            <Select
              style='width: 100%;'
              value={item.fieldValue}
              creatable
              clearable
              multiple
              filterable
              minCollapsedNum={1}
              popupProps={{ trigger: 'focus', overlayClassName: 'bklog-popover-stop' }}
              onCreate={value => {
                if (!item.fieldValue.includes(value))
                  handleSettingItemChange(index, 'fieldValue', [...item.fieldValue, value]);
              }}
              onChange={v => handleSettingItemChange(index, 'fieldValue', v)}
            >
              {fieldSearchValueList.value.map(data => (
                <Option
                  key={data.id}
                  value={data.id}
                  label={data.name}
                >
                  <div
                    style='line-height: 30px; padding: 0 12px; width: 100%;'
                    class='bklog-popover-stop'
                  >
                    {data.name}
                  </div>
                </Option>
              ))}
            </Select>
          );
        }

        return (
          <Input
            value={item.regExp}
            onChange={v => handleSettingItemChange(index, 'regExp', v)}
          />
        );
      }

      return item.regExp;
    };

    return () => (
      <BklogLoading
        data-testid='grade-option-loading'
        loading={isLoading.value}
        size='mini'
      >
        <div class='grade-title'>{$t('日志分级展示')}</div>
        <div class='grade-row grade-switcher'>
          <div class='grade-label'>{$t('分级展示')}</div>
          <div class='grade-field-des'>
            <Switch
              theme='primary'
              value={!gradeOptionForm.value.disabled}
              onChange={v => {
                handleGradeOptionFormChange('disabled', !v);
                formRef.value?.clearValidate();
              }}
            />
            <span class='bklog-icon bklog-info-fill' />
            <span>{$t('指定清洗字段后可生效该配置，日志页面将会按照不同颜色清洗分类，最多六个字段')}</span>
          </div>
        </div>
        <div class='grade-row'>
          <div class={['grade-label', { required: !gradeOptionForm.value.disabled }]}>{$t('字段设置')}</div>
          <Form
            ref={formRef}
            class='grade-field-setting'
            labelAlign='top'
            data={gradeOptionForm.value}
            rules={formRules}
          >
            <FormItem
              class='grade-type-form-item'
              name='type'
              errorDisplayType='tooltips'
              iconOffset={26}
            >
              <Select
                disabled={gradeOptionForm.value.disabled}
                popupProps={{ overlayClassName: 'bklog-popover-stop' }}
                value={gradeOptionForm.value.type}
                filterable
                onChange={handleTypeChange}
              >
                {gradeCategory.value.map(option => (
                  <Option
                    value={option.id}
                    key={option.id}
                    label={option.name}
                  />
                ))}
              </Select>
            </FormItem>
            {gradeOptionForm.value.type === 'custom' && (
              <FormItem
                class='grade-custom-field-form-item'
                name='field'
                errorDisplayType='tooltips'
                iconOffset={26}
              >
                <Select
                  disabled={gradeOptionForm.value.disabled}
                  popupProps={{ overlayClassName: 'bklog-popover-stop' }}
                  placeholder={$t('请选择字段')}
                  value={gradeOptionForm.value.field}
                  filterable
                  onChange={val => handleSettingFieldChange(val)}
                >
                  {fieldList.value.map((option: { field_name: string|number|bigint|boolean|symbol|undefined; field_alias: any; }) => (
                    <Option
                      value={option.field_name}
                      key={option.field_name}
                      label={`${option.field_name}(${option.field_alias || option.field_name})`}
                    />
                  ))}
                </Select>
              </FormItem>
            )}
          </Form>
        </div>
        <div class='grade-row'>
          <div class='grade-label'>{$t('字段列表')}</div>
          <div class='grade-table'>
            <div class='grade-table-header'>
              <div
                style='width: 46px'
                class='grade-table-col col-color'
              >
                {$t('颜色')}
              </div>
              <div
                style='width: 240px'
                class='grade-table-col'
              >
                {$t('字段定义')}
              </div>
              <div
                style='width: 330px'
                class='grade-table-col'
              >
                <RadioGroup
                  value={gradeOptionForm.value.valueType}
                  onChange={v => handleGradeOptionFormChange('valueType', v)}
                >
                  <Radio
                    disabled={gradeOptionForm.value.disabled || gradeOptionForm.value.type === 'normal'}
                    value={GradeFieldValueType.VALUE}
                  >
                    {$t('快速选择')}
                  </Radio>
                  <Radio
                    style='margin-left: 14px;'
                    disabled={gradeOptionForm.value.disabled || gradeOptionForm.value.type === 'normal'}
                    value={GradeFieldValueType.REGEXP}
                  >
                    {$t('正则表达式')}
                  </Radio>
                </RadioGroup>
              </div>
              <div
                style='width: 60px'
                class='grade-table-col'
              >
                {$t('启用')}
              </div>
            </div>
            <div class='grade-table-body'>
              {gradeOptionForm.value.settings.map((item, index) => (
                <div
                  key={item.id}
                  class={['grade-table-row', { readonly: item.id === 'others' }]}
                >
                  <div
                    style='width: 46px'
                    class='grade-table-col col-color'
                  >
                    <span style={{ width: '16px', height: '16px', background: item.color, borderRadius: '1px' }} />
                  </div>
                  <div
                    style='width: 240px'
                    class='grade-table-col'
                  >
                    {item.id !== 'others' &&
                    gradeOptionForm.value.type === 'custom' &&
                    !gradeOptionForm.value.disabled ? (
                      <Input
                        value={item.name}
                        onChange={v => handleSettingItemChange(index, 'name', v)}
                      />
                    ) : (
                      item.name
                    )}
                  </div>
                  <div
                    style='width: 330px'
                    class='grade-table-col'
                  >
                    {fieldValueRender(item, index)}
                  </div>
                  {item.id !== 'others' && (
                    <div
                      style='width: 60px'
                      class='grade-table-col'
                    >
                      <Switch
                        disabled={gradeOptionForm.value.disabled}
                        size='small'
                        theme='primary'
                        value={item.enable}
                        onChange={v => handleSettingItemChange(index, 'enable', v)}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div class='grade-row grade-footer'>
          <Button
            style='margin-right: 8px'
            theme='primary'
            onClick={e => handleSaveGradeSettingClick(e, true)}
          >
            {$t('确定')}
          </Button>
          <Button
            theme='default'
            onClick={e => handleSaveGradeSettingClick(e, false)}
          >
            {$t('取消')}
          </Button>
        </div>
      </BklogLoading>
    );
  },
});
