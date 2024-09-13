<script setup lang="ts">
  import { computed, ref, nextTick } from 'vue';

  import useStore from '@/hooks/use-store';

  import $http from '../../../api';

  const props = defineProps({
    sql: {
      default: '',
      type: String,
      required: true,
    },
  });

  const store = useStore();
  console.log(store, '---');
  // 用于展示索引集
  // 这里返回数组，展示 index_set_name 字段
  const indexSetItemList = computed(() => store.state.indexItem.items);
  // store.state.favoriteList
  const collectGroupList = computed(() => [{ id: 1, name: 2 }]);
  const groupList = ref([]); // 组列表
  const publicGroupList = ref([]); // 可见状态为公共的时候显示的收藏组space_uid
  const privateGroupList = ref([]); // 个人收藏 group_name替换为本人
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
  let unknownGroupID = ref(0);
  let privateGroupID = ref(0);
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
    return !groupList.value.some(item => item.name === verifyData.value.groupName);
  };
  // 组名称新增规则
  const groupNameRules = {
    groupName: [
      {
        validator: checkName,
        message: window.mainComponent.$t('{n}不规范, 包含特殊符号', { n: window.mainComponent.$t('组名') }),
        trigger: 'blur',
      },
      {
        validator: checkExistName,
        message: window.mainComponent.$t('组名重复'),
        trigger: 'blur',
      },
      {
        required: true,
        message: window.mainComponent.$t('必填项'),
        trigger: 'blur',
      },
      {
        max: 30,
        message: window.mainComponent.$t('不能多于{n}个字符', { n: 30 }),
        trigger: 'blur',
      },
    ],
  };
  const groupNameMap = {
    unknown: window.mainComponent.$t('未分组'),
    private: window.mainComponent.$t('个人收藏'),
  };
  // 新增组表单ref
  const checkInputFormRef = ref();
  /** 获取组列表 */
  // TODO 赋值逻辑待更改
  async function requestGroupList(isAddGroup = false, groupName?) {
    try {
      const res = await $http.request('favorite/getGroupList', {
        query: {
          space_uid: spaceUid.value,
        },
      });
      console.log(res, '----');
      groupList.value = res.data.map(item => ({
        ...item,
        name: groupNameMap[item.group_type] ?? item.name,
      }));
      publicGroupList.value = groupList.value.slice(1, groupList.value.length);
      privateGroupList.value = [this.groupList[0]];
      unknownGroupID.value = groupList[this.groupList.length - 1]?.id;
      privateGroupID.value = groupList.value[0]?.id;
    } catch (error) {
    } finally {
      if (isAddGroup) {
        favoriteData.value.group_id = groupList.value.find(item => item.name === groupName)?.id;
      }
    }
  }
  // 确认新增组事件
  const handleCreateGroup = () => {
    checkInputFormRef.value.validate().then(async () => {
      const data = { name: verifyData.value.groupName, space_uid: spaceUid.value };
      try {
        const res = await $http.request('favorite/createGroup', {
          data,
        });
        if (res.result) {
          requestGroupList(true, verifyData.value.groupName.trim());
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
    const visibleType = nVal === privateGroupID.value ? 'private' : 'public';
    isDisableSelect.value = nVal === privateGroupID.value;
    Object.assign(favoriteData.value, { visibleType });
  };
  // 存储表单数据

  const isDisableSelect = ref(false);
  // 新建提交逻辑
  const handleCreateRequest = () => {};
  // 取消提交逻辑
  const handleCancleRequest = () => {
    popoverShow.value = false;
    popoverContentRef.value.hideHandler();
  };
  // popover组件Ref
  const popoverContentRef = ref();
  // 弹窗显示字段控制
  const popoverShow = ref(false);
  // 弹窗按钮打开逻辑
  const handleCollection = () => {
    if (popoverShow.value) {
      popoverShow.value = false;
      popoverContentRef.value.hideHandler();
    } else {
      popoverShow.value = true;
      popoverContentRef.value.showHandler();
    }
  };
  const popoverHide = () => {};
  const handlePopoverShow = () => {
    // 界面初始化隐藏弹窗样式
    nextTick(() => {
      if (!popoverShow.value) {
        popoverContentRef.value.hideHandler();
      }
    });
  };
</script>
<template>
  <bk-popover
    ref="popoverContentRef"
    width="400"
    ext-cls="collection-popover"
    :always="true"
    :on-hide="popoverHide"
    :on-show="handlePopoverShow"
    placement="bottom-end"
    theme="light"
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
          ref="validateForm1"
          :label-width="200"
          :model="favoriteData"
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
              :disabled="isDisableSelect"
              ext-popover-cls="add-popover-new-page-container"
              placeholder="未编组"
              searchable
              @change="handleSelectGroup"
            >
              <bk-option
                v-for="item in collectGroupList"
                :id="item.id"
                :key="item.id"
                :name="item.name"
              ></bk-option>

              <template #extension>
                <div>
                  <div
                    v-if="isShowAddGroup"
                    class="select-add-new-group"
                    @click="isShowAddGroup = false"
                  >
                    <div><i class="bk-icon icon-plus-circle"></i> {{ $t('新增') }}</div>
                  </div>
                  <li
                    v-else
                    style=" display: flex; align-items: center;padding: 6px 0"
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
                    <div
                      style="
                        justify-content: space-between;
                        width: 45px;
                        margin-left: 6px;
                        font-size: 16px;
                        color: #979ba5;
                      "
                      class="operate-button"
                    >
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
                  </li>
                </div>
              </template>
            </bk-select>
          </bk-form-item>

          <bk-form-item label="索引集">
            <bk-input
              :value="indexSetItemList.index_set_name"
              readonly
            ></bk-input>
          </bk-form-item>

          <bk-form-item label="查询语句">
            <bk-input
              :value="props.sql"
              type="textarea"
              readonly
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
            @click.stop.prevent="handleCreateRequest"
            >{{ $t('确定') }}</bk-button
          >
          <bk-button
            size="small"
            theme="default"
            @click.stop.prevent="handleCancleRequest"
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

<style lang="scss">
  .collection-popover {
    .tippy-tooltip[data-size='small'] {
      height: 430px;
      padding: 16px 16px;
    }

    .bk-tooltip-content {
      height: 414px;

      .bk-form-content {
        .bk-form-control {
          .bk-input-text {
            .bk-form-input[readonly] {
              border: 0px;
            }
          }

          .bk-textarea-wrapper {
            border: 0px;

            .bk-form-textarea[readonly] {
              border: 0px;
            }
          }
        }
      }
    }

    .popover-footer {
      position: absolute;
      right: -16px;
      bottom: 0;
      width: 400px;
      height: 42px;
      padding: 8px 16px;
      background: #fafbfd;
      box-shadow: 0 -1px 0 0 #dcdee5;

      .footer-button {
        text-align: right;
      }
    }
  }
</style>
