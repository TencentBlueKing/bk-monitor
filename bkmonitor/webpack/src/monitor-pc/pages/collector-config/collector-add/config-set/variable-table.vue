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
    width="960px"
    :header-position="'left'"
    :show-footer="false"
    :title="$t('推荐变量')"
    :value="isShowVariableTable"
    theme="primary"
    @after-leave="handleAfterLeave"
  >
    <div class="variable-table">
      <div class="dialog-left">
        <bk-table
          style="margin-top: 15px"
          :data="tableData"
          size="small"
        >
          <bk-table-column
            :label="$t('变量名')"
            min-width="100"
            prop="name"
          />
          <bk-table-column
            :label="$t('含义')"
            min-width="70"
            prop="description"
          />
          <bk-table-column
            :label="$t('示例')"
            min-width="70"
            prop="example"
          />
        </bk-table>
      </div>
      <div class="dialog-right">
        <div class="title">
          {{ $t('说明') }}
        </div>
        <div class="item">
          <bk-popover>
            <div>
              <span class="tips"> {{ $t('变量格式') }} </span>：
            </div>
            <div slot="content">
              {{ $t('Jinja2模板引擎') }}
            </div>
          </bk-popover>
          <div
            class="content"
            v-text="'{{target.对象.字段名}}'"
          />
        </div>
        <div class="item">
          <div>{{ $t('对象包含') }}:</div>
          <div class="content">host {{ $t('主机') }}</div>
          <div class="content">process {{ $t('进程') }}</div>
          <div class="content">service {{ $t('服务实例') }}</div>
        </div>
        <div class="item">
          <div>{{ $t('字段名') }}:</div>
          <div class="content">
            {{ $t('CMDB中定义的字段名') }}
          </div>
        </div>
      </div>
      <div class="foot" />
    </div>
  </bk-dialog>
</template>

<script>
import { getCollectVariables } from 'monitor-api/modules/collecting';

export default {
  props: {
    isShowVariableTable: {
      type: Boolean,
      default: false,
    },
    variableData: Array,
  },
  data() {
    return {
      data: [],
    };
  },
  computed: {
    tableData() {
      if (Array.isArray(this.variableData) && this.variableData.length) return this.variableData;
      return this.data;
    },
  },
  mounted() {
    if (!this.variableData?.length) {
      this.getTableData();
    }
  },
  methods: {
    getTableData() {
      getCollectVariables().then(data => {
        this.data = data;
      });
    },
    handleAfterLeave() {
      this.$emit('update:isShowVariableTable', false);
    },
  },
};
</script>

<style lang="scss" scoped>
.bk-dialog-wrapper {
  :deep(.bk-dialog-header) {
    padding: 3px 24px 14px;
  }

  :deep(.bk-dialog-body) {
    padding: 3px 24px 0;
  }

  :deep(.bk-table-body-wrapper) {
    max-height: 430px;
    overflow: auto;
    overflow-x: hidden;
  }
}

.variable-table {
  position: relative;
  display: flex;
  font-size: 12px;
  color: #63656e;

  .dialog-left {
    width: 760px;
    max-height: 474px;
    margin-right: 20px;
    overflow: auto;

    :deep(.bk-table) {
      /* stylelint-disable-next-line declaration-no-important */
      margin-top: 0px !important;
    }
  }

  .dialog-right {
    width: 120px;

    .title {
      margin-bottom: 16px;
      font-weight: bold;
    }

    .item {
      margin-bottom: 16px;

      .content {
        color: #979ba5;
      }

      .tips {
        cursor: pointer;
        border-bottom: 1px dashed #63656e;
      }
    }
  }

  .foot {
    position: absolute;
    bottom: 0px;
    z-index: 1;
    width: 100%;
    height: 4px;
    background: #fff;
  }
}
</style>
