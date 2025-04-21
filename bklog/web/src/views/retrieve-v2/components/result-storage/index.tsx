import { computed, defineComponent } from 'vue';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  setup() {
    const store = useStore();
    const { $t } = useLocale();

    const isWrap = computed(() => store.state.storage.tableLineIsWrap);
    const jsonFormatDeep = computed(() => store.state.storage.tableJsonFormatDepth);
    const isJsonFormat = computed(() => store.state.storage.tableJsonFormat);
    const isAllowEmptyField = computed(() => store.state.storage.tableAllowEmptyField);
    const showRowIndex = computed(() => store.state.storage.tableShowRowIndex);
    const expandTextView = computed(() => store.state.storage.isLimitExpandView);

    const handleStorageChange = (val, key) => {
      store.commit('updateStorage', { [key]: val });
    };

    const handleJsonFormatDeepChange = val => {
      const value = Number(val);
      const target = value > 15 ? 15 : value < 1 ? 1 : value;
      store.commit('updateStorage', { tableJsonFormatDepth: target });
    };

    return () => (
      <div class='bklog-v3-storage'>
        <bk-checkbox
          style='margin: 0 12px'
          class='bklog-option-item'
          value={showRowIndex.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableShowRowIndex')}
        >
          <span class='switch-label'>{$t('显示行号')}</span>
        </bk-checkbox>
        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={expandTextView.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'isLimitExpandView')}
        >
          <span class='switch-label'>{$t('展开长字段')}</span>
        </bk-checkbox>
        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={isWrap.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableLineIsWrap')}
        >
          <span class='switch-label'>{$t('换行')}</span>
        </bk-checkbox>

        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={isJsonFormat.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableJsonFormat')}
        >
          <span class='switch-label'>{$t('JSON 解析')}</span>
        </bk-checkbox>

        {isJsonFormat.value && (
          <bk-input
            style='margin: 0 12px 0 0'
            class='json-depth-num'
            max={15}
            min={1}
            value={jsonFormatDeep.value}
            type='number'
            on-change={handleJsonFormatDeepChange}
          ></bk-input>
        )}

        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={isAllowEmptyField.value}
          theme='primary'
          on-change="val => handleStorageChange(val, 'tableAllowEmptyField')"
        >
          <span class='switch-label'>{$t('展示空字段')}</span>
        </bk-checkbox>
      </div>
    );
  },
});
