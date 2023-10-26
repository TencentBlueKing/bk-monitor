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
  <!-- 对 cmdb, job, bk_data 增加自动测试的功能 -->
  <el-dialog
    :title="tips.name + $t('接口列表')"
    :visible.sync="isShow"
    @closed="closeDialog"
    :modal-append-to-body="false"
    :before-close="handleClose"
  >
    <div>
      <el-button
        type="primary"
        :loading="saasDataToTest.loading"
        size="mini"
        @click="runTest"
      >
        {{ msg }}
      </el-button>
      <el-tooltip
        placement="top"
        :content="$t('测试进行时，请勿关闭弹窗！')"
      >
        <i class="el-icon-warning" />
      </el-tooltip>

      <el-card
        class="box-card"
        style="margin-top: 10px; overflow: scroll; height: 200px"
      >
        <el-tree
          :data="saasDataToTest.data"
          :props="treeProps"
          default-expand-all
        >
          <span
            class="custom-tree-node"
            slot-scope="{ node, data }"
          >
            <i
              class="el-icon-loading"
              v-if="data.loading"
            />
            <span :class="data.class">{{ node.label }}</span>
            <el-tooltip placement="top">
              <div slot="content">
                {{ $t('接口描述:') }} {{ data.description }} <br>
                {{ $t('测试参数:') }} {{ data.args }} <br>
                {{ $t('测试结果:') }} {{ data.result }}
                <br>
                <!--错误信息，只有请求出错时渲染-->
                <span v-if="data.class === 'class-error'"> {{ $t('出错信息:') }} {{ data.message }}</span>
              </div>
              <i
                class="el-icon-question"
                style="margin-left: 10px"
              />
            </el-tooltip>
          </span>
        </el-tree>
      </el-card>
    </div>
  </el-dialog>
</template>
<script>
import { mapState } from 'vuex';
import { Button, Card, Dialog, Tooltip, Tree } from 'element-ui';

export default {
  name: 'MoHealthzSaasPopupWindowView',
  components: {
    ElTooltip: Tooltip,
    ElButton: Button,
    ElCard: Card,
    ElTree: Tree,
    ElDialog: Dialog
  },
  props: {
    componentName: {
      type: String
    },
    isVisible: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      msg: this.$t('接口测试'), // 测试描述
      saasDataToTest: {}, // 要测试的接口数据
      treeProps: {
        children: 'children', // 父接口的子接口，可以为空
        label: 'label', // 接口的名称
        loading: 'loading', // loading 状态
        class: 'class', // 用于标识是否成功
        args: 'args', // 请求参数
        result: 'result', // 返回结果
        description: 'description' // 接口描述
      },
      isShow: false, // 是否显示当前弹窗
      tips: {} // 弹窗上的数据
    };
  },
  computed: {
    ...mapState(['saasComponentNeedToTest'])
  },
  watch: {
    // 当显示状态变更时，触发方法
    isVisible(newValue, oldValue) {
      if (newValue === true && oldValue === false) {
        this.loadSaasDataToTest();
        this.isShow = true;
      }
    }
  },
  methods: {
    // 通过接口的名称获取接口在列表中的位置索引
    findIndexOf(apiName, apiData) {
      for (let index = 0; index < apiData.length; index++) {
        if (apiData[index].label === apiName) {
          return index;
        }
      }
    },
    // 通过全局的数据分离得到当前组件的数据
    loadSaasDataToTest() {
      // 判断当前的 saasDataToTest 是否有数据
      if (Object.keys(this.saasDataToTest).length === 0) {
        this.$set(this.saasDataToTest, 'loading', false);
        this.saasDataToTest.data = [];
        // 当前组件在需要测试的组件中
        if (this.saasComponentNeedToTest.indexOf(this.tips.name) > -1) {
          const item = this.tips;
          if (Object.prototype.hasOwnProperty.call(item, 'api_list')) {
            // 处理依赖接口
            for (let j = 0; j < item.api_list.length; j++) {
              const tmpChildren = [];
              if (Object.prototype.hasOwnProperty.call(item.api_list[j], 'children_api_list')) {
                for (let k = 0; k < item.api_list[j].children_api_list.length; k++) {
                  tmpChildren[k] = {
                    label: item.api_list[j].children_api_list[k].api_name,
                    description: item.api_list[j].children_api_list[k].description
                  };
                  // 接口的loading状态，类名称，参数，出错信息需要实时更新
                  this.$set(tmpChildren[k], 'loading', false);
                  this.$set(tmpChildren[k], 'class', '');
                  this.$set(tmpChildren[k], 'result', {});
                  this.$set(tmpChildren[k], 'message', '');
                  this.$set(tmpChildren[k], 'args', item.api_list[j].children_api_list[k].args);
                }
              }
              if (Object.prototype.hasOwnProperty.call(item.api_list[j], 'api_name')) {
                this.saasDataToTest.data[j] = {
                  label: item.api_list[j].api_name,
                  children: tmpChildren,
                  description: item.api_list[j].description
                };
                this.$set(this.saasDataToTest.data[j], 'loading', false);
                this.$set(this.saasDataToTest.data[j], 'class', '');
                this.$set(this.saasDataToTest.data[j], 'result', {});
                this.$set(this.saasDataToTest.data[j], 'message', '');
                this.$set(this.saasDataToTest.data[j], 'args', item.api_list[j].args);
              }
            }
          }
        }
      }
    },
    // 弹窗关闭时的回调
    closeDialog() {
      this.$emit('update:isVisible', false);
    },
    // 运行接口测试
    runTest() {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      const self = this;
      const tmp = this.saasDataToTest;
      // 使按钮处于 loading 状态
      tmp.loading = true;
      // eslint-disable-next-line @typescript-eslint/prefer-for-of
      for (let i = 0; i < tmp.data.length; i++) {
        // 检查是否存在 loading 属性
        if (
          Object.prototype.hasOwnProperty.call(tmp.data[i], 'loading')
          && Object.prototype.hasOwnProperty.call(tmp.data[i], 'class')
        ) {
          // 重置 loading 状态和对应的类名称
          tmp.data[i].loading = true;
          tmp.data[i].class = '';
          // 重置所有的子api状态
          if (Object.prototype.hasOwnProperty.call(tmp.data[i], 'children')) {
            // eslint-disable-next-line @typescript-eslint/prefer-for-of
            for (let j = 0; j < tmp.data[i].children.length; j++) {
              tmp.data[i].children[j].loading = false;
              tmp.data[i].children[j].class = '';
            }
          }
        }
      }
      const tasks = [];
      let apiTest;
      if (this.tips.name === 'job') {
        apiTest = this.$api.healthz.jobTestRootApi;
      } else if (this.tips.name === 'cmdb') {
        apiTest = this.$api.healthz.ccTestRootApi;
      } else if (this.tips.name === 'bk_data') {
        apiTest = this.$api.healthz.bkDataTestRootApi;
      } else if (this.tips.name === 'metadata') {
        apiTest = this.$api.healthz.metadataTestRootApi;
      } else if (this.tips.name === 'nodeman') {
        apiTest = this.$api.healthz.nodemanTestRootApi;
      } else if (this.tips.name === 'gse') {
        apiTest = this.$api.healthz.gseTestRootApi;
      }
      // 根据依赖关系测试接口
      if (Object.prototype.hasOwnProperty.call(this.tips, 'api_list')) {
        for (let j = 0; j < this.saasDataToTest.data.length; j++) {
          const childrenList = this.saasDataToTest.data[j].children;
          let parentTask;
          // 存在子接口，需要等待子任务完成
          if (childrenList.length > 0) {
            parentTask = new Promise((resolve) => {
              const childTasks = [];
              const apiTask = apiTest({ api_name: self.saasDataToTest.data[j].label }, { needRes: true });
              apiTask.then(function (res) {
                const parentApi = self.saasDataToTest.data[j];
                // 父接口成功返回
                if (res.result && res.data.status) {
                  parentApi.loading = false;
                  parentApi.class = 'class-success';
                  // 更新接口的result参数
                  parentApi.result = res.data.result;
                  parentApi.args = res.data.args;
                  parentApi.message = res.data.message;
                  // eslint-disable-next-line @typescript-eslint/prefer-for-of
                  for (let childIndex = 0; childIndex < childrenList.length; childIndex++) {
                    const childTmpTask = new Promise((resolve) => {
                      // 重置子 api 的 loading 状态和样式
                      childrenList[childIndex].loading = true;
                      childrenList[childIndex].class = '';
                      let childApiTest;
                      if (self.tips.name === 'job') {
                        childApiTest = self.$api.healthz.jobTestNonRootApi;
                      } else if (self.tips.name === 'cmdb') {
                        childApiTest = self.$api.healthz.ccTestNonRootApi;
                      }
                      if (childApiTest) {
                        const childApiTestTask = childApiTest(
                          {
                            api_name: childrenList[childIndex].label,
                            parent_api: parentApi.label,
                            kwargs: res.data.result
                          },
                          { needRes: true }
                        );
                        childApiTestTask.then((childRes) => {
                          const parentApiIndex = self.findIndexOf(childRes.data.parent_api, self.saasDataToTest.data);
                          // eslint-disable-next-line vue/max-len
                          const childApiIndex = self.findIndexOf(
                            childRes.data.api_name,
                            self.saasDataToTest.data[parentApiIndex].children
                          );
                          // 更新子接口的loading状态
                          self.saasDataToTest.data[parentApiIndex].children[childApiIndex].args = childRes.data.args;
                          // eslint-disable-next-line vue/max-len
                          self.saasDataToTest.data[parentApiIndex].children[childApiIndex].message = childRes.data.message;
                          self.saasDataToTest.data[parentApiIndex]
                            .children[childApiIndex].result = childRes.data.result;
                          self.saasDataToTest.data[parentApiIndex].children[childApiIndex].loading = false;
                          if (childRes.result && childRes.data.status) {
                            self.saasDataToTest.data[parentApiIndex].children[childApiIndex].class = 'class-success';
                            resolve(0);
                          } else {
                            self.saasDataToTest.data[parentApiIndex].children[childApiIndex].class = 'class-error';
                            resolve(2);
                          }
                        });
                      }
                    });
                    childTasks.push(childTmpTask);
                  }
                  Promise.all(childTasks).then((res) => {
                    // eslint-disable-next-line @typescript-eslint/prefer-for-of
                    for (let i = 0; i < res.length; i++) {
                      if (res[i] === 2) resolve(2);
                    }
                    resolve(0);
                  });
                } else {
                  parentApi.loading = false;
                  parentApi.class = 'class-error';
                  // 更新接口的result参数
                  parentApi.result = res.data.result;
                  parentApi.args = res.data.args;
                  parentApi.message = res.data.message;
                  // 更新子接口的状态
                  for (let childIndex = 0; childIndex < childrenList.length; childIndex++) {
                    self.saasDataToTest.data[j].children[childIndex].args = {};
                    self.saasDataToTest.data[j].children[childIndex].message = this.$t('测试父接口失败');
                    self.saasDataToTest.data[j].children[childIndex].result = {};
                    self.saasDataToTest.data[j].children[childIndex].loading = false;
                    self.saasDataToTest.data[j].children[childIndex].class = 'class-error';
                  }
                  resolve(2);
                }
              });
            });
          } else {
            parentTask = new Promise((resolve) => {
              const apiTask = apiTest({ api_name: self.saasDataToTest.data[j].label }, { needRes: true });
              apiTask.then((res) => {
                const apiIndex = self.findIndexOf(res.data.api_name, self.saasDataToTest.data);
                const parentApi = self.saasDataToTest.data[apiIndex];
                parentApi.loading = false;
                // 更新接口的result参数
                parentApi.result = res.data.result;
                parentApi.args = res.data.args;
                parentApi.message = res.data.message;
                if (res.result && res.data.status) {
                  parentApi.class = 'class-success';
                  resolve(0);
                } else {
                  parentApi.class = 'class-error';
                  resolve(2);
                }
              });
            });
          }
          tasks.push(parentTask);
        }
      }
      // 所有请求都完成后，更新“开始测试”按钮的加载状态
      Promise.all(tasks).then((res) => {
        // 通过所有接口的计算结果计算最后状态
        let status = 0;
        // eslint-disable-next-line @typescript-eslint/prefer-for-of
        for (let i = 0; i < res.length; i++) {
          if (res[i] === 2) {
            status = 2;
            break;
          }
        }
        // 使按钮处于 loading 状态
        self.saasDataToTest.loading = false;
        self.changeStatus(status, self.componentName);
        self.msg = self.$t('重新测试');
      });
    },
    // 弹窗关闭前，检查是否测试结束，没有的话，则需要提示用户
    handleClose(done) {
      if (this.saasDataToTest.loading === true) {
        this.$confirm(this.$t('测试进行中，确定退出？'))
          .then(() => {
            done();
          })
          .catch(() => {});
      } else {
        done();
      }
    },
    // 接口测试结束后，更新当前组件的状态 0 表示正常，1表示关注（暂时保留），2表示错误
    changeStatus(status, componentName) {
      this.$emit('changestatus', status, componentName);
    }
  }
};
</script>
<style scoped lang="scss">
@import '../style/healthz';
</style>
