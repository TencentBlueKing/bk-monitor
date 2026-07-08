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

import { computed, defineComponent, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

import draggable from 'vuedraggable';

import axios from 'axios';
import http from '@/api';
import { messageWarn } from '@/common/bkmagic';
import BklogPopover from '@/components/bklog-popover';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { SceneType, type FilterFieldConfig, type FilterValues, type SceneDimensionValuesResponse, type SceneConfig, type FieldCandidateCondition, type ListFieldCandidatesParams } from './types';
import { getOperatorDisplay, getDefaultOp } from './scene-config';

import './filter-panel.scss';

/** 联想状态 */
interface SuggestionState {
  visible: boolean;
  loading: boolean;
  items: string[];
  count: number;
  page: number;
  keyword: string;
  currentFieldKey: string;
  /** 已选中的项 */
  selectedItems: Set<string>;
}

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
      type: Array as () => Array<[string, string]> | null,
      default: null,
    },
    isSticky: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['scene-change', 'filter-change', 'clear', 'display-fields-change', 'operator-change'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    /** 场景配置列表 */
    const sceneConfigs = computed(() => store.getters['retrieve/sceneConfigList']);

    /** 场景配置加载状态 */
    const sceneLoading = computed(() => store.state.retrieve.sceneConfigs?.is_loading ?? false);

    /** 按需翻译：skipI18n 为 true 时跳过翻译，直接返回原文 */
    const translateLabel = (label: string, skipI18n?: boolean) => (skipI18n ? label : t(label));

    const apiOptions = ref<Record<string, { loading: boolean; options: Array<{ id: string; name: string }> }>>({});

    const currentScene = computed<SceneConfig | undefined>(() => sceneConfigs.value
      .find((scene: { type: string; }) => scene.type === props.activeScene),
    );

    /** 拉取 dynamic 类型维度的可选值 */
    const fetchDynamicOptions = async (field: FilterFieldConfig) => {
      const fieldState = getApiFieldState(field.key);
      if (fieldState.loading) return;
      fieldState.loading = true;

      try {
        // 构建级联筛选条件：已选的其他维度值
        const filters: Array<{ field_name: string; value: string[]; op: string }> = [];
        const currentFields = currentScene.value?.fields ?? [];
        for (const f of currentFields) {
          if (f.key === field.key) continue;
          const fieldValue = props.filterValues[f.key];
          const val = fieldValue?.value;
          if (val == null || val === '' || (Array.isArray(val) && val.length === 0)) continue;
          filters.push({
            field_name: f.key,
            value: Array.isArray(val) ? val.map(String) : [String(val)],
            op: fieldValue.op || 'eq',
          });
        }

        const res = await http.request('retrieve/getSceneDimensionValues', {
          data: {
            bk_biz_id: store.state.bkBizId,
            scene: props.activeScene,
            dimension_key: field.key,
            filters: filters.length > 0 ? filters : undefined,
          },
        });

        const data = (res.data ?? res) as SceneDimensionValuesResponse;
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
        .map(([key]) => allFields.find(f => f.key === key))
        .filter(Boolean) as FilterFieldConfig[];
    });

    // ---- 设置显示字段弹窗相关 ----
    const settingPopoverRef = ref<any>(null);
    const editDisplayFields = ref<Array<[string, string]>>([]);

    const editRestFields = computed<FilterFieldConfig[]>(() => {
      if (!currentScene.value) return [];
      const selectedKeys = new Set(editDisplayFields.value.map(([k]) => k));
      return currentScene.value.fields.filter(f => !selectedKeys.has(f.key));
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
          editDisplayFields.value = allFieldsOfScene.value.map(f => {
            const storedOp = props.filterValues[f.key]?.op;
            return [f.key, storedOp || getDefaultOp(f.ops)] as [string, string];
          });
        }
      },
    };

    const handleAddField = (fieldName: string) => {
      if (!editDisplayFields.value.some(([k]) => k === fieldName)) {
        const field = allFieldsOfScene.value.find(f => f.key === fieldName);
        const defaultOp = getDefaultOp(field?.ops);
        editDisplayFields.value = [...editDisplayFields.value, [fieldName, defaultOp]];
      }
    };

    const handleRemoveField = (fieldName: string) => {
      editDisplayFields.value = editDisplayFields.value.filter(([k]) => k !== fieldName);
    };

    const handleBeforeHide = (e: MouseEvent) => {
      if ((e.target as HTMLElement)?.closest?.('.bklog-v3-popover-tag')) {
        return false;
      }
      return true;
    };

    /** 字段设置中操作符变更（仅修改 editDisplayFields，确认后才同步） */
    const handleEditOperatorChange = (fieldKey: string, newOp: string) => {
      editDisplayFields.value = editDisplayFields.value.map(([k, op]) => (
        k === fieldKey ? [k, newOp] as [string, string] : [k, op] as [string, string]
      ),
      );
    };

    const handleAddAllFields = () => {
      const toAdd: Array<[string, string]> = editRestFields.value.map(f => [
        f.key, getDefaultOp(f.ops)] as [string, string]);
      editDisplayFields.value = [...editDisplayFields.value, ...toAdd];
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
      const editFieldKeys = editDisplayFields.value.map(([k]) => k);
      // 字段 key 顺序与默认一致 且 每个字段的操作符也是默认值时，才算 isDefault
      const isDefaultOrder = editFieldKeys.length === allNames.length
        && editFieldKeys.every((name, i) => name === allNames[i]);
      const isDefault = isDefaultOrder && editDisplayFields.value.every(([k, op]) => {
        const field = allFieldsOfScene.value.find(f => f.key === k);
        return op === getDefaultOp(field?.ops);
      });

      // 找出被移除的字段，清除其选中值
      const prevFieldKeys = props.displayFields ? props.displayFields.map(([k]) => k) : allNames;
      const removedFields = prevFieldKeys.filter(key => !editFieldKeys.includes(key));

      // 同步操作符到 filterValues：更新已有字段的 op，为无值字段创建带 op 的条目
      const newValues = { ...props.filterValues };
      for (const key of removedFields) {
        delete newValues[key];
      }
      for (const [key, op] of editDisplayFields.value) {
        if (newValues[key]) {
          if (newValues[key].op !== op) {
            newValues[key] = { ...newValues[key], op };
          }
        } else {
          newValues[key] = { op, value: [] };
        }
      }
      emit('filter-change', { values: newValues });

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

    const buildLabels = (ids: (string | number)[], opts: Array<{ id: string; name: string }>) => {
      const result: Record<string, string> = {};
      for (const id of ids) {
        const opt = opts.find(o => o.id === id);
        if (opt) result[id as string] = opt.name;
      }
      return Object.keys(result).length ? result : undefined;
    };

    /** 获取字段的当前操作符：filterValues > displayFields > 场景配置默认值 */
    const getFieldOp = (fieldKey: string): string => {
      const stored = props.filterValues[fieldKey]?.op;
      if (stored) return stored;
      // 从 displayFields 中读取用户设置的操作符
      if (props.displayFields) {
        const displayOp = props.displayFields.find(([k]) => k === fieldKey)?.[1];
        if (displayOp) return displayOp;
      }
      const field = currentScene.value?.fields.find(f => f.key === fieldKey);
      return getDefaultOp(field?.ops);
    };

    /** 操作符变更 */
    const handleOperatorChange = (fieldKey: string, newOp: string) => {
      const currentValue = props.filterValues[fieldKey]?.value ?? [];
      emit('filter-change', {
        values: { ...props.filterValues, [fieldKey]: { op: newOp, value: currentValue } },
        operatorChange: { fieldKey, op: newOp },
      });
    };

    const handleFieldChange = (fieldName: string, value: any, fieldLabels?: Record<string, string>) => {
      const currentOp = getFieldOp(fieldName);
      emit('filter-change', {
        values: { ...props.filterValues, [fieldName]: { op: currentOp, value } },
        labels: fieldLabels ? { fieldName, labels: fieldLabels } : undefined,
      });
    };

    const handleClear = () => {
      emit('clear');
    };

    const getApiFieldState = (fieldName: string) => {
      if (!apiOptions.value[fieldName]) {
        apiOptions.value = { ...apiOptions.value, [fieldName]: { loading: false, options: [] } };
      }
      return apiOptions.value[fieldName];
    };

    // 容器场景全量集群列表缓存
    const fullClusterList = ref<Array<{ id: string; name: string }>>([]);

    // 获取容器场景全量集群列表
    const fetchFullClusterList = async () => {
      if (fullClusterList.value.length > 0) return;

      try {
        const res = await http.request('retrieve/getSceneDimensionValues', {
          data: {
            bk_biz_id: store.state.bkBizId,
            scene: SceneType.Container,
            dimension_key: 'cluster_id',
          },
        });

        const data = (res.data ?? res) as SceneDimensionValuesResponse;
        const values = data.values ?? [];
        fullClusterList.value = values.map(v => ({ id: v, name: v }));
      } catch (err) {
        console.error('fetchFullClusterList error:', err);
      }
    };

    // 监听场景变化，容器场景下预加载全量集群列表
    watch(
      () => props.activeScene,
      (newScene) => {
        if (newScene === SceneType.Container) {
          // 切换到容器场景时，预加载全量集群列表
          fetchFullClusterList();
        }
      },
      { immediate: true },
    );

    // ============ 标签输入联想功能 ============
    /** 联想状态 */
    const suggestionState = reactive<SuggestionState>({
      visible: false,
      loading: false,
      items: [],
      count: 0,
      page: 1,
      keyword: '',
      currentFieldKey: '',
      selectedItems: new Set<string>(),
    });

    /** 防抖定时器 */
    let suggestionDebounceTimer: ReturnType<typeof setTimeout> | null = null;
    /** 请求取消执行函数 */
    let suggestionCancelExecutor: (() => void) | null = null;

    /** 重置联想状态 */
    const resetSuggestionState = () => {
      suggestionState.visible = false;
      suggestionState.items = [];
      suggestionState.count = 0;
      suggestionState.page = 1;
      suggestionState.keyword = '';
      suggestionState.currentFieldKey = '';
      suggestionState.selectedItems.clear();

      // 清理防抖定时器
      if (suggestionDebounceTimer) {
        clearTimeout(suggestionDebounceTimer);
        suggestionDebounceTimer = null;
      }
      // 取消未完成的请求
      if (suggestionCancelExecutor) {
        suggestionCancelExecutor();
        suggestionCancelExecutor = null;
      }
    };

    /** 构建联想请求的 conditions 参数 */
    const buildSuggestionConditions = (): FieldCandidateCondition[] => {
      const conditions: FieldCandidateCondition[] = [];
      const currentFields = currentScene.value?.fields ?? [];

      for (const f of currentFields) {
        if (f.key === suggestionState.currentFieldKey) continue;
        // 容器场景下跳过 path 字段
        if (props.activeScene === SceneType.Container && f.key === 'path') continue;
        // 只处理 free_input 类型的字段
        if (f.choicesType !== 'free_input') continue;
        const fieldValue = props.filterValues[f.key];
        const val = fieldValue?.value;
        if (val == null || val === '' || (Array.isArray(val) && val.length === 0)) continue;

        const valueArray = Array.isArray(val) ? val.map(String) : [String(val)];
        // 只有 op 为 eq 时才传递 condition
        if (fieldValue.op === 'eq') {
          conditions.push({
            key: f.key,
            method: 'eq',
            value: valueArray,
          });
        }
      }

      return conditions;
    };

    /** 渲染联想弹窗内容 */
    const renderSuggestionDropdown = (fieldKey: string) => {
      if (suggestionState.items.length === 0) {
        return <li class='field-suggestion-empty' onMousedown={(e: MouseEvent) => e.preventDefault()}>{t('暂无数据')}</li>;
      }
      return suggestionState.items.map((item, index) => {
        const isSelected = suggestionState.selectedItems.has(item);
        return (
          <li
            key={`${fieldKey}-${index}-${item}`}
            title={item}
            class={['field-suggestion-item', { 'is-selected': isSelected }]}
            onMousedown={(e: MouseEvent) => {
              e.preventDefault();
            }}
            onClick={(e: MouseEvent) => {
              handleSelectSuggestion(item);
            }}
          >
            <div class='suggestion-item-content'>{item}</div>
            {isSelected && <i class='bk-icon icon-check-1 suggestion-item-check' />}
          </li>
        );
      }).concat(
        suggestionState.items.length < suggestionState.count && suggestionState.loading
          ? [
              <li key={`${fieldKey}-loading`} class='field-suggestion-loading' onMousedown={(e: MouseEvent) => e.preventDefault()}>
                {t('loading...')}
              </li>,
            ]
          : [],
      );
    };

    /** 请求字段联想数据 */
    const fetchFieldCandidates = async (inputValue: string, loadMore = false) => {
      // 容器场景下 path 字段不调用联想接口
      if (props.activeScene === SceneType.Container && suggestionState.currentFieldKey === 'path') {
        return;
      }
      // 清除防抖定时器
      if (suggestionDebounceTimer) {
        clearTimeout(suggestionDebounceTimer);
        suggestionDebounceTimer = null;
      }

      // 如果不是加载更多且关键词没变且不是首次加载，直接返回
      if (!loadMore && inputValue === suggestionState.keyword && suggestionState.page > 1) {
        return;
      }

      // 取消上一个未完成的请求
      if (suggestionCancelExecutor) {
        suggestionCancelExecutor();
        suggestionCancelExecutor = null;
      }

      suggestionDebounceTimer = setTimeout(async () => {
        if (!suggestionState.visible) return;

        if (!loadMore) {
          suggestionState.page = 1;
          suggestionState.items = [];
        }
        suggestionState.loading = true;

        const params: ListFieldCandidatesParams = {
          space_uid: store.state.indexItem.spaceUid,
          bk_biz_id: store.state.bkBizId,
          scene: props.activeScene,
          resource_type: suggestionState.currentFieldKey,
          conditions: buildSuggestionConditions(),
          query_string: inputValue,
          page: suggestionState.page,
          page_size: 100,
        };

        // 容器场景：必传 bcs_cluster_ids
        if (props.activeScene === SceneType.Container) {
          const clusterIdValue = props.filterValues.cluster_id?.value;
          let clusterIds: string[] = [];

          if (clusterIdValue) {
            // 有选中的集群 ID，使用选中的值
            clusterIds = Array.isArray(clusterIdValue) ? clusterIdValue.map(String) : [String(clusterIdValue)];
          } else {
            // 没有选中集群 ID，使用全量集群列表
            clusterIds = fullClusterList.value.map(opt => String(opt.id));
          }

          params.bcs_cluster_ids = clusterIds;
        }

        // 主机场景：必传 table_id_conditions、start_time、end_time
        if (props.activeScene === SceneType.Host) {
          const retrieveParams = store.getters.retrieveParams;
          params.table_id_conditions = [
            [
              {
                field_name: 'scene',
                value: ['host'],
                op: 'eq',
              }
            ]
          ];
          params.start_time = retrieveParams.start_time;
          params.end_time = retrieveParams.end_time;
        }

        const cancelToken = new axios.CancelToken((c) => {
          suggestionCancelExecutor = c;
        });

        try {
          const res = await http.request('retrieve/listSceneFieldCandidates', {
            data: params,
          }, { cancelToken });

          const data = res.data ?? res;
          suggestionState.items = [...suggestionState.items, ...(data.items ?? [])];
          suggestionState.count = data.count ?? 0;
          suggestionState.keyword = inputValue;
        } catch (err: any) {
          if (axios.isCancel(err)) {
            return;
          }
          console.error('fetchFieldCandidates error:', err);
          suggestionState.items = [];
          suggestionState.count = 0;
        } finally {
          suggestionState.loading = false;
        }
      }, 300);
    };

    /** 处理联想项点击 */
    const handleSelectSuggestion = (item: string) => {
      // 切换选中状态
      if (suggestionState.selectedItems.has(item)) {
        suggestionState.selectedItems.delete(item);
      } else {
        suggestionState.selectedItems.add(item);
      }
      // 更新标签输入框的值
      const currentTags = [...suggestionState.selectedItems];
      handleTagChange(suggestionState.currentFieldKey, currentTags);
    };

    /** 处理加载更多 */
    const handleLoadMoreSuggestions = () => {
      if (suggestionState.loading || suggestionState.items.length >= suggestionState.count) {
        return;
      }
      suggestionState.loading = true;
      suggestionState.page += 1;
      fetchFieldCandidates(suggestionState.keyword, true);
    };

    /** 标签输入框聚焦处理 */
    const handleTagInputFocus = (fieldKey: string) => {
      // 如果是同一个字段，不做处理
      if (suggestionState.currentFieldKey === fieldKey) {
        return;
      }
      // 清除联想状态
      resetSuggestionState();
      // 设置当前字段并显示弹窗
      suggestionState.currentFieldKey = fieldKey;
      suggestionState.visible = true;
      // 同步已有标签到 selectedItems
      const existingTags = localTagValues.value[fieldKey] ?? [];
      suggestionState.selectedItems = new Set(existingTags);
      // 触发首次请求（空输入）
      fetchFieldCandidates('', false);
    };

    /** 标签输入框内容变化处理 */
    const handleTagInputChange = (inputValue: string) => {
      // 重新请求联想数据
      fetchFieldCandidates(inputValue, false);
    };

    /** 点击 tag-input-wrapper 容器外部时关闭弹窗 */
    const handleDocumentMouseDown = (e: MouseEvent) => {
      // 如果弹窗不可见，不需要处理
      if (!suggestionState.visible) {
        return;
      }
      // 点击在任何 tag-input-wrapper 容器内部都不关闭弹窗
      if ((e.target as HTMLElement).closest('.tag-input-wrapper')) {
        return;
      }

      resetSuggestionState();
    };

    /** 绑定/解绑全局 mousedown 事件 */
    const bindMouseDownEvent = () => {
      document.addEventListener('mousedown', handleDocumentMouseDown);
    };

    const unbindMouseDownEvent = () => {
      document.removeEventListener('mousedown', handleDocumentMouseDown);
    };

    // 组件卸载时清理
    onBeforeUnmount(() => {
      resetSuggestionState();
      unbindMouseDownEvent();
    });

    // 组件挂载时绑定事件
    onMounted(() => {
      bindMouseDownEvent();
    });

    // 标签输入本地缓存
    const localTagValues = ref<Record<string, string[]>>({});

    // 当前激活的字段 key，用于控制 z-index 层级
    const activeFieldKey = ref<string>('');
    let blurTimer: ReturnType<typeof setTimeout> | null = null;

    const setActiveField = (key: string) => {
      if (blurTimer) {
        clearTimeout(blurTimer);
        blurTimer = null;
      }
      activeFieldKey.value = key;
    };

    const deactivateField = (key: string) => {
      if (blurTimer) {
        clearTimeout(blurTimer);
      }
      // 延迟取消激活，等待折叠动画完成
      blurTimer = setTimeout(() => {
        if (activeFieldKey.value === key) {
          activeFieldKey.value = '';
        }
        blurTimer = null;
      }, 300);
    };

    // 父组件 filterValues 变化时（切换场景、清空等），同步重置本地缓存
    watch(
      () => props.filterValues,
      (newVal) => {
        const next: Record<string, string[]> = {};
        for (const [k, v] of Object.entries(newVal ?? {})) {
          const rawVal = v?.value ?? v;
          if (Array.isArray(rawVal)) {
            next[k] = rawVal.map(String);
          } else if (typeof rawVal === 'string' && rawVal !== '') {
            next[k] = [rawVal];
          }
        }
        localTagValues.value = next;
      },
      { immediate: true, deep: true },
    );

    const getLocalTagValues = (fieldName: string) => {
      return localTagValues.value[fieldName]
        ?? (Array.isArray(props.filterValues[fieldName]?.value) ? props.filterValues[fieldName].value : []);
    };

    const handleTagChange = (fieldName: string, tags: string[]) => {
      localTagValues.value = { ...localTagValues.value, [fieldName]: tags };
      if (suggestionState.currentFieldKey === fieldName && suggestionState.visible) {
        suggestionState.selectedItems = new Set(tags);
      }
      handleFieldChange(fieldName, tags);
    };

    const handleTagClear = (fieldName: string) => {
      localTagValues.value = { ...localTagValues.value, [fieldName]: [] };
      handleFieldChange(fieldName, []);
    };

    const renderSceneTabBar = () => (
      <div class='scene-tab-bar'>
        {sceneConfigs.value.map((scene: SceneConfig) => (
          <div
            class={[
              'scene-tab-item',
              {
                'is-active': !scene.disabled && scene.type === props.activeScene,
                'is-disabled': scene.disabled,
              },
            ]}
            onClick={() => !scene.disabled && handleSceneChange(scene.type)}
          >
            {scene.icon && <i class={`bklog-icon ${scene.icon} tab-icon`} />}
            <span class='tab-label'>{translateLabel(scene.label, scene.skipI18n)}</span>
          </div>
        ))}
      </div>
    );

    /** 获取 bk-select 的 value，确保多选字段值为数组 */
    const getSelectValue = (field: FilterFieldConfig) => {
      const raw = props.filterValues[field.key]?.value;
      if (raw == null || raw === '') return field.multiple ? [] : '';
      if (field.multiple) {
        const arr = Array.isArray(raw) ? raw : [raw];
        return arr.map(v => String(v));
      }
      return String(raw);
    };

    /** 获取字段的 options，dynamic 类型初始用 currentValue 回显，接口返回后用接口数据 */
    const getFieldOptions = (field: FilterFieldConfig) => {
      if (field.choicesType === 'static') {
        return field.choices ?? [];
      }

      // dynamic：接口已返回数据时优先使用
      const loadedOptions = getApiFieldState(field.key).options;
      if (loadedOptions.length > 0) {
        return loadedOptions;
      }

      // 接口未返回时，从当前值组装临时 options 以支持回显
      const currentValue = props.filterValues[field.key]?.value;
      if (currentValue == null || currentValue === '' || (Array.isArray(currentValue) && currentValue.length === 0)) {
        return [];
      }
      const ids = Array.isArray(currentValue) ? currentValue : [currentValue];
      return ids.map(id => ({ id: String(id), name: String(id) }));
    };

    /** 操作符选择器渲染 */
    const renderOperatorSelector = (
      currentOp: string,
      ops: string[] | undefined,
      // eslint-disable-next-line no-unused-vars
      onChange: (newOp: string) => void,
      options?: {
        label?: string;
        placement?: string;
        choicesType?: string;
        fieldType?: string;
      },
    ) => {
      const { label, placement = 'bottom-start', choicesType, fieldType } = options ?? {};
      let popoverRef: any = null;

      const handleOpClick = (opKey: string) => {
        onChange(opKey);
        popoverRef?.hide();
      };

      const renderContent = () => (
        <ul class='operator-popover-list'>
          {(ops ?? []).map(opKey => (
            <li
              class={['operator-popover-item bklog-v3-popover-tag', { 'is-active': opKey === currentOp }]}
              onClick={() => handleOpClick(opKey)}
            >
              <span class='op-symbol'>{getOperatorDisplay(opKey, choicesType, fieldType)}</span>
            </li>
          ))}
        </ul>
      );

      return (
        <BklogPopover
          ref={(el: any) => {
            if (el) popoverRef = el;
          }}
          trigger='click'
          contentClass='operator-popover-content'
          options={{ appendTo: document.body, arrow: false, offset: [0, 4], placement } as any}
          content={renderContent}
        >
          <span class='field-operator-trigger'>
            {label && <span class='operator-label'>{label}</span>}
            <span class='operator-value'>{getOperatorDisplay(currentOp, choicesType, fieldType)}</span>
          </span>
        </BklogPopover>
      );
    };

    const renderFilterField = (field: FilterFieldConfig) => {
      const isFieldActive = activeFieldKey.value === field.key;
      const currentOp = getFieldOp(field.key);

      if (field.choicesType === 'static' || field.choicesType === 'dynamic') {
        const options = getFieldOptions(field);
        const loading = field.choicesType === 'dynamic' ? (getApiFieldState(field.key).loading ?? false) : false;

        return (
          <div class='filter-field-item' key={field.key}>
            <div class='field-label-row'>
              <span class='field-label' v-bk-overflow-tips>{field.name}</span>
              {renderOperatorSelector(
                currentOp,
                field.ops,
                newOp => handleOperatorChange(field.key, newOp),
                { choicesType: field.choicesType, fieldType: field.fieldType },
              )}
            </div>
            <div class={['field-input', 'is-fixed-layout', { 'is-active': isFieldActive }]}>
              <div class='field-input-placeholder' />
              <bk-select
                value={getSelectValue(field)}
                placeholder={field.placeholder || t('请选择')}
                multiple={field.multiple}
                clearable={true}
                loading={loading}
                display-tag
                on-change={(val: any) => {
                  const selectedIds = Array.isArray(val) ? val : (val !== null && val !== '' ? [val] : []);
                  handleFieldChange(field.key, val, buildLabels(selectedIds, options));
                }}
                on-toggle={(open: boolean) => {
                  if (open) {
                    setActiveField(field.key);
                    if (field.choicesType === 'dynamic') {
                      fetchDynamicOptions(field);
                    }
                  } else {
                    deactivateField(field.key);
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
          <div class='field-label-row'>
            <span class='field-label' v-bk-overflow-tips>{field.name}</span>
            {renderOperatorSelector(
              currentOp,
              field.ops,
              newOp => handleOperatorChange(field.key, newOp),
              { choicesType: field.choicesType, fieldType: field.fieldType },
            )}
          </div>
          <div class={['field-input', 'is-fixed-layout', { 'is-active': isFieldActive }]}>
            <div class='field-input-placeholder' />
            <div class='tag-input-wrapper'>
              <bk-tag-input
                value={getLocalTagValues(field.key)}
                placeholder={field.placeholder}
                allow-create={true}
                has-delete-icon={true}
                allow-next-focus={true}
                clearable={true}
                free-paste={true}
                collapse-tags={true}
                on-change={(tags: string[]) => handleTagChange(field.key, tags)}
                on-removeAll={() => handleTagClear(field.key)}
                on-focus={() => {
                  setActiveField(field.key);
                  handleTagInputFocus(field.key);
                }}
                on-inputchange={(inputValue: string) => handleTagInputChange(inputValue)}
              />
              {/* 联想弹窗 */}
              {suggestionState.visible && suggestionState.currentFieldKey === field.key && (
                <ul
                  class='field-suggestion-dropdown'
                  v-bkloading={{ isLoading: suggestionState.loading }}
                  on-scroll={(e: Event) => {
                    const target = e.target as HTMLElement;
                    if (target.scrollTop + target.clientHeight >= target.scrollHeight - 50) {
                      handleLoadMoreSuggestions();
                    }
                  }}
                >
                  {renderSuggestionDropdown(field.key)}
                </ul>
              )}
            </div>
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
                  onInput={(val: Array<[string, string]>) => {
                    editDisplayFields.value = val;
                  }}
                >
                  {editDisplayFields.value.map(([name, op]) => {
                    const field = allFieldsOfScene.value.find(f => f.key === name);
                    return (
                      <li class='setting-field-item is-selected bklog-v3-popover-tag' key={name} onClick={() => handleRemoveField(name)}>
                        <i class='bklog-icon bklog-ketuodong drag-handle' onClick={e => e.stopPropagation()} />
                        <span class='field-name'>{getFieldLabel(name)}</span>
                        <span class='setting-field-operator' onClick={e => e.stopPropagation()}>
                          {renderOperatorSelector(
                            op,
                            field?.ops,
                            newOp => handleEditOperatorChange(name, newOp),
                            { label: `${t('默认操作符')}：`, placement: 'bottom-end', choicesType: field?.choicesType, fieldType: field?.fieldType },
                          )}
                        </span>
                        <i class='bk-icon icon-close-circle-shape remove-icon' />
                      </li>
                    );
                  })}
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
      <div
        class='scene-filter-panel'
        v-bkloading={{ isLoading: sceneLoading.value }}
        style={{ opacity: props.isSticky ? 0 : 1 }}
      >
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
