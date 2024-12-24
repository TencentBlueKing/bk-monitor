<script setup>
  import { computed, ref, nextTick } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import { excludesFields } from './const.common';

  const props = defineProps({});
  const emit = defineEmits(['refresh']);
  const { $t } = useLocale();
  const store = useStore();

  const fieldList = computed(() => store.state.indexFieldInfo.fields);

  // 表单ref
  const popoverFormRef = ref();
  const settingData = ref({
    filterFields: [],
  });

  const filterFieldList = computed(() => {
    const filterFn = field => field.field_type !== '__virtual__' && !excludesFields.includes(field.field_name);
    // todo 后续这里的select下拉框增加创建自定义选项功能时，这个filterHasOptionListFn函数需要删掉
    const filterHasOptionListFn = field =>
      !store.state.indexFieldInfo.aggs_items[field.field_name]?.length &&
      field.es_doc_values &&
      ['keyword', 'integer', 'long', 'double', 'bool', 'conflict'].includes(field.field_type) &&
      !/^__dist_/.test(field.field_name);
    return fieldList.value.filter(filterFn && filterHasOptionListFn);
  });

  const filterFieldsList = computed(() => {
    return store.state.retrieve.catchFieldCustomConfig?.filterSetting?.filterFields;
  });

  // 新建提交逻辑
  const handleCreateRequest = async () => {
    const selectFilterField = settingData.value.filterFields;
    const filterFieldLists = filterFieldList.value.filter(el => selectFilterField.includes(el.field_name));
    const param = {
      filterSetting: {
        filterFields: filterFieldLists,
      },
    };
    store.dispatch('userFieldConfigChange', param).then(res => {
      if (res.code === 0) {
        window.mainComponent.messageSuccess($t('提交成功'));
        hidePopover();
      }
    });
  };
  // 提交表单校验
  const handleSubmitFormData = () => {
    popoverFormRef.value.validate().then(() => {
      handleCreateRequest();
    });
  };

  // 取消提交逻辑
  const handleCancelRequest = () => {
    popoverShow.value = false;
    popoverContentRef.value.hideHandler();
  };

  // popover组件Ref
  const popoverContentRef = ref();
  // 弹窗显示字段控制
  const popoverShow = ref(false);
  // 弹窗按钮打开逻辑
  const handleCollection = () => {
    popoverShow.value ? hidePopover() : showPopover();
  };

  const showPopover = async () => {
    popoverShow.value = true;
    popoverContentRef.value.showHandler();
    settingData.value.filterFields = filterFieldsList?.value?.map(item => item?.field_name ?? '') || [];
  };

  const hidePopover = () => {
    popoverShow.value = false;
    popoverContentRef.value.hideHandler();
  };

  const handlePopoverShow = () => {
    // 界面初始化隐藏弹窗样式
    nextTick(() => {
      if (!popoverShow.value) {
        popoverContentRef.value.hideHandler();
      }
    });
  };
  const tippyOptions = {
    theme: 'light',
    placement: 'top',
    offset: '22',
    interactive: true,
    trigger: 'manual',
  };

  const handlePopoverHide = () => {
    popoverShow.value = false;
  };
</script>
<template>
  <bk-popover
    ref="popoverContentRef"
    :style="{
      lineHeight: 1,
    }"
    width="400"
    ext-cls="filter-setting-popover"
    :on-hide="handlePopoverHide"
    :on-show="handlePopoverShow"
    :tippy-options="tippyOptions"
  >
    <span
      :style="{
        color: popoverShow ? '#3a84ff' : '',
      }"
      class="bklog-icon bklog-jiansuo"
      @click="handleCollection"
      ><slot></slot
    ></span>
    <template #content>
      <div>
        <div class="popover-title-content">
          <p class="dialog-title">{{ $t('常用查询设置') }}</p>
        </div>
        <bk-form
          ref="popoverFormRef"
          :label-width="100"
          :model="settingData"
        >
          <bk-form-item
            :property="'filterFields'"
            :label="$t('常用过滤字段')"
          >
            <bk-select
              ext-cls="add-popover-new-page-container"
              v-model="settingData.filterFields"
              :popover-options="{ appendTo: 'parent' }"
              :placeholder="$t('请选择常用过滤字段')"
              searchable
              multiple
            >
              <bk-option
                v-for="item in filterFieldList"
                :id="item.field_name"
                :key="item.field_name"
                :name="`${item.field_alias ? item.field_alias : item.field_name}`"
              ></bk-option>
            </bk-select>
          </bk-form-item>
        </bk-form>
      </div>
      <div class="popover-footer">
        <div class="footer-button">
          <bk-button
            style="margin-right: 8px"
            size="small"
            theme="primary"
            @click.stop.prevent="handleSubmitFormData"
            >{{ $t('确定') }}</bk-button
          >
          <bk-button
            size="small"
            theme="default"
            @click.stop.prevent="handleCancelRequest"
            >{{ $t('取消') }}</bk-button
          >
        </div>
      </div>
    </template>
  </bk-popover>
</template>
<style lang="scss">
  @import './setting-pop.scss';
</style>
