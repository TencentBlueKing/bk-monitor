<!--
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
-->

<template>
  <div class="no-authority">
    <bk-dialog
      v-model="showApplyDialog"
      :close-icon="false"
      :mask-close="false"
      :ok-text="$t('申请')"
      :width="740"
      @cancel="closeAuth"
      @confirm="confirmSourceApply"
    >
      <div class="apply-authority-dialog-container">
        <img
          class="lock-icon"
          alt="lock"
          src="../../images/lock-radius.svg"
        />
        <div class="title">{{ $t('该操作需要以下权限') }}</div>
        <bk-table
          v-if="tableData.length"
          class="king-table"
          :data="tableData"
          :outer-border="false"
        >
          <bk-table-column :label="$t('系统')">
            <template #default="{ row }">
              <div>{{ row.system }}</div>
            </template>
          </bk-table-column>
          <bk-table-column :label="$t('关联的资源实例')">
            <template #default="{ row }">
              <div class="related-resources-container">
                <span
                  v-for="(source, index) in row.sources"
                  :key="index"
                >
                  {{ source }}
                </span>
                <span v-if="!row.sources.length">--</span>
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('需要申请的权限')"
            prop="permission"
          ></bk-table-column>
        </bk-table>
      </div>
    </bk-dialog>

    <bk-dialog
      v-model="showConfirmDialog"
      :ok-text="$t('刷新')"
      :title="$t('权限申请单已提交？')"
      @cancel="closeAuth"
      @confirm="confirmHasApply"
    >
      {{ $t('请在权限中心填写权限申请单') }}
    </bk-dialog>
  </div>
</template>

<script>
  export default {
    data() {
      return {
        showApplyDialog: false,
        showConfirmDialog: false,
        tableData: [],
      };
    },
    computed: {
      authDialogData() {
        return this.$store.state.authDialogData;
      },
    },
    watch: {
      authDialogData: {
        handler(val) {
          if (val) {
            this.updateData(val);
          } else {
            this.tableData.splice(0);
            this.showApplyDialog = false;
          }
          this.showConfirmDialog = false;
        },
        immediate: true,
      },
    },
    methods: {
      updateData(authData) {
        try {
          const tableData = [];
          authData.apply_data.actions.forEach(action => {
            const item = {
              system: authData.apply_data.system_name, // 系统
              sources: [], // 资源
              permission: action.name, // 需要申请的权限
            };
            action.related_resource_types.forEach(resource => {
              resource.instances.flat().forEach(instance => {
                item.sources.push(`${instance.type_name}：${instance.name}`);
              });
            });
            tableData.push(item);
          });

          this.tableData = tableData;
          this.showApplyDialog = true;
        } catch (err) {
          console.log('无权限的数据格式不对', err);
        }
      },
      confirmSourceApply() {
        this.showApplyDialog = false;

        setTimeout(() => {
          this.showConfirmDialog = true;
          window.open(this.authDialogData.apply_url);
        }, 360);
      },
      confirmHasApply() {
        this.closeAuth();
        location.reload();
      },
      closeAuth() {
        this.$store.commit('updateState', {'authDialogData': null});
      },
    },
  };
</script>

<style lang="scss" scoped>
  .no-authority {
    position: fixed;
    top: 0;
    left: 0;
    width: 0;
    height: 0;
  }

  .apply-authority-dialog-container {
    display: flex;
    flex-flow: column;
    align-items: center;

    .lock-icon {
      margin-bottom: 10px;
    }

    .title {
      margin-bottom: 30px;
      font-size: 20px;
      color: #63656e;
    }

    :deep(.king-table) {
      margin-bottom: 12px;

      .bk-table-body-wrapper {
        height: 128px;
        overflow-y: auto;
      }

      .related-resources-container {
        display: flex;
        flex-flow: column;
      }
    }
  }
</style>
