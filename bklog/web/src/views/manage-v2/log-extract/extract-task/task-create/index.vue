<!-- eslint-disable vue/camelcase -->
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
    class="main-container create-task-container"
    v-en-class="'en-title'"
  >
    <div class="row-container">
      <div class="title">
        {{ $t('文件来源主机') }}
        <span class="required">*</span>
      </div>
      <div class="content">
        <div class="flex-box">
          <bk-button
            data-test-id="addNewExtraction_button_selectTheServer"
            size="small"
            theme="primary"
            @click="showSelectDialog = true"
            >{{ $t('选择服务器') }}</bk-button
          >
          <div class="select-text">
            <i18n path="已选择{0}个节点">
              <span
                v-if="ipList.length"
                class="primary"
                >{{ ipList.length }}</span
              >
              <span
                v-else
                class="error"
                >{{ ipList.length }}</span
              >
            </i18n>
          </div>
        </div>
        <log-ip-selector
          :height="670"
          :original-value="ipSelectorOriginalValue"
          :panel-list="['staticTopo']"
          :show-dialog.sync="showSelectDialog"
          :show-view-diff="isClone"
          :value="selectorNodes"
          mode="dialog"
          allow-host-list-miss-host-id
          extract-scene
          keep-host-field-output
          @change="handleConfirm"
        />
        <!-- <ip-select :show-select-dialog.sync="showSelectDialog" @confirm="handleConfirm" /> -->
      </div>
    </div>

    <div class="row-container">
      <div class="title">
        {{ $t('目录或文件名') }}
        <span class="required">*</span>
        <span
          class="bklog-icon bklog-info-fill"
          v-bk-tooltips="`${$t('以')}/${$t('结尾查询指定目录下内容，否则默认查询该目录及其子目录下所有文件')}`"
        >
        </span>
      </div>
      <div class="content">
        <files-input
          v-model="fileOrPath"
          :available-paths="availablePaths"
          @update:select="handleFilesSelect"
        />
      </div>
    </div>

    <div class="row-container">
      <div class="title">{{ $t('预览地址') }}</div>
      <preview-files
        ref="preview"
        v-model="downloadFiles"
        :file-or-path="fileOrPath"
        :ip-list="ipList"
        :ip-select-new-name-list="ipSelectNewNameList"
        @update:file-or-path="handleFileOrPathUpdate"
      />
    </div>

    <div class="row-container">
      <div class="title">{{ $t('文本过滤') }}</div>
      <div class="content">
        <text-filter ref="textFilter" />
      </div>
    </div>

    <div class="row-container">
      <div class="title">{{ $t('备注') }}</div>
      <div class="content">
        <bk-input
          style="width: 261px"
          v-model="remark"
        ></bk-input>
      </div>
    </div>
    <div class="row-container">
      <div class="title">{{ $t('提取链路') }}</div>
      <div class="content">
        <bk-select
          style="width: 250px; margin-right: 20px; background-color: #fff"
          v-model="link_id"
          :clearable="false"
          data-test-id="addNewExtraction_select_selectLink"
        >
          <bk-option
            v-for="link in extractLinks"
            :id="link.link_id"
            :key="link.link_id"
            :name="link.show_name"
          >
          </bk-option>
        </bk-select>
      </div>
      <div class="content">{{ $t('选择离你最近的提取链路') }}</div>
    </div>

    <div class="button-container">
      <bk-button
        style="width: 120px; margin-right: 16px"
        :disabled="canSubmit"
        data-test-id="addNewExtraction_button_submitConfigure"
        theme="primary"
        @click="handleSubmit"
      >
        {{ $t('提交下载任务') }}
      </bk-button>
      <bk-button
        style="width: 120px"
        data-test-id="addNewExtraction_button_cancel"
        @click="goToHome"
        >{{ $t('取消') }}</bk-button
      >
    </div>
  </div>
</template>

<script>
  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import LogIpSelector, { toSelectorNode, toTransformNode } from '@/components/log-ip-selector/log-ip-selector';
  // #else
  // #code const LogIpSelector = () => null;
  // #endif

  import FilesInput from '@/views/extract/create/files-input';
  import PreviewFiles from '@/views/extract/create/preview-files';
  import TextFilter from '@/views/extract/create/test-filter';
  import { mapGetters } from 'vuex';

  export default {
    name: 'ExtractCreate',
    components: {
      LogIpSelector,
      // IpSelect,
      FilesInput,
      TextFilter,
      PreviewFiles,
    },
    data() {
      return {
        showSelectDialog: false,
        ipList: [], // 下载目标
        fileOrPath: '', // 目录
        availablePaths: [], // 目录可选列表
        downloadFiles: [], // 下载的文件
        remark: '', // 备注
        extractLinks: [], // 提取链路
        link_id: null,
        // 编辑态ip选择器初始值
        ipSelectorOriginalValue: null,
        ipSelectNewNameList: [], // 生成新的展示所用的预览地址列表
      };
    },
    computed: {
      ...mapGetters({
        globalsData: 'globals/globalsData',
      }),
      canSubmit() {
        return (!this.ipList.length || !this.downloadFiles.length) && this.link_id != null;
      },
      isClone() {
        return this.$route.name === 'extract-clone' && !!sessionStorage.getItem('cloneData');
      },
      // ip选择器选中节点
      selectorNodes() {
        return { host_list: toSelectorNode(this.ipList, 'INSTANCE') };
      },
    },
    mounted() {
      this.checkIsClone();
      this.getExtractLinkList();
    },
    methods: {
      async checkIsClone() {
        if (this.isClone) {
          const cloneData = JSON.parse(sessionStorage.getItem('cloneData'));
          sessionStorage.removeItem('cloneData');
          this.ipList = cloneData.ip_list; // 克隆下载目标
          this.fileOrPath = cloneData.preview_directory; // 克隆目录
          this.$refs.textFilter.handleClone(cloneData); // 克隆文本过滤
          this.remark = cloneData.remark; // 克隆备注
          // 获取目录下拉列表和预览地址
          this.initCloneDisplayName(); // 克隆时 请求displayName列表来展示预览字段
          this.handleCloneAvailablePaths(cloneData);
          this.$nextTick(() => {
            this.$refs.preview.handleClone(cloneData);
          });
          this.ipSelectorOriginalValue = { host_list: toSelectorNode(this.ipList, 'INSTANCE') };
        }
      },
      initCloneDisplayName() {
        const requestIpList = this.ipList.map(item => {
          if (item?.bk_host_id) {
            return {
              host_id: item.bk_host_id,
            };
          }
          return {
            ip: item.ip ?? '',
            cloud_id: item.bk_cloud_id ?? '',
          };
        });
        this.$http
          .request('extract/getIpListDisplayName', {
            data: {
              host_list: requestIpList,
            },
            params: {
              bk_biz_id: this.$store.state.bkBizId,
            },
          })
          .then(res => {
            this.initSelectNewNameList(res.data, true);
          })
          .catch(err => {
            console.warn(err);
            this.ipSelectNewNameList = [];
          });
      },
      getExtractLinkList() {
        this.$http
          .request('extract/getExtractLinkList', {
            data: { bk_biz_id: this.$store.state.bkBizId },
          })
          .then(res => {
            this.extractLinks = res.data;
            this.link_id = this.extractLinks[0].link_id;
          })
          .catch(e => {
            console.warn(e);
          });
      },
      handleCloneAvailablePaths(cloneData) {
        this.$http
          .request('extract/getAvailableExplorerPath', {
            data: {
              bk_biz_id: this.$store.state.bkBizId,
              ip_list: cloneData.ip_list,
            },
          })
          .then(res => {
            this.availablePaths = res.data.map(item => item.file_path);
          })
          .catch(e => {
            console.warn(e);
          });
      },
      handleFileOrPathUpdate(fileOrPath) {
        this.fileOrPath = fileOrPath;
      },
      handleFilesSelect(fileOrPath) {
        this.$refs.preview.getExplorerList({ path: fileOrPath });
      },
      async handleConfirm(value) {
        const { host_list: hostList } = value;
        this.initSelectNewNameList(hostList);
        const ipList = toTransformNode(hostList, 'INSTANCE', true);
        // 选择服务器后，获取可预览的路径
        const strategies = await this.$http.request('extract/getAvailableExplorerPath', {
          data: {
            bk_biz_id: this.$store.state.bkBizId,
            ip_list: ipList,
          },
        });
        const availablePaths = strategies.data.map(item => item.file_path);
        this.ipList = ipList;
        this.availablePaths = availablePaths;
      },
      /**
       * @desc: 初始化预览地址
       * @param {Array} hostList host列表
       * @param {Boolean} isClone 是否是克隆回显
       */
      initSelectNewNameList(hostList, isClone = false) {
        if (!isClone) {
          // 新增 使用ip选择器里的值展示
          const priorityList = this.globalsData.host_identifier_priority ?? ['ip', 'host_name', 'ipv6'];
          this.ipSelectNewNameList = hostList.map(item => ({
            bk_host_id: item.host_id,
            ip: item.ip,
            bk_cloud_id: item.cloud_area.id,
            selectID: `${item.host_id ?? ''}_${item.ip ?? ''}_${item.cloud_area.id ?? ''}`, // select唯一key
            name: item[priorityList.find(pItem => Boolean(item[pItem]))] ?? '',
          }));
        } else {
          // 克隆 通过接口请求返回的display_name展示值
          this.ipSelectNewNameList = hostList.map(item => ({
            bk_host_id: item.bk_host_id,
            ip: item.bk_host_innerip,
            bk_cloud_id: item.bk_cloud_id,
            selectID: `${item.bk_host_id ?? ''}_${item.bk_host_innerip ?? ''}_${item.bk_cloud_id ?? ''}`, // select唯一key
            name: item.display_name,
          }));
        }
      },
      // handleConfirm(ipList, availablePaths) {
      //   this.ipList = ipList;
      //   this.availablePaths = availablePaths;
      // },
      handleSubmit() {
        this.$emit('loading', true);
        // 根据预览地址选择的文件提交下载任务
        this.$http
          .request('extract/createDownloadTask', {
            data: {
              bk_biz_id: this.$store.state.bkBizId,
              ip_list: this.ipList, // 下载目标
              preview_directory: this.fileOrPath, // 目录
              preview_ip_list: this.$refs.preview.getFindIpList(), // 预览地址
              preview_time_range: this.$refs.preview.timeRange, // 文件日期
              preview_start_time: this.$refs.preview.timeStringValue[0], // 文件日期
              preview_end_time: this.$refs.preview.timeStringValue[1], // 文件日期
              preview_is_search_child: this.$refs.preview.isSearchChild, // 是否搜索子目录
              file_path: this.downloadFiles, // 下载文件
              filter_type: this.$refs.textFilter.filterType, // 过滤类型
              filter_content: this.$refs.textFilter.filterContent, // 过滤内容
              remark: this.remark, // 备注
              link_id: this.link_id,
            },
          })
          .then(() => {
            this.goToHome();
          })
          .catch(err => {
            console.warn(err);
            this.$emit('loading', false);
          });
      },
      goToHome() {
        this.$router.push({
          name: 'log-extract-task',
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
  .create-task-container {
    min-width: 1260px;
    padding: 20px 24px;
    margin-top: 20px;
    color: #63656e;
    background-color: #fff;
    border: 1px solid #dcdee5;

    .row-container {
      display: flex;
      min-height: 40px;
      margin: 20px 0 24px;

      .title {
        width: 128px;
        margin-right: 16px;
        font-size: 12px;
        line-height: 40px;
        text-align: right;

        .required {
          font-size: 16px;
          color: #ea3636;
        }

        .bklog-info-fill {
          color: #979ba5;
          cursor: pointer;
        }
      }

      .content {
        display: flex;
        flex-flow: column;
        justify-content: center;
        min-height: 40px;
        font-size: 12px;

        .flex-box {
          display: flex;
          align-items: center;

          .select-text {
            margin-left: 12px;
            font-size: 12px;
            line-height: 16px;

            .primary {
              color: #3a84ff;
            }

            .error {
              color: #ea3636;
            }
          }
        }
      }
    }

    .button-container {
      margin: 32px 0 0 144px;
    }
  }

  .en-title {
    .row-container .title {
      /* stylelint-disable-next-line declaration-no-important */
      width: 180px !important;
    }
  }
</style>
