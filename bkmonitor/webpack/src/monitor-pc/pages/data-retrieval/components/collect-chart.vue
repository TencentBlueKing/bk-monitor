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
  <div>
    <template v-if="!isSingle">
      <transition name="collection-fade">
        <div
          v-show="show"
          :class="['view-collection', { en: isEn }]"
        >
          <div style="flex-grow: 1">
            <span>{{ $t('已勾选{count}个', { count: collectList.length }) }} </span>
            <span
              class="view-collection-btn"
              @click="handleCollectionAll"
              >{{ $t('点击全选') }}</span
            >
            <span
              class="view-collection-btn"
              @click="handleShowCollectionDialog"
              >{{ $t('收藏至仪表盘') }}</span
            >
            <span
              v-if="!isDataRetrieval"
              class="view-collection-btn"
              @click="gotoDataRetrieval"
            >
              {{ $t('route-数据探索') }}</span
            >
            <span
              v-if="collectList.length > 1"
              :class="['view-collection-btn', isEn ? 'mr24' : 'mr5']"
              @click="gotoViewDetail"
              >{{ $t('对比') }}</span
            >
          </div>
          <i
            class="icon-monitor icon-mc-close-fill"
            @click="handleClose"
          />
        </div>
      </transition>
    </template>

    <!-- 收藏组件 -->
    <collection-dialog
      :collection-list="collectList"
      :is-show.sync="isDialogShow"
      @on-collection-success="onCollectionSuccess"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import { isEnFn } from '../../../utils';
import CollectionDialog from './collection-dialog.vue';

@Component({
  name: 'collect-chart',
  components: {
    CollectionDialog,
  },
} as any)
export default class CollectChart extends Vue {
  @Prop({ required: true }) show: boolean;
  @Prop({ required: true }) collectList: any[];
  @Prop({ required: true }) totalCount: number;
  @Prop({ default: false, type: Boolean }) isSingle: boolean;

  isDialogShow = false;

  isEn = isEnFn();

  get isDataRetrieval() {
    return this.$route.name === 'data-retrieval';
  }

  @Watch('isDialogShow')
  watchDialogShow(v) {
    if (!v && this.isSingle) {
      this.handleClose();
    }
  }

  @Watch('show', { immediate: true })
  watchShow(v) {
    if (v && this.isSingle) {
      this.handleShowCollectionDialog();
    }
  }
  //
  handleShowCollectionDialog() {
    this.isDialogShow = true;
  }

  handleCollectionAll() {
    this.$emit('collect-all');
  }

  onCollectionSuccess() {
    this.handleClose();
  }

  @Emit('close')
  handleClose() {
    return false;
  }

  // 跳转数据检索
  @Emit('data-retrieval')
  gotoDataRetrieval() {}

  // 跳转大图
  @Emit('view-detail')
  gotoViewDetail() {}
}
</script>
<style lang="scss" scoped>
@import '../../../theme/index.scss';

.mr24 {
  margin-right: 24px;
}

.view-collection {
  position: fixed;
  bottom: 50px;
  left: calc(50vw - 210px);
  z-index: 1999;
  display: flex;
  align-items: center;
  height: 42px;
  padding: 0 11px 0 20px;
  font-size: 14px;
  color: #fff;
  background: rgba(0, 0, 0, 0.85);
  border: 1px solid #313238;
  border-radius: 21px;

  &-btn {
    margin-left: 10px;
    color: $primaryFontColor;
    cursor: pointer;
  }

  &.en {
    .view-collection-btn {
      margin-left: 24px;
      color: $primaryFontColor;
      cursor: pointer;
    }
  }

  .icon-mc-close-fill {
    font-size: 22px;
    color: #63656e;
    cursor: pointer;
  }
}

.collection-fade-enter-active {
  transition: all 0.3s ease;
}

.collection-fade-leave-active {
  transition: all 0.3s ease;
}

.collection-fade-enter,
.collection-fade-leave-to {
  opacity: 0;
  transform: translateY(42px);
}
</style>
