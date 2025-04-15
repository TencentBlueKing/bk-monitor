import { computed, defineComponent, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import useStore from '../../../hooks/use-store';
import './grade-option.scss';

export default defineComponent({
  setup() {
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

    const colorList = ref([
      { id: 'fatal', name: '#D46D5D' },
      { id: 'error', name: '#F59789' },
      { id: 'warn', name: '#F5C78E' },
      { id: 'info', name: '#6FC5BF' },
      { id: 'debug', name: '#92D4F1' },
      { id: 'trace', name: '#A3B1CC' },
    ]);

    const gradeValue = ref('normal');

    /**
     * 分级字段
     */
    const gradeFieldValue = ref(null);

    const gradeSettingList = ref([
      {
        id: 'fatal',
        color: '#D46D5D',
        name: 'fatal',
        regExp: '/\\b(?:FATAL|CRITICAL|EMERGENCY)\\b/i',
      },
      {
        id: 'error',
        color: '#F59789',
        name: 'error',
        regExp: '/\\b(?:ERROR|ERR|FAIL(?:ED|URE)?)\\b/i',
      },
      {
        id: 'warn',
        color: '#F5C78E',
        name: 'warn',
        regExp: '/\\b(?:WARNING|WARN|ALERT|NOTICE)\\b/i',
      },
      {
        id: 'info',
        color: '#6FC5BF',
        name: 'info',
        regExp: '/\\b(?:INFO|INFORMATION)\\b/i',
      },
      {
        id: 'debug',
        color: '#92D4F1',
        name: 'debug',
        regExp: '/\\b(?:DEBUG|DIAGNOSTIC)\\b/i',
      },
      {
        id: 'trace',
        color: '#A3B1CC',
        name: 'trace',
        regExp: '/\\b(?:TRACE|TRACING)\\b/i',
      },
      {
        id: 'others',
        color: '#DCDEE5',
        name: 'others',
        regExp: '--',
      },
    ]);

    const fieldList = computed(() => store.state.indexFieldInfo.fields ?? []);

    const handleSaveGradeSettingClick = () => {
      // (this.$refs.refGradePopover as any)?.hide();
    };

    const handleDeleteConfigItem = () => {};
    const handleAddConfigItem = () => {
      if (gradeSettingList.value.length < 6) {
        gradeSettingList.value.push({
          id: 'info',
          color: '#6FC5BF',
          name: '',
          regExp: '',
        });
      }
    };

    return () => (
      <div>
        <div class='grade-title'>{$t('日志分级展示')}</div>
        <div class='grade-row grade-switcher'>
          <div class='grade-label'>{$t('分级展示')}</div>
          <div class='grade-field-des'>
            <bk-switcher theme='primary'></bk-switcher>
            <span class='bklog-icon bklog-info-fill'></span>
            <span>指定清洗字段后可生效该配置，日志页面将会按照不同颜色清洗分类，最多六个字段</span>
          </div>
        </div>
        <div class='grade-row'>
          <div class='grade-label required'>{$t('字段设置')}</div>
          <div class='grade-field-setting'>
            <bk-select
              style='width: 240px'
              value={gradeValue.value}
              ext-popover-cls='bklog-popover-stop'
              searchable
              on-change={val => (gradeValue.value = val)}
            >
              {gradeCategory.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                ></bk-option>
              ))}
            </bk-select>
            {gradeValue.value === 'custom' && (
              <bk-select
                style='width: 320px; margin-left: 10px'
                ext-popover-cls='bklog-popover-stop'
                value={gradeFieldValue.value}
                searchable
                on-change={val => (gradeFieldValue.value = val)}
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
                style='width: 64px'
                class='grade-table-col'
              >
                颜色
              </div>
              <div
                style='width: 177px'
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
            </div>
            <div class='grade-table-body'>
              {gradeSettingList.value.map(item => (
                <div
                  class={['grade-table-row', { readonly: item.id === 'others' }]}
                  key={item.id}
                >
                  <div
                    style='width: 64px'
                    class='grade-table-col'
                  >
                    <span style={{ width: '16px', height: '16px', background: item.color, borderRadius: '1px' }}></span>

                    {item.id !== 'others' && (
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
                    )}
                  </div>
                  <div
                    style='width: 177px'
                    class='grade-table-col'
                  >
                    {item.name}
                  </div>
                  <div
                    style='width: 330px'
                    class='grade-table-col'
                  >
                    {item.regExp}
                  </div>
                  {item.id !== 'others' && (
                    <div class='grade-table-option'>
                      <span
                        class='bklog-icon bklog-log-plus-circle-shape'
                        onClick={handleAddConfigItem}
                      ></span>
                      <span
                        class='bklog-icon bklog-circle-minus-filled'
                        onClick={handleDeleteConfigItem}
                      ></span>
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
            onClick={handleSaveGradeSettingClick}
          >
            {$t('确定')}
          </bk-button>
          <bk-button
            style='width: 64px; height: 32px'
            theme='default'
            onClick={handleSaveGradeSettingClick}
          >
            {$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
