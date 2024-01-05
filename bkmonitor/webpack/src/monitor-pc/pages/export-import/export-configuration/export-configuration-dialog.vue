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
    v-model="show"
    :show-footer="false"
    :close-icon="false"
    width="450"
  >
    <div class="dialog">
      <!-- 导出正常 -->
      <div v-if="state !== 'FAILURE'">
        <div class="dialog-header">
          <img src="../../../static/images/svg/spinner.svg"  alt=''>
          <span v-if="state === 'PENDING' || state === 'PREPARE_FILE'"> {{ $t('准备中...') }} </span>
          <span v-else-if="state === 'MAKE_PACKAGE'"> {{ $t('打包中...') }} </span>
        </div>
        <div class="dialog-tips">
          {{ $t('所含内容文件') }}
        </div>
        <div class="dialog-content">
          <div class="column">
            <div>
              {{ $t('采集配置文件') }}
              <span
                v-show="isMakePackage"
                class="gray"
              >（<span :class="{ blue: packageNum.collect_config_file > 0 }">{{ $t(' {num} 个', { num: packageNum.collect_config_file }) }}</span>）</span>
            </div>
            <div>
              {{ $t('自动关联采集配置文件') }}
              <span
                v-show="isMakePackage"
                class="gray"
              >（<span :class="{ blue: packageNum.associated_collect_config > 0 }">{{ $t(' {num} 个', { num: packageNum.associated_collect_config }) }}</span> ）</span>
            </div>
          </div>
          <div class="column">
            <div>
              {{ $t('策略配置文件') }}
              <span
                v-show="isMakePackage"
                class="gray"
              >（<span :class="{ blue: packageNum.strategy_config_file > 0 }">{{ $t(' {num} 个', { num: packageNum.strategy_config_file }) }}</span>）</span>
            </div>
            <div>
              {{ $t('自动关联插件文件') }}
              <span
                v-show="isMakePackage"
                class="gray"
              >（<span :class="{ blue: packageNum.associated_plugin > 0 }">{{ $t(' {num} 个', { num: packageNum.associated_plugin }) }}</span>）</span>
            </div>
          </div>
          <div>
            {{ $t('仪表盘') }}
            <span
              v-show="isMakePackage"
              class="gray"
            >（<span :class="{ blue: packageNum.view_config_file > 0 }">{{ $t(' {num} 个', { num: packageNum.view_config_file }) }}</span>）</span>
          </div>
        </div>
      </div>
      <!-- 导出失败 -->
      <div v-else>
        <div class="dialog-header">
          <i class="icon-monitor icon-remind" /><span> {{ $t('导出失败，请重试！') }} </span>
        </div>
        <div
          class="dialog-tips"
          :class="{ 'tips-err': state === 'FAILURE' }"
        >{{ $t('失败原因') }}</div>
        <div class="dialog-content dialog-content-err">
          <div class="column">
            {{ message }}
          </div>
          <div class="btn">
            <span
              style="margin-right: 16px"
              @click="handlerRetry"
            > {{ $t('点击重试') }} </span><span @click="handleCloseDialog"> {{ $t('取消') }} </span>
          </div>
        </div>
      </div>
    </div>
  </bk-dialog>
</template>

<script>
export default {
  name: 'ExportConfigurationDialog',
  props: {
    // 导出状态 PENDING PREPARE_FILE MAKE_PACKAGE FAILURE
    state: {
      type: String,
      default: 'PREPARE_FILE'
    },
    // 文件具体个数
    packageNum: {
      type: Object,
      default: () => ({})
    },
    // 控制dialog显示
    show: {
      type: Boolean,
      default: false
    },
    // 错误信息
    message: String
  },
  computed: {
    // 判断各文件数值是否有值
    isMakePackage() {
      return this.state === 'MAKE_PACKAGE' && Object.keys(this.packageNum).length;
    }
  },
  methods: {
    // 导出失败取消按钮事件
    handleCloseDialog() {
      this.$emit('update:show', false);
    },
    // 重试操作事件
    handlerRetry() {
      this.$parent.handleSubmit();
    }
  }
};
</script>

<style lang="scss" scoped>
.dialog {
  position: relative;

  &-header {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80px;
    font-size: 20px;
    color: #313238;
    border-bottom: 1px solid #d8d8d8;

    img {
      width: 32px;
      height: 32px;
      margin-right: 14px;
    }

    i {
      margin-right: 14px;
      font-size: 32px;
      color: #ea3636;
    }
  }

  &-tips {
    position: absolute;
    top: 70px;
    left: 185px;
    padding: 0 7px;
    margin: auto;
    font-size: 12px;
    color: #c4c6cc;
    background: #fff;
  }

  .tips-err {
    left: 195px;
  }

  &-content {
    height: 140px;
    padding: 25px 40px 30px 40px;
    font-size: 12px;

    .column {
      display: flex;
      max-width: 340px;
      max-height: 42px;
      margin-bottom: 18px;
      overflow: hidden;
      word-break: normal;
      word-wrap: break-word;

      div {
        width: 50%;
        white-space: nowrap;
      }
    }

    .gray {
      color: #c4c6cc;
    }

    .blue {
      color: #3a84ff;
    }
  }

  &-content-err {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    padding-top: 30px;
    font-size: 14px;

    .btn {
      color: #3a84ff;

      span {
        cursor: pointer;
      }
    }
  }
}

:deep(.bk-dialog-body) {
  padding: 0;
}

:deep(.bk-dialog-tool) {
  display: none;
}
</style>
