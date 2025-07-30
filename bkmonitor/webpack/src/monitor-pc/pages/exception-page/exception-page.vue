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
  <div class="exception-page">
    <bk-exception
      class="exception-page-img"
      :type="type"
    >
      <template v-if="type + '' === '403'">
        <div class="exception-title">
          {{ $t('您没有该资源的权限，请先申请或联系管理员!') }}
          <bk-button
            class="exception-btn"
            theme="primary"
            @click="handleGotoApply"
          >
            {{ $t('去申请') }}
          </bk-button>
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
              <template v-if="applyActions && applyActions.length > 0">
                <tr
                  v-for="(action, index) in applyActions"
                  :key="index"
                >
                  <!-- <td width="20%">{{authorityDetail.systemName}}</td> -->
                  <td width="30%">
                    {{ action.name }}
                  </td>
                  <td width="50%">
                    <p
                      v-for="(reItem, reIndex) in getResource(action.related_resource_types)"
                      :key="reIndex"
                      class="resource-type-item"
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
                >
                  {{ $t('无数据') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </bk-exception>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import { getAuthorityDetail } from 'monitor-api/modules/iam';
// 20231205 代码还原，先保留原有部分
// import { showAccessRequest } from '../../components/access-request-dialog';
Component.registerHooks(['beforeRouteEnter']);
@Component({
  name: 'error-exception',
})
export default class ExceptionPage extends Vue {
  @Prop({ default: '404' }) type: number | string;
  @Prop({ default: '' }) queryUid: string;
  applyUrl = '';
  applyActions = [];
  isQuery = false;
  @Watch('queryUid')
  async onQueryUidChange() {
    if (this.isQuery) return;
    this.applyActions = [];
    const { actionId } = this.$route.query;
    if (actionId) {
      this.isQuery = true;
      const data = await getAuthorityDetail(
        {
          action_ids: Array.isArray(actionId) ? actionId : [actionId],
          space_uid: window.space_uid || undefined,
          bk_biz_id: !window.space_uid ? window.bk_biz_id || window.cc_biz_id : undefined,
        },
        { needMessage: false }
      ).catch(e => {
        console.error(e);
        return false;
      });
      if (data) {
        this.applyActions = data.authority_list?.actions;
        this.applyUrl = data.apply_url;
      }
      this.isQuery = false;
    }
  }
  mounted() {
    this.onQueryUidChange();
  }

  handleGotoApply() {
    // 20231205 代码还原，先保留原有部分
    // showAccessRequest(this.applyUrl);
    if (!this.applyUrl) return;
    try {
      if (self === top) {
        window.open(this.applyUrl, '_blank');
      } else {
        top.BLUEKING.api.open_app_by_other('bk_iam', this.applyUrl);
      }
    } catch {
      window.open(this.applyUrl, '_blank');
    }
  }
  getResource(resources) {
    if (resources.length === 0) {
      return ['--'];
    }
    const data = [];
    for (const resource of resources) {
      if (resource.instances.length > 0) {
        const instances = resource.instances
          .map(instanceItem => instanceItem.map(item => `[${item.id}]${item.name}`).join('，'))
          .join('，');
        const resourceItemData = `${resource.type_name}：${instances}`;
        data.push(resourceItemData);
      }
    }
    return data;
  }
}
</script>
<style lang="scss" scoped>
@import '../../theme/mixin.scss';

.exception-page {
  position: relative;
  display: flex;
  justify-content: center;
  height: 100%;

  @include permission-fix;

  .exception-title {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 15px;
    font-size: 14px;
  }

  &-img {
    position: absolute;
    top: 40%;
    max-width: 800px;
    transform: translateY(-50%);

    .exception-btn {
      margin-left: 10px;
    }
  }
}
</style>
