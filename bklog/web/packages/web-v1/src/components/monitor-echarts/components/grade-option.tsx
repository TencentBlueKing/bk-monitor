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

import { computed, defineComponent, nextTick, ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { bkMessage } from 'bk-magic-vue';

import { parseTableRowData } from '../../../common/util';
import { GradeFieldValueType, type GradeSetting } from '../../../views/retrieve-core/interface';
import $http from '@/api';

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

    const isLoading = ref(false);

    const fieldList = computed(() =>
      (store.state.indexFieldInfo.fields ?? []).filter(f => f.es_doc_values && f.field_type === 'keyword'),
    );

    const gradeOptionField = computed(() => fieldList.value.find(f => f.field_name === gradeOptionForm.value.field));
    const fieldSearchValueList = computed(() => {
      if (gradeOptionForm.value.valueType === GradeFieldValueType.VALUE && gradeOptionForm.value.field) {
        const storedValues = gradeOptionForm.value.settings.flatMap(item => item.fieldValue ?? []);
        return Array.from(
          new Set([
            ...store.state.indexSetQueryResult.list.map(item =>
              parseTableRowData(item, gradeOptionForm.value.field, gradeOptionField.value?.field_type, true),
            ),
            ...storedValues,
          ]),
        ).map(f => ({ id: `${f}`, name: `${f}` }));
      }

      return [];
    });

    const handleSaveGradeSettingClick = (e: MouseEvent, isSave = true) => {
      if (!isSave) {
        gradeOptionForm.value = getDefaultGradeOption();
        emit('change', { event: e, isSave, data: gradeOptionForm.value });
        return;
      }

      if (isSave) {
        isLoading.value = true;

        $http
          .request('retrieve/setIndexSetCustomConfig', {
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
              emit('change', { event: e, isSave, data: gradeOptionForm.value });
              store.commit('updateIndexSetCustomConfig', {
                grade_options: structuredClone(gradeOptionForm.value),
              });
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

    const updateOptions = (cfg?) => {
      const target = cfg ?? getDefaultGradeOption();
      Object.assign(gradeOptionForm.value, structuredClone(target));
    };

    const handleTypeChange = type => {
      const target = { ...gradeOptionForm.value, type };
      if (type === 'normal') {
        target.settings = getDefaultGradeOption().settings;
      }
      Object.assign(gradeOptionForm.value, target);
    };

    const handleGradeOptionFormChange = (key: string, value: any) => {
      gradeOptionForm.value[key] = value;
    };

    const handleSettingItemChange = (index: number, key: string, value: any) => {
      gradeOptionForm.value.settings[index][key] = value;
    };

    const handleSettingFieldChange = (value: any) => {
      handleGradeOptionFormChange('field', value);
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
            <bk-tag-input
              style='width: 100%;'
              tpl={data => (
                <div
                  style='line-height: 30px; padding: 0 12px; width: 100%;'
                  class='bklog-popover-stop'
                >
                  {data.name}
                </div>
              )}
              list={fieldSearchValueList.value}
              trigger='focus'
              value={item.fieldValue}
              allow-create
              clearable
              multiple
              searchable
              onChange={v => handleSettingItemChange(index, 'fieldValue', v)}
            />
          );
        }

        return (
          <bk-input
            value={item.regExp}
            on-change={v => handleSettingItemChange(index, 'regExp', v)}
          />
        );
      }

      return item.regExp;
    };

    return () => (
      <div v-bkloading={{ isLoading: isLoading.value, size: 'mini' }}>
        <div class='grade-title'>{$t('日志分级展示')}</div>
        <div class='grade-row grade-switcher'>
          <div class='grade-label'>{$t('分级展示')}</div>
          <div class='grade-field-des'>
            <bk-switcher
              theme='primary'
              value={!gradeOptionForm.value.disabled}
              on-change={v => handleGradeOptionFormChange('disabled', !v)}
            />
            <span class='bklog-icon bklog-info-fill' />
            <span>{$t('指定清洗字段后可生效该配置，日志页面将会按照不同颜色清洗分类，最多六个字段')}</span>
          </div>
        </div>
        <div class='grade-row'>
          <div class='grade-label required'>{$t('字段设置')}</div>
          <div class='grade-field-setting'>
            <bk-select
              style='width: 240px'
              disabled={gradeOptionForm.value.disabled}
              ext-popover-cls='bklog-popover-stop'
              value={gradeOptionForm.value.type}
              searchable
              on-change={handleTypeChange}
            >
              {gradeCategory.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            {gradeOptionForm.value.type === 'custom' && (
              <bk-select
                style='width: 366px; margin-left: 10px'
                disabled={gradeOptionForm.value.disabled}
                ext-popover-cls='bklog-popover-stop'
                placeholder={$t('请选择字段')}
                value={gradeOptionForm.value.field}
                searchable
                on-change={val => handleSettingFieldChange(val)}
              >
                {fieldList.value.map(option => (
                  <bk-option
                    id={option.field_name}
                    key={option.field_name}
                    name={`${option.field_name}(${option.field_alias || option.field_name})`}
                  />
                ))}
              </bk-select>
            )}
          </div>
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
                <bk-radio-group
                  value={gradeOptionForm.value.valueType}
                  onChange={v => handleGradeOptionFormChange('valueType', v)}
                >
                  <bk-radio
                    disabled={gradeOptionForm.value.disabled || gradeOptionForm.value.type === 'normal'}
                    value={GradeFieldValueType.VALUE}
                  >
                    {$t('快速选择')}
                  </bk-radio>
                  <bk-radio
                    style='margin-left: 14px;'
                    disabled={gradeOptionForm.value.disabled || gradeOptionForm.value.type === 'normal'}
                    value={GradeFieldValueType.REGEXP}
                  >
                    {$t('正则表达式')}
                  </bk-radio>
                </bk-radio-group>
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
                      <bk-input
                        value={item.name}
                        on-change={v => handleSettingItemChange(index, 'name', v)}
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
                      <bk-switcher
                        disabled={gradeOptionForm.value.disabled}
                        size='small'
                        theme='primary'
                        value={item.enable}
                        on-change={v => handleSettingItemChange(index, 'enable', v)}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div class='grade-row grade-footer'>
          <bk-button
            style='margin-right: 8px'
            theme='primary'
            onClick={e => handleSaveGradeSettingClick(e, true)}
          >
            {$t('确定')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={e => handleSaveGradeSettingClick(e, false)}
          >
            {$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
