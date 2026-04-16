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

import { computed, defineComponent, reactive, ref, watch } from 'vue';

import draggable from 'vuedraggable';

import http from '@/api';
import { messageWarn } from '@/common/bkmagic';
import BklogPopover from '@/components/bklog-popover';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { SceneType, type FilterFieldConfig, type FilterValues, type SceneConfig, type SceneDimensionValuesResponse } from './types';

import './filter-panel.scss';

export default defineComponent({
  name: 'FilterPanel',
  components: { draggable },
  props: {
    activeScene: {
      type: String,
      default: SceneType.Container,
    },
    filterValues: {
      type: Object as () => FilterValues,
      default: () => ({}),
    },
    displayFields: {
      type: Array as () => string[] | null,
      default: null,
    },
  },
  emits: ['scene-change', 'filter-change', 'clear', 'display-fields-change'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    /** 场景配置列表 */
    const sceneConfigs = computed(() => store.getters['retrieve/sceneConfigList']);

    /** 场景配置加载状态 */
    const sceneLoading = computed(() => store.state.retrieve.sceneConfigs?.is_loading ?? false);

    /** 按需翻译：skipI18n 为 true 时跳过翻译，直接返回原文 */
    const translateLabel = (label: string, skipI18n?: boolean) => (skipI18n ? label : t(label));

    const apiOptions = reactive<Record<string, { loading: boolean; options: Array<{ id: string; name: string }> }>>({});

    const currentScene = computed<SceneConfig | undefined>(() => sceneConfigs.value
      .find(scene => scene.type === props.activeScene),
    );

    /** 拉取 dynamic 类型维度的可选值 */
    const fetchDynamicOptions = async (field: FilterFieldConfig) => {
      const fieldState = getApiFieldState(field.key);
      if (fieldState.loading) return;
      fieldState.loading = true;

      try {
        // 构建级联筛选条件：已选的其他维度值
        const filters: Record<string, string> = {};
        const currentFields = currentScene.value?.fields ?? [];
        for (const f of currentFields) {
          if (f.key !== field.key && props.filterValues[f.key]) {
            filters[f.key] = String(props.filterValues[f.key]);
          }
        }

        const res = await http.request('retrieve/getSceneDimensionValues', {
          data: {
            bk_biz_id: store.state.bkBizId,
            scene: props.activeScene,
            dimension_key: field.key,
            filters: Object.keys(filters).length > 0 ? filters : undefined,
          },
        });

        const data = (res.data ?? res) as SceneDimensionValuesResponse;
        console.log('fetchDynamicOptions data:', data);
        const values = data.values ?? [];
        fieldState.options = values.map(v => ({ id: v, name: v }));
      } catch (err) {
        console.error('fetchDynamicOptions error:', err);
        fieldState.options = [];
      } finally {
        fieldState.loading = false;
      }
    };

    const visibleFields = computed<FilterFieldConfig[]>(() => {
      if (!currentScene.value) return [];
      const allFields = currentScene.value.fields;
      if (!props.displayFields) return allFields;
      return props.displayFields
        .map(key => allFields.find(f => f.key === key))
        .filter(Boolean) as FilterFieldConfig[];
    });

    // ---- 设置显示字段弹窗相关 ----
    const settingPopoverRef = ref<any>(null);
    const editDisplayFields = ref<string[]>([]);

    const editRestFields = computed<FilterFieldConfig[]>(() => {
      if (!currentScene.value) return [];
      const selectedSet = new Set(editDisplayFields.value);
      return currentScene.value.fields.filter(f => !selectedSet.has(f.key));
    });

    const allFieldsOfScene = computed<FilterFieldConfig[]>(() => currentScene.value?.fields ?? []);

    const getFieldLabel = (fieldName: string): string => {
      const field = allFieldsOfScene.value.find(f => f.key === fieldName);
      if (!field) return fieldName;
      return field.name;
    };

    const settingTippyOptions: any = {
      arrow: false,
      hideOnClick: false,
      trigger: 'click',
      interactive: true,
      placement: 'bottom-end',
      theme: 'light',
      onShow: () => {
        if (props.displayFields) {
          editDisplayFields.value = [...props.displayFields];
        } else {
          editDisplayFields.value = allFieldsOfScene.value.map(f => f.key);
        }
      },
    };

    const handleAddField = (fieldName: string) => {
      if (!editDisplayFields.value.includes(fieldName)) {
        editDisplayFields.value = [...editDisplayFields.value, fieldName];
      }
    };

    const handleRemoveField = (fieldName: string) => {
      if (editDisplayFields.value.length <= 1) return;
      editDisplayFields.value = editDisplayFields.value.filter(n => n !== fieldName);
    };

    const handleBeforeHide = (e: MouseEvent) => {
      if ((e.target as HTMLElement)?.closest?.('.bklog-v3-popover-tag')) {
        return false;
      }
      return true;
    };

    const handleAddAllFields = () => {
      editDisplayFields.value = allFieldsOfScene.value.map(f => f.key);
    };

    const handleClearAllFields = () => {
      editDisplayFields.value = [];
    };

    const handleSettingConfirm = () => {
      if (editDisplayFields.value.length === 0) {
        messageWarn(t('筛选字段不能为空'));
        return;
      }
      const allNames = allFieldsOfScene.value.map(f => f.key);
      const isDefault = editDisplayFields.value.length === allNames.length
        && editDisplayFields.value.every((name, i) => name === allNames[i]);
      emit('display-fields-change', isDefault ? null : [...editDisplayFields.value]);
      settingPopoverRef.value?.hide();
    };

    const handleSettingCancel = () => {
      settingPopoverRef.value?.hide();
    };

    const handleSceneChange = (type: string) => {
      if (type === props.activeScene) return;
      emit('scene-change', type);
    };

    const handleFieldChange = (fieldName: string, value: any) => {
      emit('filter-change', { ...props.filterValues, [fieldName]: value });
    };

    const handleClear = () => {
      emit('clear');
    };

    const getFieldValue = (fieldName: string) => {
      return props.filterValues[fieldName] ?? '';
    };

    const getApiFieldState = (fieldName: string) => {
      if (!apiOptions[fieldName]) {
        apiOptions[fieldName] = { loading: false, options: [] };
      }
      return apiOptions[fieldName];
    };

    // 输入框本地缓存
    const localInputValues = ref<Record<string, string>>({});

    // 父组件 filterValues 变化时（切换场景、清空等），同步重置本地缓存
    watch(
      () => props.filterValues,
      (newVal) => {
        const next: Record<string, string> = {};
        for (const [k, v] of Object.entries(newVal ?? {})) {
          if (typeof v === 'string') {
            next[k] = v;
          }
        }
        localInputValues.value = next;
      },
      { immediate: true, deep: true },
    );

    const getLocalInputValue = (fieldName: string) => {
      return localInputValues.value[fieldName] ?? props.filterValues[fieldName] ?? '';
    };

    const handleInputChange = (fieldName: string, value: string) => {
      localInputValues.value = { ...localInputValues.value, [fieldName]: value };
    };

    const handleInputConfirm = (fieldName: string) => {
      const val = localInputValues.value[fieldName] ?? '';
      if (val === (props.filterValues[fieldName] ?? '')) return;
      handleFieldChange(fieldName, val);
    };

    const handleInputClear = (fieldName: string) => {
      localInputValues.value = { ...localInputValues.value, [fieldName]: '' };
      handleFieldChange(fieldName, '');
    };

    const renderSceneTabBar = () => (
      <div class='scene-tab-bar'>
        {sceneConfigs.value.map(scene => (
          <div
            class={['scene-tab-item', { 'is-active': scene.type === props.activeScene }]}
            onClick={() => handleSceneChange(scene.type)}
          >
            {scene.icon && <i class={`bklog-icon ${scene.icon} tab-icon`} />}
            <span class='tab-label'>{translateLabel(scene.label, scene.skipI18n)}</span>
          </div>
        ))}
      </div>
    );

    const renderFilterField = (field: FilterFieldConfig) => {
      if (field.choicesType === 'static' || field.choicesType === 'dynamic') {
        const options = field.choicesType === 'static'
          ? (field.choices ?? [])
          : (getApiFieldState(field.key).options);
        const loading = field.choicesType === 'dynamic' ? (getApiFieldState(field.key).loading ?? false) : false;

        return (
          <div class='filter-field-item' key={field.key}>
            <span class='field-label' v-bk-overflow-tips>{field.name}</span>
            <div class='field-input'>
              <bk-select
                value={getFieldValue(field.key)}
                placeholder={field.placeholder || t('请选择')}
                searchable={field.searchable ?? field.choicesType === 'dynamic'}
                multiple={field.multiple ?? false}
                clearable={true}
                loading={loading}
                on-change={(val: any) => handleFieldChange(field.key, val)}
                on-toggle={(open: boolean) => {
                  if (open && field.choicesType === 'dynamic') {
                    fetchDynamicOptions(field);
                  }
                }}
              >
                {options.map(opt => (
                  <bk-option id={opt.id} name={opt.name} key={opt.id} />
                ))}
              </bk-select>
            </div>
          </div>
        );
      }

      return (
        <div class='filter-field-item' key={field.key}>
          <span class='field-label' v-bk-overflow-tips>{field.name}</span>
          <div class='field-input'>
            <bk-input
              value={getLocalInputValue(field.key)}
              placeholder={field.placeholder || t('请输入')}
              clearable={true}
              on-change={(val: string) => handleInputChange(field.key, val)}
              on-blur={() => handleInputConfirm(field.key)}
              on-enter={() => handleInputConfirm(field.key)}
              on-clear={() => handleInputClear(field.key)}
            />
          </div>
        </div>
      );
    };

    const renderSettingPopover = () => (
      <BklogPopover
        ref={settingPopoverRef}
        options={settingTippyOptions}
        trigger='click'
        beforeHide={handleBeforeHide}
        content-class='scene-fields-setting-popover-content'
        content={() => (
          <div class='scene-fields-setting'>
            <div class='setting-body'>
              <div class='setting-column'>
                <div class='setting-column-title'>
                  <span>{t('待选字段')}({editRestFields.value.length})</span>
                  <span class='text-action' onClick={handleAddAllFields}>{t('全部添加')}</span>
                </div>
                <ul class='setting-field-list'>
                  {editRestFields.value.map(field => (
                    <li class='setting-field-item bklog-v3-popover-tag' key={field.key} onClick={() => handleAddField(field.key)}>
                      <span class='field-name'>{field.name}</span>
                      <i class='bklog-icon bklog-filled-right-arrow add-icon' />
                    </li>
                  ))}
                  {editRestFields.value.length === 0 && (
                    <bk-exception type='empty' scene='part' />
                  )}
                </ul>
              </div>
              <div class='setting-divider'>
                <span class='bklog-icon bklog-double-arrow' />
              </div>
              <div class='setting-column'>
                <div class='setting-column-title'>
                  <span>{t('已选字段')}({editDisplayFields.value.length})</span>
                  <span class='text-action' onClick={handleClearAllFields}>{t('清空')}</span>
                </div>
                <draggable
                  class='setting-field-list'
                  tag='ul'
                  animation={150}
                  ghostClass='setting-ghost'
                  handle='.drag-handle'
                  value={editDisplayFields.value}
                  onInput={(val: string[]) => {
                    editDisplayFields.value = val;
                  }}
                >
                  {editDisplayFields.value.map(name => (
                    <li class='setting-field-item is-selected bklog-v3-popover-tag' key={name} onClick={() => handleRemoveField(name)}>
                      <i class='bklog-icon bklog-ketuodong drag-handle' />
                      <span class='field-name'>{getFieldLabel(name)}</span>
                      <i class='bk-icon icon-close-circle-shape remove-icon' />
                    </li>
                  ))}
                </draggable>
              </div>
            </div>
            <div class='setting-actions'>
              <bk-button theme='primary' size='small' onClick={handleSettingConfirm}>{t('确定')}</bk-button>
              <bk-button size='small' onClick={handleSettingCancel}>{t('取消')}</bk-button>
            </div>
          </div>
        )}
      >
        <span
          class='filter-setting-btn'
          v-bk-tooltips={{ content: t('设置显示字段'), placement: 'top' }}
        >
          <i class='bklog-icon bklog-shezhi' />
        </span>
      </BklogPopover>
    );

    return () => (
      <div class='scene-filter-panel' v-bkloading={{ isLoading: sceneLoading.value }}>
        <div class='scene-filter-top'>
          <div class='top-left'>
            {renderSceneTabBar()}
            <span class='filter-tip'>
              <i class='bk-icon icon-info tip-icon' />
              <i18n path='请先按照 {0} 日志范围后，再进行日志检索！'>
                <span class='tip-underline'>{t('场景过滤')}</span>
              </i18n>
            </span>
          </div>
          <div class='top-right'>
            <span class='filter-clear-btn' onClick={handleClear}>
              {t('清空查询')}
            </span>
            {renderSettingPopover()}
          </div>
        </div>

        <div class='scene-filter-grid'>
          {visibleFields.value.map(field => renderFilterField(field))}
        </div>
      </div>
    );
  },
});
