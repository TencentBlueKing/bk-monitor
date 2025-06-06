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
import { bkMessage } from 'bk-magic-vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import $http from '@/api';

import './grade-option.scss';
import { GradeFieldValueType, GradeSetting } from '../../../views/retrieve-core/interface';
import { parseTableRowData } from '../../../common/util';

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
        name: '默认配置',
      },
      {
        id: 'custom',
        name: '自定义',
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
        const storedValues = gradeOptionForm.value.settings.map(item => item.fieldValue ?? []).flat();
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
                grade_options: JSON.parse(JSON.stringify(gradeOptionForm.value)),
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
      Object.assign(gradeOptionForm.value, JSON.parse(JSON.stringify(target)));
    };

    const handleTypeChange = type => {
      const target = Object.assign({}, gradeOptionForm.value, { type });
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
              value={item.fieldValue}
              searchable
              trigger='focus'
              multiple
              allow-create
              clearable
              list={fieldSearchValueList.value}
              onChange={v => handleSettingItemChange(index, 'fieldValue', v)}
              tpl={data => (
                <div
                  class='bklog-popover-stop'
                  style='line-height: 30px; padding: 0 12px; width: 100%;'
                >
                  {data.name}
                </div>
              )}
            ></bk-tag-input>
          );
        }

        return (
          <bk-input
            value={item.regExp}
            on-change={v => handleSettingItemChange(index, 'regExp', v)}
          ></bk-input>
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
            ></bk-switcher>
            <span class='bklog-icon bklog-info-fill'></span>
            <span>指定清洗字段后可生效该配置，日志页面将会按照不同颜色清洗分类，最多六个字段</span>
          </div>
        </div>
        <div class='grade-row'>
          <div class='grade-label required'>{$t('字段设置')}</div>
          <div class='grade-field-setting'>
            <bk-select
              style='width: 240px'
              value={gradeOptionForm.value.type}
              ext-popover-cls='bklog-popover-stop'
              searchable
              disabled={gradeOptionForm.value.disabled}
              on-change={handleTypeChange}
            >
              {gradeCategory.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                ></bk-option>
              ))}
            </bk-select>
            {gradeOptionForm.value.type === 'custom' && (
              <bk-select
                style='width: 366px; margin-left: 10px'
                ext-popover-cls='bklog-popover-stop'
                value={gradeOptionForm.value.field}
                searchable
                disabled={gradeOptionForm.value.disabled}
                on-change={val => handleSettingFieldChange(val)}
                placeholder={$t('请选择字段')}
              >
                {fieldList.value.map(option => (
                  <bk-option
                    id={option.field_name}
                    key={option.field_name}
                    name={`${option.field_name}(${option.field_alias || option.field_name})`}
                  ></bk-option>
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
                颜色
              </div>
              <div
                style='width: 240px'
                class='grade-table-col'
              >
                字段定义
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
                    value={GradeFieldValueType.VALUE}
                    disabled={gradeOptionForm.value.disabled || gradeOptionForm.value.type === 'normal'}
                  >
                    快速选择
                  </bk-radio>
                  <bk-radio
                    value={GradeFieldValueType.REGEXP}
                    style='margin-left: 14px;'
                    disabled={gradeOptionForm.value.disabled || gradeOptionForm.value.type === 'normal'}
                  >
                    正则表达式
                  </bk-radio>
                </bk-radio-group>
              </div>
              <div
                style='width: 60px'
                class='grade-table-col'
              >
                启用
              </div>
            </div>
            <div class='grade-table-body'>
              {gradeOptionForm.value.settings.map((item, index) => (
                <div
                  class={['grade-table-row', { readonly: item.id === 'others' }]}
                  key={item.id}
                >
                  <div
                    style='width: 46px'
                    class='grade-table-col col-color'
                  >
                    <span style={{ width: '16px', height: '16px', background: item.color, borderRadius: '1px' }}></span>
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
                      ></bk-input>
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
                      class='grade-table-col'
                      style='width: 60px'
                    >
                      <bk-switcher
                        value={item.enable}
                        theme='primary'
                        size='small'
                        disabled={gradeOptionForm.value.disabled}
                        on-change={v => handleSettingItemChange(index, 'enable', v)}
                      ></bk-switcher>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div class='grade-row grade-footer'>
          <bk-button
            style='width: 64px; height: 32px; margin-right: 8px'
            theme='primary'
            onClick={e => handleSaveGradeSettingClick(e, true)}
          >
            {$t('确定')}
          </bk-button>
          <bk-button
            style='width: 64px; height: 32px'
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
