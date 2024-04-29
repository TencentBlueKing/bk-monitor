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
  <div class="no-tasks">
    <div class="desc">
      {{ !isNode ? $t('暂无拨测任务') : $t('暂无拨测节点') }}
    </div>
    <div v-if="!isNode">
      <div class="create-task">
        <div class="create-title">
          {{ $t('新建') }}
        </div>
        <div class="create-desc">
          {{ $t('点击立即创建业务的拨测监控，化被动投诉为主动发现问题') }}
        </div>
        <span
          v-authority="{ active: !authority.MANAGE_AUTH }"
          class="create-btn"
          @click="authority.MANAGE_AUTH ? $emit('create') : handleShowAuthorityDetail()"
        >
          {{ $t('立即新建') }}
        </span>
      </div>
      <div class="create-task">
        <div class="create-title">
          {{ $t('导入') }}
        </div>
        <div class="create-desc">
          {{ $t('根据官方提供的任务模板Excel，您可以快速批量导入多个拨测任务') }}
        </div>
        <span
          v-authority="{ active: !authority.MANAGE_AUTH }"
          class="create-btn"
          @click="authority.MANAGE_AUTH ? $emit('import') : handleShowAuthorityDetail()"
        >
          {{ $t('导入') }}
        </span>
      </div>
    </div>
    <div v-else>
      <div class="create-task">
        <div class="create-title">
          {{ $t('新建') }}
        </div>
        <div class="create-desc">
          {{ $t('创建拨测任务前先要至少有一个拨测节点,拨测节点负责拨测任务的执行.') }}
        </div>
        <span
          v-authority="{ active: !authority.MANAGE_AUTH }"
          class="create-btn"
          @click="authority.MANAGE_AUTH ? $emit('create-node') : handleShowAuthorityDetail()"
        >
          {{ $t('立即新建') }}
        </span>
      </div>
    </div>
  </div>
</template>
<script>
export default {
  default: 'uptime-check-empty',
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    isNode: Boolean,
  },
  funtianal: true,
};
</script>

<style lang="scss" scoped>
.no-tasks {
  text-align: center;
  padding-top: 72px;
  color: #63656e;

  .desc {
    font-size: 20px;
    margin-bottom: 36px;
    color: #313238;
  }

  .create-task {
    display: inline-block;
    width: 320px;
    height: 220px;
    background: #fff;
    margin: 0 10px;
    border: 1px solid #f0f1f5;
    border-radius: 2px;

    .create-title {
      margin: 40px auto 10px auto;
      font-size: 16px;
      font-weight: bold;
    }

    .create-desc {
      margin: 0 auto 27px;
      width: 204px;
      font-size: 12px;
      color: #63656e;
    }

    .create-btn {
      display: inline-block;
      height: 36px;
      line-height: 36px;
      width: 160px;
      border: 1px solid #699df4;
      border-radius: 18px;
      color: #3a84ff;
      cursor: pointer;
      font-size: 12px;
    }
  }
}
</style>
