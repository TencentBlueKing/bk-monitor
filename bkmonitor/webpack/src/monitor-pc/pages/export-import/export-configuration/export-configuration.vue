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
  <div
    v-bkloading="{ isLoading: loading }"
    class="export"
  >
    <!-- 搜索——下拉选框 组件 -->
    <select-input
      ref="selectInput"
      :parent-loading="loading"
      :default-value="defaultValue"
      @change-table-loading="handleChangeLoading"
      @select-data="handleChangeSelectData"
    />
    <div class="export-table">
      <!-- 表格 组件 -->
      <export-configuration-form
        v-for="(item, index) in exportData"
        :key="item.name"
        :class="{ 'view-border': index === exportData.length - 1 }"
        :list="item.list"
        :name="item.name"
        :route-name="item.routeName"
        :checked="item.checked"
        @check-change="handleCheckChange(...arguments, index)"
      />
    </div>
    <bk-button
      theme="primary"
      :disabled="isdisable"
      class="btn"
      @click="handleSubmit"
    >
      {{ $t('导出') }}
    </bk-button>
    <bk-button
      class="cancel"
      @click="handleCancel"
    >
      {{ $t('取消') }}
    </bk-button>
    <!-- 导出dialog框 组件 -->
    <export-configuration-dialog
      :state="state"
      :package-num="packageNum"
      :show.sync="dialogShow"
      :message="message"
    />
  </div>
</template>

<script>
import { queryAsyncTaskResult } from 'monitor-api/modules/commons';
import { exportPackage } from 'monitor-api/modules/export_import';
import { mapActions } from 'vuex';

import authorityMixinCreate from '../../../mixins/authorityMixin';
import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import * as importExportAuth from '../authority-map';
import exportConfigurationDialog from './export-configuration-dialog';
import exportConfigurationForm from './export-configuration-forms';
import selectInput from './select-input';

export default {
  name: 'ExportConfiguration',
  components: {
    selectInput,
    exportConfigurationForm,
    exportConfigurationDialog,
  },
  mixins: [authorityMixinCreate(importExportAuth)],
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail,
      emptyStatus: this.emptyStatus,
    };
  },
  // created () {
  //     this.getTableList()
  // },
  beforeRouteEnter(to, from, next) {
    next(vm => {
      vm.updateNavData(vm.$t('route-导出配置'));
      const routeParams = vm.$route.params;
      vm.defaultValue.routeName = from.name || '';
      vm.handleDefaultChecked();
      // 如果是服务分类跳转，则不调用getAllExportList
      if (from.name === 'service-classify') {
        vm.loading = true;
        vm.defaultValue.value = 3;
        vm.defaultValue.serverFirst = routeParams.first;
        vm.defaultValue.serverSecond = routeParams.second;
      } else {
        vm.getTableList();
      }
    });
  },
  data() {
    return {
      loading: false,
      exportData: [], // 所有的导出目录
      dialogShow: false,
      timer: null,
      state: 'PREPARE_FILE',
      message: '',
      defaultValue: {
        value: 1,
      },
      packageNum: {}, // dialog里面对应的导出条数
      listMap: [
        // 勾选的ID会存到对应的checked里面
        {
          name: this.$t('采集配置'),
          id: 'collectConfigList',
          routeName: 'collect-config',
          checked: [],
        },
        {
          name: this.$t('策略配置'),
          id: 'strategyConfigList',
          routeName: 'strategy-config-detail',
          checked: [],
        },
        {
          name: this.$t('仪表盘'),
          id: 'viewConfigList',
          routeName: 'grafana',
          checked: [],
        },
      ],
      emptyStatus: {
        type: 'empty',
        changeType: this.changeType,
        handleOperation: this.handleOperation,
      },
    };
  },
  computed: {
    // 未勾选不能导出
    isdisable() {
      return this.listMap.every(item => item.checked.length === 0);
    },
  },
  beforeDestroy() {
    clearTimeout(this.timer);
  },
  methods: {
    ...mapActions('export', ['getAllExportList']),
    /**
     * 处理仪表盘选中数据
     */
    handleDefaultChecked() {
      const {
        params: { dashboardChecked = [] },
      } = this.$route;
      if (dashboardChecked) {
        const target = this.listMap.find(item => item.id === 'viewConfigList');
        !!dashboardChecked.length && this.$set(target, 'checked', dashboardChecked);
      }
    },
    updateNavData(name = '') {
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, [{ name, id: '' }]);
    },
    // 获取导出列表事件
    async getTableList(params = {}) {
      this.loading = true; // 导出列表接口
      const data = await this.getAllExportList(params);
      this.handleChangeSelectData(data);
      this.loading = false;
    },
    // 筛选事件
    handleChangeSelectData(data) {
      this.exportData = this.listMap.map(item => ({
        name: item.name,
        list: data[item.id],
        routeName: item.routeName,
        checked: item.checked,
      }));
    },
    // 勾选变更事件
    handleCheckChange(value, index) {
      this.listMap[index].checked = value;
    },
    // 开始导出和重试事件
    handleSubmit() {
      this.state = 'PREPARE_FILE';
      this.packageNum = {};
      let num = 0;
      const polling = (params, callBack) => {
        queryAsyncTaskResult(params)
          .then(data => {
            if (!data.is_completed) {
              if (data.state === 'PENDING') {
                num += 1;
                if (num > 25) {
                  clearTimeout(this.timer);
                  const result = {
                    is_completed: true,
                    state: 'FAILURE',
                    message: this.$t('请求超时'),
                  };
                  callBack(result);
                  return;
                }
              }
              this.timer = setTimeout(() => {
                polling(params, callBack);
                clearTimeout(this.timer);
              }, 500);
            }
            callBack(data);
          })
          .catch(err => {
            const result = {
              is_completed: true,
              state: 'FAILURE',
              data: err.data,
              message: err.message,
            };
            callBack(result);
          });
      };
      const params = {
        collect_config_ids: this.listMap[0].checked,
        strategy_config_ids: this.listMap[1].checked,
        view_config_ids: this.listMap[2].checked,
      };
      this.dialogShow = true;
      // 导出配置接口
      exportPackage(params, { isAsync: true })
        .then(data => {
          polling(data, data => {
            this.state = data.state;
            if (data.state === 'MAKE_PACKAGE' && data.data) {
              this.packageNum = data.data;
            }
            if (data.state === 'SUCCESS') {
              let url = data.data.download_path;
              if (data.data.download_path.indexOf('http') !== 0) {
                url =
                  process.env.NODE_ENV === 'development'
                    ? `${process.env.proxyUrl}/media${data.data.download_path}`
                    : `${window.location.origin}${window.site_url}media${data.data.download_path}`;
              }
              // 创建a标签的方式不会弹新窗口
              const element = document.createElement('a');
              element.setAttribute('href', `${url}/${data.data.download_name}`);
              element.setAttribute('download', data.data.download_name);
              element.style.display = 'none';
              document.body.appendChild(element);
              element.click();
              document.body.removeChild(element);
              this.dialogShow = false;
            }
            if (data.state === 'FAILURE') {
              this.state = data.state;
              this.message = data.message;
            }
          });
        })
        .catch(err => {
          this.state = 'FAILURE';
          this.message = err.message;
        });
    },
    // select-input 派发的loading事件
    handleChangeLoading(v) {
      this.loading = v;
    },
    // 取消按钮事件
    handleCancel() {
      this.$router.push({ name: 'export-import' });
    },
    changeType(val) {
      this.emptyStatus.type = val;
    },
    handleOperation(val) {
      this.$refs.selectInput.handleOperation(val);
    },
  },
};
</script>

<style lang="scss" scoped>
.export {
  margin: 24px;
  font-size: 12px;
  color: #63656e;

  &-table {
    display: flex;
    width: 100%;
    height: calc(100vh - 234px);
    margin-bottom: 20px;
    background: #fff;

    .view-border {
      border-right: 1px solid #dcdee5;
    }
  }

  .btn {
    margin-right: 8px;
  }

  .cancel {
    width: 88px;
  }
}
</style>
