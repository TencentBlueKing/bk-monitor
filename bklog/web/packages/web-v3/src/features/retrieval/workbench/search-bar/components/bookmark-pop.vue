<script setup>import { ServicesInstance } from '@/platform/services';

  import { computed, ref, nextTick } from 'vue';
  import { Popup, Form, FormItem, Input, Textarea, Select, Option, Button } from 'tdesign-vue-next';
  import 'tdesign-vue-next/es/style/index.css';

  import useLocale from '@/shared/composables/use-locale';
  import useStore from '@/shared/composables/use-store';
  import { ConditionOperator } from '@/app/state/condition-operator';

  

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
      type: [Boolean, String],
    },
    matchSQLStr: {
      default: false,
      type: Boolean,
    },
    commonFilterAddition: {
      default: () => [],
      type: Array,
    },
  });
  const emit = defineEmits(['refresh', 'save-current-active-favorite', 'instanceShow', "saveCurrentActiveFavorite"]);
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
    const indexSet = indexSetList.find(item => String(item.index_set_id) === String(indexSetId));
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
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
      verifyData.value.groupName.trim(),
    );
  };

  const checkExistName = () => {
    return !collectGroupList.value.some(item => item.name === verifyData.value.groupName);
  };
  const checkSpecification = () => {
    return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
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
    checkInputFormRef.value.validate().then(async result => {
      if (result !== true) return;
      const data = {
        name: verifyData.value.groupName,
        space_uid: spaceUid.value,
        source_type: store.getters.isSceneMode ? 'scene' : 'index_set',
      };
      if (window.__IS_MONITOR_APM__) {
        Object.assign(data, {
          scope: {
            app_name: window.MONITOR_APM_APP_NAME,
            service_name: window.MONITOR_APM_SERVICE_NAME,
          },
        });
      }
      try {
        const res = await ServicesInstance.favorite.createGroup({
          data,
        });
        if (res.result) {
          // 获取最新组列表
          await store.dispatch('requestFavoriteList');
          favoriteData.value.group_id = res.data.id;
          window.mainComponent.messageSuccess($t('操作成功'));
          groupPopupVisible.value = false;
        }
      } catch {
        // 分组创建失败时保留当前状态，错误由请求层统一处理
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

  const formatValueStr = value => {
    if (Array.isArray(value)) {
      return `[${value.map(v => `'${v}'`).join(',')}]`;
    }
    return `[${value !== null && value !== undefined ? `'${value}'` : ''}]`;
  };

  const formatConditionStr = ({ field, operator, value }) => {
    if (field === '_ip-select_') {
      const target = value?.[0] ?? {};
      return Object.keys(target)
        .reduce((output, key) => {
          return [...output, `${key}:[${(target[key] ?? []).map(c => c.ip ?? c.objectId ?? c.id).join(' ')}]`];
        }, [])
        .join(' AND ');
    }
    return `${field} ${operator} ${formatValueStr(value)}`;
  };

  const allConditions = computed(() => {
    const conditions = formatAddition.value.map(formatConditionStr);
    if (props.commonFilterAddition?.length) {
      props.commonFilterAddition.forEach(item => {
        conditions.push(formatConditionStr(item));
      });
    }
    return conditions;
  });

  const additionString = computed(() => {
    return `* AND (${allConditions.value.join(' AND ')})`;
  });

  const commonFilterAdditionString = computed(() => {
    if (!props.commonFilterAddition?.length) return '';
    return `AND (${props.commonFilterAddition
      .map(({ field, operator, value }) => `${field} ${operator} ${formatValueStr(value)}`)
      .join(' AND ')})`;
  });

  const sceneFilterString = computed(() => {
    if (!store.getters.isSceneMode) return '';

    const { table_id_conditions: tableIdConditions, scene_filter_values: sceneFilterValues } =
      store.getters.retrieveParams;

    const staticParts = (tableIdConditions?.[0] ?? [])
      .filter(item => item.field_name !== 'scene')
      .map(item => `${item.field_name} ${item.op} ${item.value.join(',')}`);

    const freeInputParts = (sceneFilterValues ?? []).map(
      item => `(${item.field} ${item.operator} [${item.value.join(',')}])`,
    );

    const segments = [];
    if (staticParts.length > 0) {
      segments.push(`((${staticParts.join(' AND ')}))`);
    }
    if (freeInputParts.length > 0) {
      segments.push(freeInputParts.join(' AND '));
    }

    return segments.length > 0 ? segments.join(' AND ') : '';
  });

  const sqlString = computed(() => {
    const scenePrefix = sceneFilterString.value;

    if ('sqlChart' === props.searchMode) {
      return props.extendParams.chart_params.sql;
    }

    if (['sql'].includes(props.searchMode)) {
      if (['sql'].includes(props.searchMode)) {
        const sql = commonFilterAdditionString.value ? `${props.sql} ${commonFilterAdditionString.value}` : props.sql;

        return scenePrefix ? `${scenePrefix} AND ${sql}` : sql;
      }
    }

    return scenePrefix ? `${scenePrefix} AND ${additionString.value}` : additionString.value;
  });

  // 新建提交逻辑
  const handleCreateRequest = async () => {
    const { name, group_id: groupId, display_fields, id, is_enable_display_fields } = favoriteData.value;

    const searchParams = ['sql', 'sqlChart'].includes(props.searchMode)
      ? {
          keyword: sqlString.value,
          addition: [],
          ...(props.extendParams ?? {}),
        }
      : {
          addition: [...formatAddition.value.filter(v => v.field !== '_ip-select_'), ...props.commonFilterAddition],
          keyword: '*',
        };

    const data = {
      name,
      group_id: groupId,
      display_fields,
      visible_type: groupId === privateGroupID.value ? 'private' : 'public',
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
      const { table_id_conditions, scene_filter_values } = store.getters.retrieveParams;
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

    if (window.__IS_MONITOR_APM__) {
      Object.assign(data, {
        scope: {
          app_name: window.MONITOR_APM_APP_NAME,
          service_name: window.MONITOR_APM_SERVICE_NAME,
        },
      });
    }

    try {
      const res = await ServicesInstance.favorite.createFavorite({
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
    } catch {
      // 收藏保存失败时保留当前输入，错误由请求层统一处理
    }
  };
  const saveCurrentFavorite = () => {
    emit('save-current-active-favorite');
  };
  // 提交表单校验
  const handleSubmitFormData = () => {
    popoverFormRef.value.validate().then(result => {
      if (result !== true) return;
      if (!unknownGroupID.value) return;
      // 未选择组则新增到未分组中
      if (!favoriteData.value.group_id) favoriteData.value.group_id = unknownGroupID.value;
      handleCreateRequest();
    });
  };

  // 取消提交逻辑
  const handleCancelRequest = () => {
    initialization();
    popoverShow.value = false;
  };
  const initialization = () => {
    popoverShow.value = false;
    favoriteData.value.name = '';
    favoriteData.value.group_id = undefined;
    verifyData.value.groupName = '';
    emit('instanceShow', false);
    nextTick(() => {
      popoverFormRef.value?.clearValidate();
      checkInputFormRef.value?.clearValidate();
    });
  };
  // popover组件Ref
  // 弹窗显示字段控制
  const popoverShow = ref(false);
  // 弹窗按钮打开逻辑
  const handleCollection = () => {
    popoverShow.value ? hidePopover() : showPopover();
  };
  // 历史记录弹窗按钮打开逻辑
  const handleHistoryCollection = () => {
    emit('instanceShow', true);
    popoverShow.value ? hidePopover() : showPopover();
  };
  const showPopover = () => {
    popoverShow.value = true;
    // 打开弹窗时，若未选择分组，则默认选中个人分组
    if (!favoriteData.value.group_id && privateGroupID.value) {
      favoriteData.value.group_id = privateGroupID.value;
    }
    handlePopoverShow();
  };
  const hidePopover = () => {
    handlePopoverHide();
  };
  const favoriteNameInputRef = ref(null);
  const favoriteGroupSelectRef = ref(null);
  const groupPopupVisible = ref(false);
  const handlePopoverShow = () => {
    // 界面初始化隐藏弹窗样式
    nextTick(() => {
      favoriteNameInputRef.value?.focus();
      if (!popoverShow.value) {
        popoverShow.value = false;
      }
    });
  };
  const handlePopoverHide = () => {
    initialization();
  };
  const handlePopupVisibleChange = (visible, context) => {
    // V2 uses a manual trigger: explicit buttons open it, outside clicks close it.
    if (!visible && context.trigger === 'document') handlePopoverHide();
  };
</script>
<template>
  <Popup
    :style="{ lineHeight: 1 }"
    :visible="popoverShow"
    :placement="activeFavorite === 'history' ? 'right' : 'bottom-right'"
    :show-arrow="false"
    :destroy-on-close="false"
    trigger="click"
    overlay-class-name="collection-favorite-popover"
    :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [22, 10] } }] }"
    @visible-change="handlePopupVisibleChange"
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
      v-bk-tooltips="$t('收藏当前查询')"
      :style="{
        color: popoverShow ? '#3a84ff' : '',
      }"
      class="bklog-icon bklog-star-line"
      @click="handleCollection"
      ><slot></slot
    ></span>
    <Popup
      v-else
      placement="bottom"
      trigger="hover"
      overlay-class-name="bookmark-save-menu"
    >
      <template #default>
        <div
          v-bk-tooltips="$t('收藏')"
          style="font-size: 18px"
          class="icon bklog-icon bklog-save"
        ></div>
      </template>
      <template #content>
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
    </Popup>
    <template #content>
      <div>
        <div class="popover-title-content">
          <p class="dialog-title">{{ $t('新建收藏') }}</p>
        </div>
        <Form
          ref="popoverFormRef"
          :label-width="200"
          :data="favoriteData"
          :rules="rules"
          label-align="top"
        >
          <FormItem
            :label="$t('收藏名称')"
            name="name"
            required
          >
            <Input
              ref="favoriteNameInputRef"
              v-model="favoriteData.name"
            ></Input>
          </FormItem>
          <FormItem
            :label="$t('所属分组')"
            name="project"
          >
            <Select
              ref="favoriteGroupSelectRef"
              v-model="favoriteData.group_id"
              v-model:popup-visible="groupPopupVisible"
              :placeholder="$t('未编组')"
              :popup-props="{ attach: el => el.parentElement, overlayClassName: 'add-popover-new-page-container' }"
              :input-props="{ placeholder: $t('请输入关键字') }"
              filterable
              @change="handleSelectGroup"
            >
              <Option
                v-for="item in collectGroupList"
                :value="item.group_id"
                :key="item.group_id"
                :label="item.group_type === 'private' ? `${item.group_name} (${$t('仅个人可见')})` : item.group_name"
              >
                <span>{{ item.group_name }}</span>
                <span
                  v-if="item.group_type === 'private'"
                  class="private-content"
                >
                  ({{ $t('仅个人可见)') }})
                </span>
              </Option>

              <template #panelBottomContent>
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
                    <Form
                      ref="checkInputFormRef"
                      style="width: 100%"
                      :label-width="0"
                      :data="verifyData"
                      :rules="groupNameRules"
                    >
                      <FormItem name="groupName">
                        <Input
                          v-model="verifyData.groupName"
                          :placeholder="$t('{n}, （长度30个字符）', { n: $t('请输入组名') })"
                        ></Input>
                      </FormItem>
                    </Form>
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
            </Select>
          </FormItem>

          <FormItem :label="store.getters.isSceneMode ? $t('场景') : $t('索引集')">
            <Input
              :value="indexSetName"
              readonly
            ></Input>
          </FormItem>

          <FormItem :label="$t('查询语句')">
            <Textarea
              :value="sqlString"
              readonly
            ></Textarea>
          </FormItem>
        </Form>
      </div>
      <div class="popover-footer">
        <div class="footer-button">
          <Button
            size="small"
            theme="primary"
            @click.stop.prevent="handleSubmitFormData"
          >
            {{ $t('确定') }}
          </Button>
          <Button
            size="small"
            theme="default"
            @click.stop.prevent="handleCancelRequest"
          >
            {{ $t('取消') }}
          </Button>
        </div>
      </div>
    </template>
  </Popup>
</template>
<style lang="scss">
  @import './bookmark-pop.scss';
</style>
