<script setup>
  import { computed, ref, nextTick } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import { buildTableIdConditions } from '@/store/helper';

  import $http from '../../../../api';

  const props = defineProps({
    sql: {
      default: '',
      type: String,
      required: true,
    },
    addition: {
      default: () => [],
      type: Array,
      required: true,
    },
    searchMode: {
      default: '',
      type: String,
      required: true,
    },
    extendParams: {
      type: Object,
    },
    activeFavorite: {
      default: true,
      type: Boolean | String,
    },
    matchSQLStr: {
      default: false,
      type: Boolean,
    },
  });
  const emit = defineEmits(['refresh', 'save-current-active-favorite','instanceShow']);
  const { $t } = useLocale();
  const store = useStore();

  const indexSetItem = computed(() => store.state.indexItem);

  // 用于展示索引集
  // 这里返回数组，展示 index_set_name 字段
  // const indexSetItemList = computed(() => store.state.indexItem.items);
  // const indexSetName = computed(() => {
  //   return indexSetItemList.value?.map(item => item?.index_set_name).join(',');
  // });
  const indexSetName = computed(() => {
    if (store.getters.isSceneMode) {
      const sceneConfigs = store.getters['retrieve/sceneConfigList'] ?? [];
      const sceneActive = store.state.indexItem?.scene_active ?? '';
      const sceneConfig = sceneConfigs.find(s => s.type === sceneActive);
      return sceneConfig?.label ?? sceneActive ?? '';
    }
    const indexSetList = store.state.retrieve.flatIndexSetList || [];
    const indexSetId = store.state.indexId;
    const indexSet = indexSetList.find(item => item.index_set_id == indexSetId);
    return indexSet ? indexSet.index_set_name : ''; // 提供一个默认名称或处理
  });
  const collectGroupList = computed(() => store.state.favoriteList);
  const favStrList = computed(() => store.state.favoriteList.map(item => item.name));
  const unknownGroupID = computed(() => collectGroupList.value[collectGroupList.value.length - 1]?.group_id);
  const privateGroupID = computed(() => collectGroupList.value[0]?.group_id);
  // 表单ref
  const popoverFormRef = ref();
  const favoriteData = ref({
    // 收藏参数
    space_uid: -1,
    index_set_id: -1,
    name: '',
    group_id: privateGroupID.value,
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
          await store.dispatch('requestFavoriteList');
          favoriteData.value.group_id = res.data.id;
          window.mainComponent.messageSuccess($t('操作成功'));
          favoriteGroupSelectRef.value?.close();
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

  const formatAddition = computed(() =>
    props.addition
      .filter(item => !item.disabled)
      .map(item => {
        const instance = new ConditionOperator(item);
        return instance.getRequestParam();
      }),
  );

  const additionString = computed(() => {
    return `* AND (${formatAddition.value
      .map(({ field, operator, value }) => {
        if (field === '_ip-select_') {
          const target = value?.[0] ?? {};
          return Object.keys(target)
            .reduce((output, key) => {
              return [...output, `${key}:[${(target[key] ?? []).map(c => c.ip ?? c.objectId ?? c.id).join(' ')}]`];
            }, [])
            .join(' AND ');
        }
        return `${field} ${operator} [${value?.toString() ?? ''}]`;
      })
      .join(' AND ')})`;
  });

  const sqlString = computed(() => {
    if ('sqlChart' === props.searchMode) {
      return props.extendParams.chart_params.sql;
    }

    if (['sql'].includes(props.searchMode)) {
      return props.sql;
    }

    return additionString.value;
  });

  // 新建提交逻辑
  const handleCreateRequest = async () => {
    const { name, group_id, display_fields, id, is_enable_display_fields } = favoriteData.value;

    const searchParams = ['sql', 'sqlChart'].includes(props.searchMode)
      ? { keyword: props.sql, addition: [], ...(props.extendParams ?? {}) }
      : { addition: formatAddition.value.filter(v => v.field !== '_ip-select_'), keyword: '*' };

    const data = {
      name,
      group_id,
      display_fields,
      visible_type: group_id === privateGroupID.value ? 'private' : 'public',
      is_enable_display_fields,
      search_mode: props.searchMode,
      ip_chooser: formatAddition.value.find(item => item.field === '_ip-select_')?.value?.[0] ?? {},
      index_set_ids: [],
      index_set_names: [],
      space_uid: spaceUid.value,
      pid: store.state.indexItem.pid,
      ...searchParams,
    };

    if (store.getters.isSceneMode) {
      // 场景化收藏
      const { table_id_conditions, scene_filter_values } = buildTableIdConditions(
        store.state,
        store.getters['retrieve/sceneConfigList'],
      );
      Object.assign(data, {
        source_type: 'scene',
        scene_id: store.state.indexItem.scene_active,
        table_id_conditions,
        scene_filter_values,
      });
    } else if (indexSetItem.value.isUnionIndex) {
      Object.assign(data, {
        index_set_ids: indexSetItem.value.ids,
        index_set_type: 'union',
      });
    } else {
      Object.assign(data, {
        index_set_id: store.state.indexId,
        index_set_type: 'single',
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
  const saveCurrentFavorite = () => {
    emit('save-current-active-favorite');
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
    initialization();
    popoverContentRef.value.hideHandler();
  };
  const initialization = () => {
    popoverShow.value = false;
    favoriteData.value.name = '';
    favoriteData.value.group_id = undefined;
    verifyData.value.groupName = '';
    emit('instanceShow',false);
    nextTick(() => {
      popoverContentRef.value?.clearError?.();
    });
  };
  // popover组件Ref
  const popoverContentRef = ref();
  // 弹窗显示字段控制
  const popoverShow = ref(false);
  // 弹窗按钮打开逻辑
  const handleCollection = () => {
    popoverShow.value ? hidePopover() : showPopover();
  };
  // 历史记录弹窗按钮打开逻辑
  const handleHistoryCollection = () => {
    emit('instanceShow',true);
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
  const favoriteNameInputRef = ref(null);
  const favoriteGroupSelectRef = ref(null);
  const handlePopoverShow = () => {
    // 界面初始化隐藏弹窗样式
    nextTick(() => {
      favoriteNameInputRef.value?.focus();
      if (!popoverShow.value) {
        popoverContentRef.value.hideHandler();
      }
    });
  };
  const tippyOptions = {
    theme: 'light',
    placement: props.activeFavorite === 'history'? 'right' : 'bottom-end',
    offset: '22',
    interactive: true,
    trigger: 'manual',
  };
  const handlePopoverHide = () => {
    initialization();
  };
</script>
<template>
  <bk-popover
    ref="popoverContentRef"
    :style="{
      lineHeight: 1,
    }"
    width="400"
    ext-cls="collection-favorite-popover"
    :on-hide="handlePopoverHide"
    :on-show="handlePopoverShow"
    :tippy-options="tippyOptions"
  >
    <span v-if="activeFavorite === 'history'">
      <span
        class="bklog-icon bklog-lc-star-shape"
        @click.stop="handleHistoryCollection"
      >
      </span>
    </span>
    <span
      v-else-if="activeFavorite"
      :style="{
        color: popoverShow ? '#3a84ff' : '',
      }"
      class="bklog-icon bklog-star-line"
      v-bk-tooltips="$t('收藏当前查询')"
      @click="handleCollection"
      ><slot></slot
    ></span>
    <bk-dropdown-menu
      v-else
      :align="'center'"
    >
      <template #dropdown-trigger>
        <div
          style="font-size: 18px"
          class="icon bklog-icon bklog-save"
          v-bk-tooltips="$t('收藏')"
        ></div>
      </template>
      <template #dropdown-content>
        <ul class="bk-dropdown-list">
          <li>
            <a
              v-bk-tooltips="{ disabled: !matchSQLStr, content: $t('当前检索已收藏'), placement: 'left' }"
              :class="matchSQLStr ? 'disabled' : ''"
              href="javascript:;"
              @click.stop="saveCurrentFavorite"
              >{{ $t('覆盖当前收藏') }}</a
            >
          </li>
          <li>
            <a
              href="javascript:;"
              @click.stop="handleCollection"
              >{{ $t('另存为新收藏') }}</a
            >
          </li>
        </ul>
      </template>
    </bk-dropdown-menu>
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
            :label="$t('收藏名称')"
            :property="'name'"
            required
          >
            <bk-input
              ref="favoriteNameInputRef"
              v-model="favoriteData.name"
            ></bk-input>
          </bk-form-item>
          <bk-form-item
            :label="$t('所属分组')"
            :property="'project'"
          >
            <bk-select
              ref="favoriteGroupSelectRef"
              ext-cls="add-popover-new-page-container"
              v-model="favoriteData.group_id"
              :placeholder="$t('未编组')"
              :popover-options="{ appendTo: 'parent' }"
              :search-placeholder="$t('请输入关键字')"
              searchable
              @change="handleSelectGroup"
            >
              <bk-option
                v-for="item in collectGroupList"
                :id="item.group_id"
                :key="item.group_id"
                :name="item.group_type === 'private' ? `${item.group_name} (${$t('仅个人可见')})` : item.group_name"
              >
                <span>{{ item.group_name }}</span>
                <span
                  v-if="item.group_type === 'private'"
                  class="private-content"
                >
                  ({{ $t('仅个人可见)') }})
                </span>
              </bk-option>
              <template #name> 4444 </template>
              <template #extension>
                <div class="favorite-group-extension">
                  <div
                    v-if="isShowAddGroup"
                    class="select-add-new-group"
                    @click="isShowAddGroup = false"
                  >
                    <i class="bk-icon icon-plus-circle" />
                    <span class="add-text">{{ $t('新增分组') }}</span>
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

          <bk-form-item :label="store.getters.isSceneMode ? $t('场景') : $t('索引集')">
            <bk-input
              :value="indexSetName"
              readonly
              show-overflow-tooltips
            ></bk-input>
          </bk-form-item>

          <bk-form-item :label="$t('查询语句')">
            <bk-input
              :value="sqlString"
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
            size="small"
            theme="primary"
            @click.stop.prevent="handleSubmitFormData"
          >
            {{ $t('确定') }}
          </bk-button>
          <bk-button
            size="small"
            theme="default"
            @click.stop.prevent="handleCancelRequest"
          >
            {{ $t('取消') }}
          </bk-button>
        </div>
      </div>
    </template>
  </bk-popover>
</template>
<style lang="scss">
  @import './bookmark-pop.scss';
</style>
