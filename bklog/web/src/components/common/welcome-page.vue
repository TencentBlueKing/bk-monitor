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
    <h1 class="title">{{ $t('未接入业务或无可查看的业务权限') }}</h1>
    <div class="card-container">
      <div
        v-if="data.newBusiness"
        class="card"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
      >
        <img
          class="card-img"
          alt=""
          src="../../images/icons/new-business.svg"
        />
        <p class="card-title">{{ $t('新业务接入') }}</p>
        <p class="card-detail">{{ $t('新业务接入详情') }}</p>
        <div
          class="button-container"
          @click="handleNewBusiness"
        >
          <bk-button class="king-button">{{ $t('业务接入') }}</bk-button>
          <svg
            v-en-style="'left: 186px'"
            class="outside-link-icon"
            viewBox="0 0 1024 1024"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M864 864H160V160h352V96H128a32 32 0 0 0-32 32v768a32 32 0 0 0 32 32h768a32 32 0 0 0 32-32V512h-64z"
            ></path>
            <path d="M896 96H672v64h146.72l-192 192L672 397.76l192-192V352h64V128a32 32 0 0 0-32-32z"></path>
          </svg>
        </div>
      </div>
      <div
        v-if="data.getAccess"
        class="card"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
      >
        <img
          class="card-img"
          alt=""
          src="../../images/icons/get-access.svg"
        />
        <p class="card-title">{{ $t('获取权限') }}</p>
        <!-- 权限中心 -->
        <template v-if="data.getAccess.url">
          <p class="card-detail">
            {{
              data.getAccess.businessName
                ? $t('您当前没有业务--{n}的权限，请先申请吧！', { n: data.getAccess.businessName })
                : $t('您当前没有业务权限，请先申请吧！')
            }}
          </p>
          <bk-button
            class="king-button"
            @click="handleGetAccess"
            >{{ $t('权限申请') }}</bk-button
          >
        </template>
        <!-- 未接入权限中心带业务ID -->
        <p
          v-else-if="data.getAccess.businessName"
          class="card-detail"
        >
          {{
            $t('您当前没有业务--${x}的权限，请先联系运维同学{n}进行角色的添加', {
              x: data.getAccess.businessName,
              n: data.getAccess.operatorId ? `(${data.getAccess.operatorId})` : '',
            })
          }}
        </p>
        <!-- 未接入权限中心不带业务ID -->
        <p
          v-else
          class="card-detail"
        >
          {{ $t('您当前没有业务权限，请先联系对应的业务运维同学进行添加!') }}
        </p>
      </div>
      <div
        v-if="data.demoBusiness"
        class="card"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
      >
        <img
          class="card-img"
          alt=""
          src="../../images/icons/demo-business.svg"
        />
        <p class="card-title">{{ $t('业务DEMO') }}</p>
        <p class="card-detail">{{ $t('您当前想快速体验下平台的功能') }}</p>
        <bk-button
          class="king-button"
          @click="handleDemoBusiness"
          >{{ $t('我要体验') }}</bk-button
        >
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    data: {
      type: Object,
      default: () => ({
        newBusiness: {
          url: '', // 新业务接入链接
        },
        getAccess: {
          url: '', // 权限申请链接（接入权限中心时必填）
          businessName: '', // 业务ID对应的业务名（URL带ID时找到对应业务）
          operatorId: '', // 业务ID对应的运维人员ID（没有接入权限中心时URL带ID找到运维人员）
        },
        demoBusiness: {
          url: '', // 业务DEMO链接
        },
      }),
    },
  },
  methods: {
    handleMouseEnter(e) {
      const button = e.target.querySelector('.king-button');
      if (button) {
        button.classList.remove('bk-default');
        button.classList.add('bk-primary');
      }
    },
    handleMouseLeave(e) {
      const button = e.target.querySelector('.king-button');
      if (button) {
        button.classList.remove('bk-primary');
        button.classList.add('bk-default');
      }
    },
    handleNewBusiness() {
      window.open(this.data.newBusiness.url);
    },
    handleDemoBusiness() {
      window.open(this.data.demoBusiness.url);
    },
    handleGetAccess() {
      window.open(this.data.getAccess.url);
    },
  },
};
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
        position: relative;
        display: flex;
        flex-flow: column;
        align-items: center;
        width: 260px;
        height: 400px;
        background: #fff;
        border-radius: 2px;
        transition: box-shadow 0.3s;

        .outside-link-icon {
          position: absolute;
          top: 333px;
          left: 162px;
          width: 10px;
          height: 10px;
          cursor: pointer;
          fill: #63656e;
        }

        &:not(:last-child) {
          margin-right: 40px;
        }

        &:hover {
          box-shadow: 0 3px 6px 0 rgba(0, 0, 0, 0.1);
          transition: box-shadow 0.3s;

          .outside-link-icon {
            fill: #fff;
          }
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

        .king-button {
          width: 200px;
          font-size: 12px;
        }
      }
    }
  }
</style>
