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
  <div class="welcome-page-container">
    <h1 class="title">
      {{ $t('无业务或没有权限') }}
    </h1>
    <div class="card-container">
      <div
        v-if="newBusiness"
        class="card"
      >
        <img
          class="card-img"
          src="../../static/images/svg/new-business.svg"
          alt=""
        />
        <p class="card-title">
          {{ $t('新业务接入') }}
        </p>
        <p class="card-detail">
          {{ $t('新业务接入详情') }}
        </p>
        <bk-button
          class="common-btn"
          hover-theme="primary"
          @click="handleNewBusiness"
          >{{ $t('接入业务') }}<i class="icon-monitor icon-mc-wailian"
        /></bk-button>
      </div>
      <div
        v-if="getAccess"
        class="card"
      >
        <img
          class="card-img"
          src="../../static/images/svg/get-access.svg"
          alt=""
        />
        <p class="card-title">
          {{ $t('获取权限') }}
        </p>
        <!-- 权限中心带业务ID -->
        <template v-if="getAccess.url && getAccess.businessName">
          <p class="card-detail">
            {{ $t('您没有业务{name}的权限', { name: getAccess.businessName }) + $tc('先申请吧') }}
          </p>
          <bk-button
            class="common-btn"
            theme="primary"
            @click="handleGetAccess"
            >{{ $t('申请权限') }}</bk-button
          >
        </template>
        <!-- 权限中心不带业务ID -->
        <template v-else-if="getAccess.url && !getAccess.businessName">
          <p class="card-detail">
            {{ $t('您没有业务权限，请先申请！') }}
          </p>
          <bk-button
            class="common-btn"
            hover-theme="primary"
            @click="handleGetAccess"
            >{{ $t('申请权限') }}</bk-button
          >
        </template>
        <!-- 未接入权限中心带业务ID -->
        <p
          v-else-if="getAccess.businessName"
          class="card-detail"
        >
          {{ $t('您没有业务{0}的权限,请联系运维!', [getAccess.businessName]) }}
        </p>
        <!-- 未接入权限中心不带业务ID -->
        <p
          v-else
          class="card-detail"
        >
          {{ $t('您没有业务权限，请先联系对应的业务运维同学进行添加!') }}
        </p>
      </div>
      <div
        v-if="hasDemoBiz"
        class="card"
      >
        <img
          class="card-img"
          src="../../static/images/svg/demo-business.svg"
          alt=""
        />
        <p class="card-title">
          {{ $t('业务DEMO') }}
        </p>
        <p class="card-detail">
          {{ $t('您当前想快速体验下平台的功能') }}
        </p>
        <bk-button
          class="common-btn"
          hover-theme="primary"
          @click="handleDemoBusiness"
          >{{ $t('我要体验') }}</bk-button
        >
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Vue } from 'vue-property-decorator';

import { fetchBusinessInfo } from 'monitor-api/modules/commons';
import { getUrlParam } from 'monitor-common/utils';
interface IGetAccess {
  businessName: string; // 业务ID对应的业务名（URL带ID时找到对应业务）
  operator: string[]; // 业务ID对应的运维人员ID（没有接入权限中心时URL带ID找到运维人员）
  url: string; // 权限申请链接（接入权限中心时必填）
}
// 20231205 代码还原，先保留原有部分
// import { showAccessRequest } from '../../components/access-request-dialog';
interface INewBusiness {
  url: string;
}
@Component({ name: 'NoBusiness' })
export default class NoBusiness extends Vue {
  newBusiness: INewBusiness = { url: '' }; // 新业务接入链接
  getAccess: IGetAccess = { url: '', businessName: '', operator: [] };
  demoBusiness: INewBusiness = { url: '' }; // 业务DEMO链接

  async created() {
    const data = await fetchBusinessInfo({ space_uid: getUrlParam('space_uid') || undefined }).catch(() => false);
    this.newBusiness.url = data.new_biz_apply;
    this.getAccess = {
      url: data.get_access_url || '',
      operator: data.operator || [],
      businessName: data.bk_biz_name || '',
    };
  }
  get hasDemoBiz() {
    return this.$store.getters.bizList.some(item => item.is_demo);
  }
  get handleOperator() {
    let str = '';
    const operatorList = this.getAccess.operator;
    if (operatorList.length) {
      str = `(${operatorList[0]})`;
      if (operatorList[0] === 'admin') {
        str = `(${operatorList[1]})`;
      }
    }
    return str;
  }
  handleNewBusiness() {
    window.open(this.newBusiness.url);
  }
  handleDemoBusiness() {
    const demo = this.$store.getters.bizList.find(item => item.is_demo);
    if (demo?.id) {
      window.open(`${location.origin}${location.pathname}?bizId=${demo.id}#/`);
    }
  }
  handleGetAccess() {
    window.open(this.getAccess.url);
    // 20231205 代码还原，先保留原有部分
    // showAccessRequest(this.getAccess.url);
  }
}
</script>

<style lang="scss" scoped>
.welcome-page-container {
  display: flow-root;
  height: 100%;
  background: #f4f7fa;

  .title {
    height: 26px;
    margin: 70px 0 35px;
    font-size: 20px;
    font-weight: normal;
    line-height: 26px;
    color: #313238;
    text-align: center;
  }

  .card-container {
    display: flex;
    justify-content: center;

    .card {
      display: flex;
      flex-flow: column;
      align-items: center;
      width: 260px;
      height: 400px;
      background: #fff;
      border-radius: 2px;
      transition: box-shadow 0.3s;

      &:not(:last-child) {
        margin-right: 40px;
      }

      &:hover {
        box-shadow: 0 3px 6px 0 rgba(0, 0, 0, 0.1);
        transition: box-shadow 0.3s;
      }

      .card-img {
        width: 220px;
        height: 160px;
        margin: 28px 0 20px;
      }

      .card-title {
        font-size: 16px;
        font-weight: 500;
        line-height: 22px;
        color: #313238;
      }

      .card-detail {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 200px;
        height: 60px;
        margin: 11px 0 21px;
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
        text-align: center;
      }

      .common-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 200px;

        :deep(span) {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .icon-monitor {
          margin-left: 4px;
          font-size: 18px;
        }
      }
    }
  }
}
</style>
