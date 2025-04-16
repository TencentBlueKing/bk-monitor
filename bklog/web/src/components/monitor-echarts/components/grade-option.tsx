import { computed, defineComponent, ref } from 'vue';
import { bkMessage } from 'bk-magic-vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import $http from '@/api';

import './grade-option.scss';

const getDefaultGradeOption = () => {
  return {
    disabled: false,
    type: 'normal',
    field: null,
    settings: [
      {
        id: 'level_1',
        color: '#D46D5D',
        name: 'fatal',
        regExp: '/\\b(?:FATAL|CRITICAL|EMERGENCY)\\b/i',
        enable: true,
      },
      {
        id: 'level_2',
        color: '#F59789',
        name: 'error',
        regExp: '/\\b(?:ERROR|ERR|FAIL(?:ED|URE)?)\\b/i',
        enable: true,
      },
      {
        id: 'level_3',
        color: '#F5C78E',
        name: 'warn',
        regExp: '/\\b(?:WARNING|WARN|ALERT|NOTICE)\\b/i',
        enable: true,
      },
      {
        id: 'level_4',
        color: '#6FC5BF',
        name: 'info',
        regExp: '/\\b(?:INFO|INFORMATION)\\b/i',
        enable: true,
      },
      {
        id: 'level_5',
        color: '#92D4F1',
        name: 'debug',
        regExp: '/\\b(?:DEBUG|DIAGNOSTIC)\\b/i',
        enable: true,
      },
      {
        id: 'level_6',
        color: '#A3B1CC',
        name: 'trace',
        regExp: '/\\b(?:TRACE|TRACING)\\b/i',
        enable: true,
      },
      {
        id: 'others',
        color: '#DCDEE5',
        name: 'others',
        regExp: '--',
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

    const fieldList = computed(() => (store.state.indexFieldInfo.fields ?? []).filter(f => f.es_doc_values));
    const isLoading = ref(false);

    const handleSaveGradeSettingClick = (e: MouseEvent, isSave = true) => {
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
            store.commit('updateIndexSetCustomConfig', { grade_options: gradeOptionForm.value });
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
    };

    const updateOptions = (cfg?) => {
      Object.assign(gradeOptionForm.value, cfg ?? getDefaultGradeOption());
    };

    const handleTypeChange = val => {
      gradeOptionForm.value.type = val;
      if (val === 'normal') {
        gradeOptionForm.value.settings = getDefaultGradeOption().settings;
      }
    };

    expose({
      updateOptions,
    });

    return () => (
      <div v-bkloading={{ isLoading: isLoading.value, size: 'mini' }}>
        <div class='grade-title'>{$t('日志分级展示')}</div>
        <div class='grade-row grade-switcher'>
          <div class='grade-label'>{$t('分级展示')}</div>
          <div class='grade-field-des'>
            <bk-switcher
              theme='primary'
              value={!gradeOptionForm.value.disabled}
              on-change={v => (gradeOptionForm.value.disabled = !v)}
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
                on-change={val => (gradeOptionForm.value.field = val)}
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
                正则表达式
              </div>
              <div
                style='width: 60px'
                class='grade-table-col'
              >
                启用
              </div>
            </div>
            <div class='grade-table-body'>
              {gradeOptionForm.value.settings.map(item => (
                <div
                  class={['grade-table-row', { readonly: item.id === 'others' }]}
                  key={item.id}
                >
                  <div
                    style='width: 46px'
                    class='grade-table-col col-color'
                  >
                    <span style={{ width: '16px', height: '16px', background: item.color, borderRadius: '1px' }}></span>

                    {/* {item.id !== 'others' && (
                      <bk-select
                        style='width: 32px'
                        class='bklog-v3-grade-color-select'
                        value={item.color}
                        clearable={false}
                        behavior='simplicity'
                        ext-popover-cls='bklog-v3-grade-color-list bklog-popover-stop'
                        size='small'
                        on-change={val => (item.color = val)}
                      >
                        {colorList.value.map(option => (
                          <bk-option
                            id={option.name}
                            key={option.id}
                            name={option.name}
                          >
                            <div
                              class='bklog-popover-stop'
                              style={{
                                width: '100%',
                                height: '16px',
                                background: option.name,
                              }}
                            ></div>
                          </bk-option>
                        ))}
                      </bk-select>
                    )} */}
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
                        on-change={v => (item.name = v)}
                      ></bk-input>
                    ) : (
                      item.name
                    )}
                  </div>
                  <div
                    style='width: 330px'
                    class='grade-table-col'
                  >
                    {item.id !== 'others' &&
                    gradeOptionForm.value.type === 'custom' &&
                    !gradeOptionForm.value.disabled ? (
                      <bk-input
                        value={item.regExp}
                        on-change={v => (item.regExp = v)}
                      ></bk-input>
                    ) : (
                      item.regExp
                    )}
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
                        on-change={v => (item.enable = v)}
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
