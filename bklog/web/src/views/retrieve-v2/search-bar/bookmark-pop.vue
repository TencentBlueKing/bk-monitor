<script setup>
import { computed, ref } from 'vue';

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

// 用于展示索引集
// 这里返回数组，展示 index_set_name 字段
const indexSetItemList = computed(() => store.state.indexItem.items);
const collectGroupList = computed(() => [{ id: 1, name: '2' }]);
const groupList = ref([]); // 组列表
const publicGroupList = ref([]); // 可见状态为公共的时候显示的收藏组
const privateGroupList = ref([]); // 个人收藏 group_name替换为本人

let unknownGroupID = ref(0);
let privateGroupID = ref(0);
const spaceUid = computed(() => store.state.spaceUid);
const isShowAddGroup = ref(false); // 是否新增组
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

/** 获取组列表 */
// TODO 赋值逻辑待更改
// async function requestGroupList(isAddGroup = false, groupName?) {
//   try {
//     const res = await $http.request('favorite/getGroupList', {
//       query: {
//         space_uid: spaceUid.value,
//       },
//     });

//     groupList.value = res.data.map(item => ({
//       ...item,
//       name: this.groupNameMap[item.group_type] ?? item.name,
//     }));
//     publicGroupList.value = groupList.value.slice(1, groupList.value.length);
//     privateGroupList.value = [groupList.value[0]];
//     unknownGroupID.value = groupList.value[groupList.value.length - 1]?.id;
//     privateGroupID.value = groupList.value[0]?.id;
//   } catch (error) {
//   } finally {
//     if (isAddGroup) {
//       favoriteData.group_id = groupList.value.find(item => item.name === groupName)?.id;
//     }
//   }
// }

const handleCreateGroup = () => {
  checkInputFormRef.validate().then(async () => {
    const data = { name: verifyData.value.groupName, space_uid: spaceUid.value };

    // TODO 赋值逻辑待修改
    // try {
    //   const res = await $http.request('favorite/createGroup', {
    //     data,
    //   });
    //   if (res.result) {
    //     this.$bkMessage({
    //       message: this.$t('操作成功'),
    //       theme: 'success',
    //     });
    //     // requestGroupList(true, verifyData.value.groupName.trim());
    //   }
    // } catch (error) {
    // } finally {
    //   isShowAddGroup.value = true;
    //   verifyData.value.groupName = '';
    // }
  });
};

// 存储表单数据

const formData = ref({
  name: '',
  group_id: '',
  desc: '',
});
const isDisableSelect = ref(false);
// 新建提交逻辑
const handleCreateRequest = () => {};

// 弹窗显示字段控制
const dilagShow = ref(false);
// 弹窗按钮打开逻辑
const handleCollection = () => {
  dilagShow.value = true;
};
</script>
<template>
  <div>
    <span
      :style="{
        color: dilagShow ? '#3a84ff' : '',
      }"
      class="bklog-icon bklog-star-line"
      @click="handleCollection"
    ></span>
    <bk-dialog
      width="400"
      ext-cls="collection-dialog"
      v-model="dilagShow"
      theme="primary"
    >
      <p class="dialog-title">{{ $t('新建收藏') }}</p>
      <bk-form
        ref="validateForm1"
        :label-width="200"
        :model="formData"
        form-type="vertical"
      >
        <bk-form-item
          :property="'name'"
          :required="true"
          label="收藏名称"
        >
          <bk-input
            v-model="formData.name"
            placeholder="请输入收藏名称"
          ></bk-input>
        </bk-form-item>
        <bk-form-item
          :property="'project'"
          :required="true"
          label="所属分组"
        >
          <bk-select
            v-model="formData.group_id"
            :disabled="isDisableSelect"
            ext-popover-cls="add-new-page-container"
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
                  style="padding: 6px 0"
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
    </bk-dialog>
  </div>
</template>
<style lang="scss" scoped>
//先借用 add-collect-dialog样式，后续更改
@import '@/scss/mixins/flex.scss';

.collection-dialog {
  .bk-dialog {
    .bk-dialog-content {
      width: 400px;
      height: 429.62px;
      background: #ffffff;
      border: 1px solid #dcdee5;
      box-shadow: 0 2px 6px 0 #0000001a;
    }
  }
}

.add-collect-dialog {
  .bk-form {
    > :first-child {
      margin-top: -10px;
    }

    > :not(:first-child) {
      /* stylelint-disable-next-line declaration-no-important */
      margin-top: 12px !important;
    }
  }

  .edit-information {
    padding: 0 16px;
    font-size: 12px;

    @include flex-justify(start);

    > :first-child {
      display: inline-block;
      min-width: 72px;
      margin-right: 6px;
      color: #979ba5;
    }

    > :last-child {
      flex-direction: column;

      @include flex-justify(center);
    }
  }

  .collect-radio {
    /* stylelint-disable-next-line declaration-no-important */
    margin-top: 0 !important;

    .bk-form-control {
      > :first-child {
        margin-right: 20px;
      }
    }
  }

  .filed-label .bk-label-text {
    width: 100%;
  }

  .bk-form-item {
    padding: 0 16px;

    .bk-label,
    .bk-radio-text,
    .bk-checkbox-text {
      font-size: 12px;
    }
  }

  .form-item-container {
    align-items: center;

    @include flex-justify(space-between);

    .bk-form-item {
      width: 50%;
    }
  }

  .explanation-field {
    padding: 6px 8px;
    font-size: 12px;
    line-height: 20px;
    background: #f5f7fa;
  }

  .bk-form-checkbox {
    margin-right: 20px;
  }

  .filed-container {
    display: flex;
    flex-wrap: wrap;
    align-items: center;

    .current-filed {
      margin-left: 24px;
      font-size: 12px;
      color: #979ba5;
    }
  }

  .add-new-page-container {
    .add-new-page-input {
      display: flex;
      align-items: center;
    }

    .operate-button {
      justify-content: space-between;
      margin-left: 6px;
      font-size: 16px;
      color: #979ba5;

      span {
        cursor: pointer;
      }

      > :first-child {
        margin-right: 12px;
        color: #33d05c;
      }

      > :last-child {
        color: #979ba5;
      }
    }
  }

  .fl-jcsb {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
}
</style>
