<script setup>
  import { computed, ref, nextTick } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import $http from '../../../api';

  const props = defineProps({
    sql: {
      default: '',
      type: String,
      required: true,
    },
  });
  const emit = defineEmits(['refresh']);
  const { $t } = useLocale();
  const store = useStore();

  const indexSetItem = computed(() => store.state.indexItem);

  // 用于展示索引集
  // 这里返回数组，展示 index_set_name 字段
  const indexSetItemList = computed(() => store.state.indexItem.items);
  const indexSetName = computed(() => {
    return indexSetItemList.value?.map(item => item?.index_set_name).join(',');
  });
  const collectGroupList = computed(() => store.state.favoriteList);
  const favStrList = computed(() => store.state.favoriteList.map(item => item.name));
  const unknownGroupID = computed(() => collectGroupList.value[collectGroupList.value.length - 1]?.group_id);
  // 表单ref
  const popoverFormRef = ref();
  const favoriteData = ref({
    // 收藏参数
    space_uid: -1,
    index_set_id: -1,
    name: '',
    group_id: undefined,
    created_by: '',
    params: {
      host_scopes: {
        modules: [],
        ips: '',
        target_nodes: [],
        target_node_type: '',
      },
      addition: [],
      keyword: null,
      search_fields: [],
    },
    is_enable_display_fields: false,
    index_set_ids: [],
    index_set_name: '',
    index_set_names: [],
    visible_type: 'public',
    display_fields: [],
  });
  const spaceUid = computed(() => store.state.spaceUid);
  const isShowAddGroup = ref(true); // 是否新增组
  const verifyData = ref({
    groupName: '',
  }); // 组名称
  const checkName = () => {
    if (verifyData.value.groupName.trim() === '') return true;
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      verifyData.value.groupName.trim(),
    );
  };

  const checkExistName = () => {
    return !collectGroupList.value.some(item => item.name === verifyData.value.groupName);
  };
  const checkSpecification = () => {
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      favoriteData.value.name.trim(),
    );
  };
  const checkCannotUseName = () => {
    return ![$t('个人收藏'), $t('未分组')].includes(favoriteData.value.name.trim());
  };

  /** 判断是否收藏名是否重复 */
  const checkRepeatName = () => {
    return !favStrList.value.includes(favoriteData.value.name);
  };
  const rules = {
    name: [
      {
        required: true,
        trigger: 'blur',
      },
      {
        validator: checkSpecification,
        message: $t('{n}不规范, 包含特殊符号', { n: $t('收藏名') }),
        trigger: 'blur',
      },
      {
        validator: checkRepeatName,
        message: $t('收藏名重复'),
        trigger: 'blur',
      },
      {
        validator: checkCannotUseName,
        message: $t('保留名称，不可使用'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: $t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
    ],
  };

  // 组名称新增规则
  const groupNameRules = {
    groupName: [
      {
        validator: checkName,
        message: $t('{n}不规范, 包含特殊符号', { n: $t('组名') }),
        trigger: 'blur',
      },
      {
        validator: checkExistName,
        message: $t('组名重复'),
        trigger: 'blur',
      },
      {
        required: true,
        message: $t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: $t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
    ],
  };

  // 新增组表单ref
  const checkInputFormRef = ref();

  // 确认新增组事件
  const handleCreateGroup = () => {
    checkInputFormRef.value.validate().then(async () => {
      const data = { name: verifyData.value.groupName, space_uid: spaceUid.value };
      try {
        const res = await $http.request('favorite/createGroup', {
          data,
        });
        if (res.result) {
          // 获取最新组列表
          store.dispatch('requestFavoriteList');
          window.mainComponent.messageSuccess($t('操作成功'));
        }
      } catch (error) {
      } finally {
        isShowAddGroup.value = true;
        verifyData.value.groupName = '';
      }
    });
  };
  // 组选择事件
  const handleSelectGroup = nVal => {
    if (collectGroupList.value.length > 0) {
      const visibleType = nVal === collectGroupList.value[0].group_id ? 'private' : 'public';
      Object.assign(favoriteData.value, { visibleType });
    }
  };

  // 新建提交逻辑
  const handleCreateRequest = async () => {
    const { name, group_id, display_fields, visible_type, id, is_enable_display_fields } = favoriteData.value;
    const data = {
      name,
      group_id,
      display_fields,
      visible_type,
      keyword: props.sql,
      is_enable_display_fields,
      index_set_name: indexSetName.value,
      search_mode: 'sql',
      index_set_ids: [],
      index_set_names: [],
    };

    Object.assign(data, {
      index_set_id: store.state.indexId,
      space_uid: spaceUid.value,
    });

    if (indexSetItem.value.isUnionIndex) {
      Object.assign(data, {
        index_set_ids: indexSetItem.value.ids,
        index_set_names: indexSetItemList.value?.map(item => item?.index_set_name),
        space_uid: spaceUid.value,
      });
    }

    const requestStr = 'createFavorite';
    try {
      const res = await $http.request(`favorite/${requestStr}`, {
        params: { id },
        data,
      });
      if (res.result) {
        // 新增成功
        // 获取最新组列表
        window.mainComponent.messageSuccess($t('收藏成功'));
        hidePopover();
        store.dispatch('requestFavoriteList');
        favoriteData.value.name = '';
        favoriteData.value.group_id = undefined;
        verifyData.value.groupName = '';
        emit('refresh', true);
      }
    } catch (error) {}
  };
  // 提交表单校验
  const handleSubmitFormData = () => {
    popoverFormRef.value.validate().then(() => {
      if (!unknownGroupID.value) return;
      // 未选择组则新增到未分组中
      if (!favoriteData.value.group_id) favoriteData.value.group_id = unknownGroupID.value;
      handleCreateRequest();
    });
  };

  // 取消提交逻辑
  const handleCancelRequest = () => {
    popoverShow.value = false;
    favoriteData.value.name = '';
    favoriteData.value.group_id = undefined;
    verifyData.value.groupName = '';
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
  const showPopover = () => {
    popoverShow.value = true;
    popoverContentRef.value.showHandler();
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
    placement: 'bottom-end',
    offset: '22',
  };
</script>
<template>
  <bk-popover
    ref="popoverContentRef"
    width="400"
    ext-cls="collection-favorite-popover"
    :always="true"
    :on-show="handlePopoverShow"
    :tippy-options="tippyOptions"
  >
    <span
      :style="{
        color: popoverShow ? '#3a84ff' : '',
      }"
      class="bklog-icon bklog-star-line"
      @click="handleCollection"
    ></span>
    <template #content>
      <div>
        <div class="popover-title-content">
          <p class="dialog-title">{{ $t('新建收藏') }}</p>
        </div>
        <bk-form
          ref="popoverFormRef"
          :label-width="200"
          :model="favoriteData"
          :rules="rules"
          form-type="vertical"
        >
          <bk-form-item
            :property="'name'"
            label="收藏名称"
            required
          >
            <bk-input
              v-model="favoriteData.name"
              placeholder="请输入收藏名称"
            ></bk-input>
          </bk-form-item>
          <bk-form-item
            :property="'project'"
            label="所属分组"
          >
            <bk-select
              v-model="favoriteData.group_id"
              ext-popover-cls="add-popover-new-page-container"
              placeholder="未编组"
              searchable
              @change="handleSelectGroup"
            >
              <bk-option
                v-for="item in collectGroupList"
                :id="item.group_id"
                :key="item.group_id"
                :name="item.group_name"
              ></bk-option>

              <template #extension>
                <div class="favorite-group-extension">
                  <div
                    v-if="isShowAddGroup"
                    class="select-add-new-group"
                    @click="isShowAddGroup = false"
                  >
                    <div><i class="bk-icon icon-plus-circle"></i> {{ $t('新增') }}</div>
                  </div>
                  <div
                    v-else
                    class="add-new-page-input"
                  >
                    <bk-form
                      ref="checkInputFormRef"
                      style="width: 100%"
                      :label-width="0"
                      :model="verifyData"
                      :rules="groupNameRules"
                    >
                      <bk-form-item property="groupName">
                        <bk-input
                          v-model="verifyData.groupName"
                          :placeholder="$t('{n}, （长度30个字符）', { n: $t('请输入组名') })"
                          clearable
                        ></bk-input>
                      </bk-form-item>
                    </bk-form>
                    <div class="operate-button">
                      <span
                        style="color: #33d05c"
                        class="bk-icon icon-check-line"
                        @click="handleCreateGroup"
                      ></span>
                      <span
                        class="bk-icon icon-close-line-2"
                        @click="
                          () => {
                            isShowAddGroup = true;
                            verifyData.groupName = '';
                          }
                        "
                      ></span>
                    </div>
                  </div>
                </div>
              </template>
            </bk-select>
          </bk-form-item>

          <bk-form-item label="索引集">
            <bk-input
              :value="indexSetName"
              readonly
              show-overflow-tooltips
            ></bk-input>
          </bk-form-item>

          <bk-form-item label="查询语句">
            <bk-input
              :value="props.sql"
              type="textarea"
              readonly
              show-overflow-tooltips
            ></bk-input>
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
  @import './bookmark-pop.scss';
</style>
