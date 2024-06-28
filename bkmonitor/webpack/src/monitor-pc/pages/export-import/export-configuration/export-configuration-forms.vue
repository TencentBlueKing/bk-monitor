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
  <div class="export-table-form">
    <!-- 标题 -->
    <div class="table-title">
      {{ name }}
    </div>
    <!-- 表格 -->
    <div
      v-if="list.length"
      class="table-content"
    >
      <!-- 全选 -->
      <bk-checkbox
        :value="allElection"
        :indeterminate="indeterminate"
        @change="handleAllElection"
      >
        <div class="content-checkbox">
          <div>
            {{ $t('全选') }}&nbsp;&nbsp;
            <i18n path="共计{0}项"> &nbsp;{{ list.length }}&nbsp; </i18n>
          </div>
          <div>
            <i18n path="已选{0}项">
              &nbsp;<span class="blue">{{ groupChecked.length }}</span
              >&nbsp;
            </i18n>
          </div>
        </div>
      </bk-checkbox>
      <!-- 单选 -->
      <bk-checkbox-group
        v-model="groupChecked"
        @change="handleCheckChange"
      >
        <div
          v-for="(item, index) in list"
          :key="index"
          @mouseenter="handleTableRowEnter(index)"
          @mouseleave="handleTableRowLeave"
        >
          <bk-checkbox :value="item.id">
            <div class="content-checkbox">
              <div class="font">
                {{ item.name }}<span>（#{{ item.id }}）</span>
              </div>
              <div
                v-show="hover === index"
                class="icon"
              >
                <i
                  v-if="item.dependencyPlugin"
                  ref="Icon"
                  class="icon-monitor icon-mc-guanlian"
                  @mouseenter.self="handleIconEnter($event, item.dependencyPlugin)"
                  @mouseleave.self="handleIconLeave"
                />
                <i
                  class="icon-monitor icon-mc-wailian"
                  @click.stop="handleToDetail(item.id)"
                />
              </div>
            </div>
          </bk-checkbox>
        </div>
      </bk-checkbox-group>
    </div>
    <!-- 无数据 -->
    <div
      v-else
      class="content-none"
    >
      <empty-status
        :type="emptyStatus.type"
        @operation="emptyStatus.handleOperation"
      />
    </div>
  </div>
</template>

<script>
import EmptyStatus from '../../../components/empty-status/empty-status';

export default {
  name: 'ExportConfigurationForms',
  components: { EmptyStatus },
  inject: ['authority', 'handleShowAuthorityDetail', 'emptyStatus'],
  props: {
    // form 数据
    list: {
      type: Array,
      default: () => [],
    },
    // 标题
    name: {
      type: String,
      default: '',
    },
    // 跳转路由
    routeName: {
      type: String,
      default: '',
    },
    // 已勾选ID
    checked: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      groupChecked: [],
      hover: -1,
      popover: {
        index: -1,
        instance: null,
      },
    };
  },
  computed: {
    // 全选的状态
    allElection() {
      return this.groupChecked.length === this.list.length;
    },
    // 半选的状态
    indeterminate() {
      return this.groupChecked.length !== 0;
    },
  },
  watch: {
    // 数据切换时，清空勾选
    list() {
      this.groupChecked = [];
      this.$emit('check-change', []);
    },
    checked: {
      handler(newV) {
        this.groupChecked = newV;
      },
      immediate: true,
    },
  },
  methods: {
    // 勾选触发的回调函数
    handleCheckChange(newV) {
      this.$emit('check-change', newV);
    },
    // 表格行鼠标划入高亮事件
    handleTableRowEnter(index) {
      this.hover = index;
    },
    // 表格行鼠标划出事件
    handleTableRowLeave() {
      this.hover = -1;
    },
    // 行内icon hover划入事件
    handleIconEnter(event, text) {
      if (text) {
        this.popover.instance = this.$bkPopover(event.target, {
          content: text,
          arrow: true,
          hideOnClick: false,
        });
        this.popover.instance.show(100);
      }
    },
    // 行内icon hover划出事件
    handleIconLeave() {
      if (this.popover.instance) {
        this.popover.instance.hide(0);
        this.popover.instance.destroy();
        this.popover.instance = null;
      }
    },
    // 全选事件
    handleAllElection() {
      if (this.allElection) {
        this.groupChecked = [];
      } else {
        this.groupChecked = this.list.map(item => item.id);
      }
      this.$emit('check-change', this.groupChecked);
    },
    // 跳转详情事件
    handleToDetail(id) {
      if (this.routeName === 'strategy-config-detail') {
        const { href } = this.$router.resolve({
          name: 'strategy-config-detail',
          params: { id },
        });
        window.open(href, '_blank');
      } else if (this.routeName === 'grafana') {
        // 跳转仪表盘
        const { href } = this.$router.resolve({
          name: 'favorite-dashboard',
          params: {
            url: id,
          },
        });
        window.open(href, '_blank');
      } else {
        const { href } = this.$router.resolve({
          name: this.routeName,
          query: { id },
        });
        window.open(href, '_blank');
      }
    },
  },
};
</script>

<style lang="scss">
.export-table-form {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  width: 0;
  border: 1px solid #dcdee5;
  border-right: 0;
  transition: width 0.5s;

  @media screen and (max-width: 1366px) {
    max-width: 420px;
  }

  &:hover {
    /* stylelint-disable-next-line declaration-no-important */
    box-shadow: 0px 3px 6px 0px rgba(0, 0, 0, 0.1);

    @media screen and (max-width: 1366px) {
      width: 420px;
    }
  }

  .table-title {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 55px;
    font-size: 14px;
    font-weight: bold;
    color: #313238;
    border-bottom: 1px solid #dcdee5;
  }

  .content-none {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 166px auto 0;
    font-size: 14px;

    i {
      height: 28px;
      margin-bottom: 13px;
      font-size: 28px;
      color: #dcdee5;
    }
  }

  .table-content {
    padding: 4px 0;
    overflow: scroll;

    .content-checkbox {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 36px;
      font-size: 12px;

      .font {
        flex-grow: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      i {
        font-size: 16px;
        color: #3a84ff;
      }

      .icon {
        margin: 6px -5px 0 0;

        i {
          font-size: 24px;
        }
      }

      .blue {
        color: #3a84ff;
      }

      .gray {
        color: #989dab;
      }

      span {
        color: #c4c6cc;
      }
    }
  }

  .right-border {
    border-right: 1px solid #dcdee5;
  }

  .bk-form-checkbox {
    width: 100%;
    padding: 0 15px 0 22px;

    &:hover {
      cursor: pointer;
      background: #eef5ff;
    }
  }

  .bk-form-checkbox .bk-checkbox-text {
    width: calc(100% - 22px);
  }

  .bk-tooltip-ref {
    margin-top: 2px;
  }
}
</style>
