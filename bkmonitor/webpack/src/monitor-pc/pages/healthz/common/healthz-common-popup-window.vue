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
  <!-- 监控后台服务弹窗 -->
  <el-dialog
    :title="dialogDescription"
    :visible.sync="isShow"
    @closed="closeDialog"
  >
    <div class="dialog-detail">
      <div v-show="!isJson">
        <p class="dialog-detail-p">
          {{ dialogStatus }} {{ dialogMessage }}
        </p>
      </div>
      <pre v-show="isJson">
{{ dialogMessage }}
</pre>
      <div
        v-for="(item, index) in tips.solution"
        v-show="tips.status > 1"
        :key="index"
      >
        <el-collapse
          v-model="activeName"
          accordion
          v-show="tips.status > 1"
          @change="collapseChange(index, item, tips.solution)"
        >
          <el-collapse-item :name="item.reason">
            <template slot="title">
              <el-tag
                size="small"
                type="danger"
              >{{ possibleSolution }}{{ index + 1 }}</el-tag>
              <span>{{ item.reason }}</span>
            </template>
            <div class="collapse-items">
              <el-tag size="small">
                {{ errorSolution }}{{ index + 1 }}
              </el-tag>
              {{ item.solution }}
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </el-dialog>
</template>
<script>
import { Collapse, CollapseItem, Dialog, Tag } from 'element-ui';

export default {
  name: 'MoHealthzCommonPopupWindowView',
  components: {
    ElDialog: Dialog,
    ElCollapse: Collapse,
    ElCollapseItem: CollapseItem,
    ElTag: Tag
  },
  props: {
    isVisible: {
      type: Boolean,
      default: false
    },
    tips: {
      type: Object,
      default() {
        return {};
      }
    }
  },
  data() {
    return {
      activeName: '',
      possibleSolution: this.$t('可能原因'),
      errorSolution: this.$t('解决方案'),
      isJson: false,
      isShow: false
    };
  },
  computed: {
    // 弹窗的状态
    dialogStatus() {
      if (this.tips.status === 0) {
        return this.$t('正常');
      }
      if (this.tips.status === 1) {
        return this.$t('关注');
      }
      if (this.tips.status > 1) {
        return this.$t('异常');
      }
      return this.$t('未知');
    },
    // 弹窗的描述
    dialogDescription() {
      if (this.tips.description && this.dialogStatus) return this.tips.description + this.dialogStatus;
      return '';
    },
    // 弹窗的信息
    dialogMessage() {
      return this.tips.message;
    }
  },
  watch: {
    isVisible(newValue, oldValue) {
      if (newValue === true && oldValue === false) {
        this.isShow = true;
      }
    }
  },
  methods: {
    // 关闭弹窗
    closeDialog() {
      this.$emit('update:isVisible', false);
    },
    // 判断后台传过来的数据是否为json数据
    isJsonString(str) {
      this.isJson = Array.isArray(str.message);
    },
    // 解决方案展开
    collapseChange(index, val, arr) {
      arr.forEach((item, i) => {
        if (index !== i) {
          item.show = false;
        }
      });
      val.show = !val.show;
    }
  }
};
</script>
<style scoped lang="scss">
@import '../style/healthz';

.el-dialog {
  background: #fff;
}

.dialog-detail {
  :deep(.el-collapse-item__content) {
    padding-bottom: 0;
    font-size: 13px;
    line-height: 1.769230769230769;
    color: #303133;
  }
}
</style>
