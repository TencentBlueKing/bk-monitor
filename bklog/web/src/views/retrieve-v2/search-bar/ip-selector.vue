<!-- eslint-disable perfectionist/sort-imports -->
<script setup>
  import { computed, watch, ref } from 'vue';

  import useLocale from '@/hooks/use-locale';
  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import LogIpSelector from '@/components/log-ip-selector/log-ip-selector';
  // #endif
  // #if MONITOR_APP === 'apm' || MONITOR_APP === 'trace'
  // #code const LogIpSelector = () => null;
  // #endif
  const props = defineProps({
    isShow: {
      type: Boolean,
      default: false,
      required: true,
    },
    value: {
      type: Object,
      default: () => ({}),
      required: true,
    },
    bkBizId: {
      type: String,
      required: true,
    },
  });

  const emit = defineEmits(['change', 'input', 'update:isShow']);
  const { $t } = useLocale();

  const propIsShow = computed(() => props.isShow);
  const localIsShow = ref(false);

  watch(propIsShow, () => {
    localIsShow.value = propIsShow.value;
  });

  watch(localIsShow, () => {
    emit('update:isShow', localIsShow.value);
  });

  const nodeType = computed(() => {
    // 当前选择的ip类型
    const selectType = Object.keys(props.value).find(item => props.value[item].length);
    return selectType ?? '';
  });

  const nodeCount = computed(() => {
    // ip选择的数量
    return props.value[nodeType.value]?.length ?? 0;
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

  const showText = computed(() => $t('已选择 {0} 个{1}', { 0: nodeCount.value, 1: nodeUnit.value }));

  const emitChange = value => {
    emit('input', value);
    emit('change', value);
  };

  const handleIpSelectorValueChange = val => {
    const nodeType = Object.keys(val).find(item => val[item].length);
    let newValue = Object.assign({}, props.value);
    if (nodeType) {
      newValue[nodeType] = val[nodeType];
      emitChange(newValue);
      return;
    }

    if (!nodeCount.value) {
      newValue = {};
    }

    emitChange(newValue);
  };
</script>
<template>
  <div>
    {{ showText }}
    <!-- 目标选择器 -->
    <LogIpSelector
      :height="670"
      :key="bkBizId"
      :show-dialog.sync="localIsShow"
      :value="value"
      mode="dialog"
      @change="handleIpSelectorValueChange"
    />
  </div>
</template>
