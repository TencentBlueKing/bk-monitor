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
  <bk-dialog
    width="768"
    ext-cls="permission-dialog"
    :z-index="2990"
    :mask-close="false"
    :header-position="'left'"
    :title="''"
    @value-change="handleValueChange"
    :value="isModalShow"
    @cancel="onCloseDialog"
  >
    <div
      class="permission-modal"
      v-bkloading="{ isLoading: loading }"
    >
      <div class="permission-header">
        <span class="title-icon">
          <img
            :src="lock"
            alt="permission-lock"
            class="lock-img"
          >
        </span>
        <h3>{{ $t('该操作需要以下权限') }}</h3>
      </div>
      <table class="permission-table table-header">
        <thead>
          <tr>
            <!-- <th width="20%">{{$t('系统')}}</th> -->
            <th width="30%">
              {{ $t('需要申请的权限') }}
            </th>
            <th width="50%">
              {{ $t('关联的资源实例') }}
            </th>
          </tr>
        </thead>
      </table>
      <div class="table-content">
        <table class="permission-table">
          <tbody>
            <template v-if="authorityDetail.actions && authorityDetail.actions.length > 0">
              <tr
                v-for="(action, index) in authorityDetail.actions"
                :key="index"
              >
                <!-- <td width="20%">{{authorityDetail.systemName}}</td> -->
                <td width="30%">
                  {{ action.name }}
                </td>
                <td width="50%">
                  <p
                    class="resource-type-item"
                    v-for="(reItem, reIndex) in getResource(action.relatedResourceTypes)"
                    :key="reIndex"
                  >
                    {{ reItem }}
                  </p>
                </td>
              </tr>
            </template>
            <tr v-else>
              <td
                class="no-data"
                colspan="3"
              >{{ $t('无数据') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div
      class="permission-footer"
      slot="footer"
    >
      <div class="button-group">
        <bk-button
          theme="primary"
          @click="goToApply"
        >{{ $t('去申请') }}</bk-button>
        <bk-button
          theme="default"
          @click="onCloseDialog"
        >{{ $t('取消') }}</bk-button>
      </div>
    </div>
  </bk-dialog>
</template>
<script lang="ts">
import { Component, Vue, Watch } from 'vue-property-decorator';
// 20231205 代码还原，先保留原有部分
// import { showAccessRequest } from '../../monitor-pc/components/access-request-dialog';
import authorityStore from '@store/modules/authority';

import lockImg from '../../monitor-pc/static/images/svg/lock-radius.svg';

@Component
export default class AuthorityModal extends Vue {
  isModalShow = false;
  permissionData: any = {};
  lock = lockImg;

  get loading() {
    return this.$store.getters['authority/loading'];
  }
  get show() {
    return this.$store.getters['authority/showDialog'];
  }
  get applyUrl() {
    return this.$store.getters['authority/applyUrl'];
  }
  get authorityDetail() {
    return this.$store.getters['authority/authorityDetail'];
  }
  @Watch('show')
  onIsModalShowChange(val) {
    this.isModalShow = val;
  }
  handleValueChange() {
    authorityStore.setShowAuthortyDialog(this.isModalShow);
  }

  getResource(resoures) {
    if (resoures.length === 0) {
      return ['--'];
    }

    const data = [];
    resoures.forEach((resource) => {
      if (resource.instances.length > 0) {
        const instances = resource.instances
          .map(instanceItem => instanceItem.map(item => item.name).join('，'))
          .join('，');
        const resourceItemData = `${resource.typeName}：${instances}`;
        data.push(resourceItemData);
      }
    });
    return data;
  }
  goToApply() {
    // 20231205 代码还原，先保留原有部分
    // showAccessRequest(this.applyUrl);
    try {
      if (self === top) {
        window.open(this.applyUrl, '__blank');
      } else {
        top.BLUEKING.api.open_app_by_other('bk_iam', this.applyUrl);
      }
    } catch (_) {
      // 防止跨域问题
      window.open(this.applyUrl, '__blank');
    }
  }
  onCloseDialog() {
    this.isModalShow = false;
  }
}
</script>
<style lang="scss">
.permission-dialog {
  /* stylelint-disable-next-line declaration-no-important */
  z-index: 3000 !important;
}
</style>
<style lang="scss" scoped>
@import '../../monitor-pc/theme/mixin.scss';

.permission-modal {
  @include permission-fix;

  .permission-header {
    text-align: center;

    .title-icon {
      display: inline-block;
    }

    .lock-img {
      width: 120px;
    }

    h3 {
      margin: 6px 0 24px;
      font-size: 20px;
      font-weight: normal;
      line-height: 1;
      color: #63656e;
    }
  }
}

.button-group {
  .bk-button {
    margin-left: 7px;
  }
}
</style>
