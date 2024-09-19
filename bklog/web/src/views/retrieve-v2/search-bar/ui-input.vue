<script setup>
  import { ref, computed, set } from 'vue';

  import { getOperatorKey } from '@/common/util';
  import LogIpSelector from '@/components/log-ip-selector/log-ip-selector';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import {
    getInputQueryDefaultItem,
    getInputQueryIpSelectItem,
    FulltextOperatorKey,
    FulltextOperator,
  } from './const.common';
  import UiInputOptions from './ui-input-option.vue';
  import useFocusInput from './use-focus-input';

  import { debounce } from 'lodash';

  const props = defineProps({
    value: {
      type: Array,
      required: true,
      default: () => [],
    },
  });

  /**
   * 格式化搜索标签渲染格式
   * @param {*} item
   */
  const formatModelValueItem = item => {
    const key = item.field === '*' ? getOperatorKey(`*${item.operator}`) : getOperatorKey(item.operator);
    const label = operatorDictionary.value[key]?.label ?? item.operator;
    if (!Array.isArray(item.value)) item.value = item.value.split(',');
    if (!item.relation) item.relation = 'OR';
    return { operator_label: label, disabled: false, ...item };
  };

  const emit = defineEmits(['input', 'change', 'height-change']);
  const store = useStore();
  const { $t } = useLocale();

  const showIpSelectorDialog = ref(false);
  const cacheIpChooser = ref({});
  const dialogIpChooser = ref({});
  const bkBizId = computed(() => store.state.bkBizId);
  const ipChooser = computed(() => store.getters.retrieveParams.ip_chooser);

  const nodeType = computed(() => {
    // 当前选择的ip类型
    return Object.keys(ipChooser.value || [])?.[0] ?? '';
  });

  const nodeCount = computed(() => {
    // ip选择的数量
    return ipChooser.value[nodeType.value]?.length ?? 0;
  });

  const nodeUnit = computed(() => {
    // ip单位
    const nodeTypeTextMap = {
      node_list: $t('节点'),
      host_list: $t('IP'),
      service_template_list: $t('服务模板'),
      set_template_list: $t('集群模板'),
      dynamic_group_list: $t('动态分组'),
    };
    return nodeTypeTextMap[nodeType.value] || '';
  });

  const handleHeightChange = height => {
    emit('height-change', height);
  };

  const operatorDictionary = computed(() => {
    const defVal = {
      [getOperatorKey(FulltextOperatorKey)]: { label: $t('包含'), operator: FulltextOperator },
    };
    return {
      ...defVal,
      ...store.state.operatorDictionary,
    };
  });

  const refPopInstance = ref(null);
  const refUlRoot = ref(null);
  const refSearchInput = ref(null);
  const queryItem = ref('');
  const activeIndex = ref(null);
  const isInputFocus = ref(false);
  const isOptionShowing = ref(false);
  let delayItemClickFn = undefined;

  const { modelValue, inputValue, hideTippyInstance, getTippyInstance, handleInputBlur, delayShowInstance } =
    useFocusInput(props, {
      onHeightChange: handleHeightChange,
      formatModelValueItem,
      refContent: refPopInstance,
      onShowFn: () => {
        isOptionShowing.value = true;
        refPopInstance.value?.beforeShowndFn?.();
      },
      onHiddenFn: () => {
        refPopInstance.value?.afterHideFn?.();
        isOptionShowing.value = false;

        // inputValue.value = '';
        handleInputBlur();

        delayItemClickFn?.();
        delayItemClickFn = undefined;
        return true;
      },
    });

  const debounceShowInstance = debounce(() => {
    const target = refSearchInput.value.closest('.search-item');
    delayShowInstance(target);
  }, 300);

  /**
   * 执行点击弹出操作项方法
   * @param {*} target 目标元素
   */
  const showTagListItems = target => {
    // 如果当前实例是弹出状态
    // 本次弹出操作需要在当前弹出实例收起之后再执行
    // delayItemClickFn 函数会在实例 onHidden 之后执行
    if (isOptionShowing.value) {
      delayItemClickFn = () => {
        delayShowInstance(target);
      };
      return;
    }

    delayShowInstance(target);
  };

  const handleIpSelectorValueChange = value => {
    const IPSelectIndex = modelValue.value.findIndex(item => item.field === '_ip-select_');
    cacheIpChooser.value = value;
    store.commit('updateIndexItemParams', {
      ip_chooser: value,
    });
    if (!nodeCount.value && IPSelectIndex >= 0) {
      handleDeleteTagItem(IPSelectIndex);
      store.commit('updateIndexItemParams', {
        ip_chooser: {},
      });
      return;
    }
    if (IPSelectIndex >= 0) {
      modelValue.value[IPSelectIndex].value = [$t('已选择 {0} 个{1}', { 0: nodeCount.value, 1: nodeUnit.value })];
    } else {
      if (!nodeCount.value) {
        store.commit('updateIndexItemParams', {
          ip_chooser: {},
        });
        return;
      }
      let targetValue = formatModelValueItem(
        getInputQueryIpSelectItem($t('已选择 {0} 个{1}', { 0: nodeCount.value, 1: nodeUnit.value })),
      );
      modelValue.value.push({ ...targetValue, disabled: false });
    }
    emitChange(modelValue.value);
  };

  const getMatchName = field => {
    if (field === '*') return $t('全文');
    if (field === '_ip-select_') return $t('IP目标');
    return field;
  };

  const emitChange = value => {
    emit('input', value);
    emit('change', value);
  };

  const handleAddItem = e => {
    isInputFocus.value = false;
    const target = e.target.closest('.search-item');
    queryItem.value = '';
    activeIndex.value = null;
    showTagListItems(target);
  };

  const handleTagItemClick = (e, item, index) => {
    if (item.field === '_ip-select_') {
      const isHaveIpChooser = !!Object.keys(ipChooser.value).length;
      dialogIpChooser.value = isHaveIpChooser ? ipChooser.value : cacheIpChooser;
      showIpSelectorDialog.value = true;
      return;
    }
    queryItem.value = {};
    isInputFocus.value = false;
    if (!Array.isArray(item.value)) item.value = item.value.split(',');
    if (!item.relation) item.relation = 'OR';
    Object.assign(queryItem.value, item);
    const target = e.target.closest('.search-item');
    activeIndex.value = isInputFocus.value ? null : index;
    showTagListItems(target);
  };

  const handleDisabledTagItem = item => {
    set(item, 'disabled', !item.disabled);
    if (item.field === '_ip-select_') {
      store.commit('updateIndexItemParams', {
        ip_chooser: item.disabled ? {} : cacheIpChooser.value,
      });
    }
    emitChange(modelValue.value);
  };

  const handleDeleteTagItem = (index, item) => {
    if (item?.field === '_ip-select_') {
      store.commit('updateIndexItemParams', {
        ip_chooser: {},
      });
    }
    modelValue.value.splice(index, 1);
    emitChange(modelValue.value);
  };

  const handleSaveQueryClick = payload => {
    const isPayloadValueEmpty = !(payload?.value?.length ?? 0);
    const isFulltextEnterVlaue = isInputFocus.value && isPayloadValueEmpty && !payload?.field;

    if (payload === 'ip-select-show') {
      const isHaveIpChooser = !!Object.keys(ipChooser.value).length;
      dialogIpChooser.value = isHaveIpChooser ? ipChooser.value : cacheIpChooser;
      showIpSelectorDialog.value = true;
      getTippyInstance()?.hide();
      return;
    }

    // 如果是全文检索，未输入任何内容就点击回车
    // 此时提交无任何意义，禁止后续逻辑
    if (isFulltextEnterVlaue && !inputValue.value) {
      return;
    }

    let targetValue = formatModelValueItem(isFulltextEnterVlaue ? getInputQueryDefaultItem(inputValue.value) : payload);
    getTippyInstance()?.hide();

    if (isInputFocus.value) {
      inputValue.value = '';

      // nextTick(() => {
      //   refSearchInput.value?.focus();
      //   handleFocusInput({ target: refSearchInput.value });
      // });
    }

    if (activeIndex.value !== null && activeIndex.value >= 0) {
      Object.assign(modelValue.value[activeIndex.value], targetValue);
      emitChange(modelValue.value);
      return;
    }

    modelValue.value.push({ ...targetValue, disabled: false });
    emitChange(modelValue.value);
  };

  const handleInputValueEnter = () => {
    if (!(getTippyInstance().state.isShown ?? false)) {
      handleSaveQueryClick(undefined);
    }
  };

  const handleFullTextInputBlur = e => {
    console.log('handleFullTextInputBlur')
    if (!getTippyInstance()?.state?.isShown) {
      inputValue.value = '';
      handleInputBlur(e);
    }
  };

  const handleCancelClick = () => {
    getTippyInstance()?.hide();
  };

  const handleFocusInput = () => {
    isInputFocus.value = true;
    activeIndex.value = null;
    queryItem.value = '';
    debounceShowInstance();
  };

  const handleInputValueChange = () => {
    if (inputValue.value.length && !getTippyInstance()?.state?.isShown) {
      debounceShowInstance();
    }
  };

  const needDeleteItem = ref(false);
  const handleDeleteItem = e => {
    if (e.target.value) {
      needDeleteItem.value = false;
    }

    if (!e.target.value) {
      if (needDeleteItem.value) {
        if (modelValue.value.length >= 1) {
          modelValue.value.splice(-1, 1);
          emitChange(modelValue.value);

          hideTippyInstance();
        }
      }

      needDeleteItem.value = true;
    }
  };
</script>

<template>
  <ul
    ref="refUlRoot"
    class="search-items"
  >
    <li
      class="search-item btn-add"
      @click.stop="handleAddItem"
    >
      <div class="tag-add">+</div>
      <div class="tag-text">{{ $t('添加条件') }}</div>
    </li>
    <li
      v-for="(item, index) in modelValue"
      :class="['search-item', 'tag-item', { disabled: item.disabled }]"
      :key="`${item.field}-${index}`"
      @click.stop="e => handleTagItemClick(e, item, index)"
    >
      <div class="tag-row match-name">
        {{ getMatchName(item.field) }}
        <span
          class="symbol"
          :data-operator="item.operator"
          >{{ item.operator_label }}</span
        >
      </div>
      <div class="tag-row match-value">
        <template v-if="Array.isArray(item.value)">
          <span
            v-for="(child, childInex) in item.value"
            :key="childInex"
          >
            <span class="match-value-text">{{ child }}</span>
            <span
              v-if="childInex < item.value.length - 1"
              class="match-value-relation"
              >{{ item.relation }}</span
            >
          </span>
        </template>
        <template v-else>
          <span>{{ item.value }}</span>
        </template>
      </div>
      <div class="tag-options">
        <span
          :class="[
            'bklog-icon',
            { 'bklog-eye': !item.disabled, disabled: item.disabled, 'bklog-eye-slash': item.disabled },
          ]"
          @click.stop="e => handleDisabledTagItem(item, e)"
        ></span>
        <span
          class="bk-icon icon-close"
          @click.stop="() => handleDeleteTagItem(index, item)"
        ></span>
      </div>
    </li>
    <li class="search-item is-focus-input">
      <input
        ref="refSearchInput"
        class="tag-option-focus-input"
        v-model="inputValue"
        type="text"
        @blur="handleFullTextInputBlur"
        @focus.stop="handleFocusInput"
        @keyup.delete="handleDeleteItem"
        @keyup.enter="handleInputValueEnter"
        @input="handleInputValueChange"
      />
    </li>
    <div style="display: none">
      <UiInputOptions
        ref="refPopInstance"
        :is-input-focus="isInputFocus"
        :value="queryItem"
        @cancel="handleCancelClick"
        @save="handleSaveQueryClick"
      ></UiInputOptions>
    </div>
    <!-- 目标选择器 -->
    <LogIpSelector
      :height="670"
      :key="bkBizId"
      :show-dialog.sync="showIpSelectorDialog"
      :value="dialogIpChooser"
      mode="dialog"
      @change="handleIpSelectorValueChange"
    />
  </ul>
</template>
<style scoped>
  @import './ui-input.scss';
  @import 'tippy.js/dist/tippy.css';
</style>
<style>
  .tippy-box {
    &[data-theme='log-light'] {
      color: #63656e;
      background-color: #fff;
      box-shadow: 0 2px 6px 0 #0000001a;

      .tippy-content {
        padding: 0;
      }

      .tippy-arrow {
        color: #fff;

        &::after {
          background-color: #fff;
          box-shadow: 0 2px 6px 0 #0000001a;
        }
      }
    }
  }
</style>
