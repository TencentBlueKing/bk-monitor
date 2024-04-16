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
  <div class="upload-container">
    <div class="main-file-wrap">
      <div class="upload-view">
        <div class="file-icon">
          <span
            v-if="system === 'linux_aarch64'"
            class="item-icon icon-arm"
          >ARM
          </span>
          <span
            v-else
            :class="['item-icon', 'icon-monitor', `icon-${system}`]"
          />
        </div>
        <div
          class="upload-operator"
          @mouseover="handleMouseOver('main')"
          @mouseleave="showClearIcon = false"
        >
          <span
            v-if="!fileName"
            class="upload-btn"
          >
            {{ $t('点击上传文件') }}
          </span>
          <div
            v-else
            class="file-name"
          >
            <span class="name">{{ fileName }}</span>
            <div class="icon-wrapper">
              <span
                v-show="progress === 100 || isEdit"
                @click="handleClearMainFile"
                :class="['bk-icon', monitorIcon]"
              />
            </div>
            <div
              v-show="fileName && progress !== 100 && !isEdit"
              class="progress-wrap"
            >
              <div :style="{ width: `${progress}%` }" />
            </div>
          </div>
        </div>
      </div>
      <input
        v-show="!fileName"
        ref="uploadFile"
        type="file"
        :accept="accept"
        @change="handleSelectFile"
      >
    </div>

    <template v-if="pluginType === 'Exporter'">
      <div
        v-for="(item, ind) of dependFile"
        :class="{ 'depend-file-item': true, last: ind === dependFile.length - 1 }"
        :key="`${item.fileName}_${ind}`"
      >
        <div
          v-if="!item.fileName"
          :class="{ 'depend-upload-btn': true, disabled: dependFileDisabled }"
        >
          <i class="icon-monitor icon-plus-line" />
          <span>{{ $t('执行依赖文件') }}</span>
          <input
            v-show="!item.fileName && !dependFileDisabled"
            type="file"
            accept=".zip,.rar,.tar,.tgz,.tar.gz"
            @change="e => handleDependSelectFile(e, item)"
          >
        </div>
        <div
          v-else
          class="upload-view depend-upload-view"
        >
          <div class="file-icon">
            <span class="item-icon icon-monitor icon-wendang" />
          </div>
          <div
            class="upload-operator"
            @mouseover="handleMouseOver('depend', ind)"
            @mouseleave="item.showClearIcon = false"
          >
            <div class="file-name">
              <span class="name">{{ item.fileName }}</span>
              <div class="icon-wrapper">
                <span
                  v-show="item.progress === 100"
                  v-bk-tooltips.top="item.toolTipsConf"
                  @click="handelClearDependFile(ind)"
                  :class="['bk-icon', dependFileIcon[ind]]"
                />
              </div>
              <div
                v-show="item.fileName && item.progress !== 100"
                class="progress-wrap"
              >
                <div :style="{ width: `${item.progress}%` }" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <span
        class="icon-monitor icon-tishi"
        v-bk-tooltips.top="{ content: $t('对tar、tgz、gz、zip等压缩包格式文件，会自动解压到可执行文件同级目录') }"
      />

      <bk-popover
        placement="bottom"
        width="280"
        theme="light"
        trigger="click"
        :disabled="!fileTree.length"
      >
        <span :class="{ 'preview-btn': true, 'disabled': !fileTree.length }">{{ $t('预览') }}</span>
        <div
          style="background-color: #f5f7fa"
          slot="content"
        >
          <bk-big-tree
            :data="treeData"
            show-link-line
            :options="{ idKey: 'treeId' }"
          >
            <template #default="{ data }">
              <div>
                <i
                  :class="{
                    'bk-icon icon-folder-open': data.type !== 'file',
                    'bk-icon icon-file': data.type === 'file'
                  }"
                />
                <span class="name">
                  {{ data.name }}
                </span>
              </div>
            </template>
          </bk-big-tree>
        </div>
      </bk-popover>
    </template>
  </div>
</template>
<script>
import { uploadFileCollectorPlugin } from 'monitor-api/modules/model';
import { dataDogPluginUpload } from 'monitor-api/modules/plugin';

export default {
  name: 'MoUpload',
  props: {
    pluginId: String,
    pluginType: String,
    index: Number,
    system: String,
    collector: Object,
    isEdit: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      fileName: '',
      fileDesc: null,
      showClearIcon: false,
      progress: 0,
      toolTipsConf: {
        content: '',
        disable: true
      },
      dependFileDisabled: true,
      dependFile: [],
      fileTree: []
    };
  },
  computed: {
    accept() {
      if (this.pluginType === 'DataDog') {
        return '.tgz';
      }
      return this.system === 'windows' ? '.exe' : '*';
    },
    monitorIcon() {
      if (this.toolTipsConf.content) {
        return 'icon-close error-icon';
      }
      if ((this.progress === 100 || this.isEdit) && !this.showClearIcon) {
        return 'check-icon';
      }
      if ((this.progress === 100 || this.isEdit) && this.showClearIcon) {
        return 'icon-close-circle-shape clear-icon';
      }
      return '';
    },
    dependFileIcon() {
      return this.dependFile.map((item) => {
        if (item.toolTipsConf.content) {
          return 'icon-close error-icon';
        }
        if ((item.progress === 100 || this.isEdit) && !item.showClearIcon) {
          return 'check-icon';
        }
        if ((item.progress === 100 || this.isEdit) && item.showClearIcon) {
          return 'icon-close-circle-shape clear-icon';
        }
        return '';
      });
    },
    treeData() {
      let id = 0;
      // 给文件树添加treeId，确保唯一
      function setId(data) {
        return data.map((item) => {
          const res = { ...item, treeId: id };
          id += 1;
          if (item.children) {
            res.children = setId(item.children);
          }
          return res;
        });
      }
      return setId(this.fileTree);;
    }
  },
  watch: {
    collector: {
      handler(v) {
        this.setFileData(v);
      },
      deep: true
    }
  },
  created() {
    this.dependFile = [this.initDependFileData()];
    this.setFileData(this.collector);
  },
  beforeDestroy() {
    if (this.poppoverInstance) {
      this.poppoverInstance.hide(0);
      this.poppoverInstance.destroy();
      this.poppoverInstance = null;
    }
  },
  methods: {
    /** 初始依赖文件项 */
    initDependFileData(data) {
      return {
        fileName: data?.file_name || '',
        progress: data ? 100 : 0,
        fileDesc: data || null,
        showClearIcon: false,
        toolTipsConf: {
          content: '',
          disable: true
        }
      };
    },

    /** 清除主文件 */
    handleClearMainFile() {
      this.fileName = '';
      this.fileDesc = null;
      this.progress = 0;
      this.toolTipsConf.content = '';
      this.toolTipsConf.disable = true;
      this.dependFileDisabled = true;
      this.fileTree = [];
      this.handelClearDependFile();
    },

    /** 清除依赖文件 */
    handelClearDependFile(ind) {
      if (ind === undefined) {
        this.dependFile = [this.initDependFileData()];
      } else {
        this.fileTree = this.fileTree.filter(item => item.name !== this.dependFile[ind].fileName);
        this.dependFile.splice(ind, 1);
      }
    },

    setFileData(v) {
      // eslint-disable-next-line camelcase
      if (v?.file_name) {
        this.fileDesc = v;
        this.fileName = v.file_name;
        this.dependFileDisabled = false;
        v.dependFile.length && (this.dependFile = v.dependFile.map(item => this.initDependFileData(item)));
      }
    },
    handleMouseOver(type, ind) {
      if (type === 'main') {
        this.showClearIcon = this.fileName && !this.toolTipsConf.content;
      } else {
        const target = this.dependFile[ind];
        target.showClearIcon = target.fileName && !target.toolTipsConf.content;
      }
    },
    /**
     * 计算进度条（因为定时器是异步的，在计算中可以删除其他的文件，所以不能用索引）
     * @param {*} type 文件类型：主文件还是依赖文件
     * @param {*} dependItem 依赖文件
     */
    handleProgress(type, dependItem) {
      let t = 300;
      if (type === 'main') {
        this.progress = 0;
      } else {
        dependItem.progress = 0;
      }
      const timer = setInterval(() => {
        const progress = type === 'main' ? this.progress : dependItem.progress;
        if (progress < 100 && t <= 1200) {
          t += 300;
          if (type === 'main') {
            this.progress += 20;
          } else {
            dependItem.progress += 20;
          }
        } else {
          clearInterval(timer);
        }
      }, t);
    },

    handleSelectFile(e) {
      if (!e.target.files.length) return;
      const file = e.target.files[0];
      this.fileName = file.name;
      const params = {
        file_data: file,
        file_name: file.name,
        os: this.system
      };
      if (this.isEdit) {
        params.plugin_id = this.pluginId;
      }
      let ajax = uploadFileCollectorPlugin;
      const isDataDog = this.pluginType === 'DataDog';
      if (isDataDog) {
        ajax = dataDogPluginUpload;
        delete params.file_name;
      } else {
        params.plugin_type = 'Exporter';
      }
      this.handleProgress('main');
      ajax(params)
        .then((data) => {
          this.fileDesc = {
            file_name: data.actual_filename || data.file_name,
            file_id: data.file_id,
            md5: data.file_md5 || data.md5
          };
          if (isDataDog) {
            this.fileDesc.datadog_check_name = data.datadog_check_name;
          }
          if (data.file_tree) {
            this.fileTree = [data.file_tree];
          }
          this.$emit('change', data.datadog_check_name || '');
          this.$emit('yaml', data.config_yaml || '', this.system);
          const timer = setTimeout(() => {
            this.progress = 100;
            this.dependFileDisabled = false;
            clearTimeout(timer);
          }, 300);
        })
        .catch((e) => {
          this.progress = 100;
          this.toolTipsConf.content = e.message || this.$t('网络错误');
          this.toolTipsConf.disable = false;
        });
      e.target.value = '';
    },

    /**
     * 依赖文件上传（因为上传是异步的，在上传中可以删除其他的文件，所以不能用索引）
     * @param {*} e 事件对象
     * @param {*} item 依赖文件
     */
    handleDependSelectFile(e, item) {
      if (!e.target.files.length) return;
      const file = e.target.files[0];
      item.fileName = file.name;
      // 如果所有上传选择器都选择了文件，新增一个上传选择器
      if (this.dependFile.every(item => item.fileName)) {
        this.dependFile.push(this.initDependFileData());
      }
      this.handleProgress('depend', item);
      const params = {
        file_data: file,
        file_name: file.name,
        os: this.system,
        ext: true,
        plugin_type: 'Exporter'
      };
      if (this.isEdit) {
        params.plugin_id = this.pluginId;
      }
      uploadFileCollectorPlugin(params)
        .then((data) => {
          item.fileDesc = {
            file_name: data.actual_filename || data.file_name,
            file_id: data.file_id,
            md5: data.file_md5 || data.md5
          };
          data.file_tree && this.fileTree.push(data.file_tree);
          const timer = setTimeout(() => {
            item.progress = 100;
            setTimeout(timer);
          }, 300);
        })
        .catch((e) => {
          item.progress = 100;
          item.toolTipsConf.content = e.message || this.$t('网络错误');
          item.toolTipsConf.disable = false;
        });
      e.target.value = '';
    }
  }
};
</script>
<style lang="scss" scoped>
.upload-container {
  display: flex;
  flex-wrap: wrap;
  min-height: 32px;

  input {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 10;
    width: 100%;
    height: 100%;
    cursor: pointer;
    opacity: 0;
  }

  .upload-view {
    display: flex;
    width: 100%;
    height: 100%;

    .file-icon {
      flex: 0 0 32px;
      height: 100%;

      .item-icon {
        position: relative;
        display: inline-block;
        width: 100%;
        height: 100%;
        overflow: hidden;
        font-size: 16px;
        line-height: 32px;
        text-align: center;

        .set-mark {
          position: absolute;
          top: -14px;
          left: -14px;
          width: 28px;
          height: 28px;
          background-color: #979ba5;
          transform: rotate(-45deg);

          .set-mark-font {
            position: absolute;
            top: 2px;
            left: 6px;
            font-size: 12px;
            color: #fff;
            transform: scale(.8);
          }
        }
      }

      .icon-arm {
        font-size: 12px;
      }
    }

    .upload-operator {
      position: relative;
      width: calc(100% - 32px);
      font-size: 12px;
      line-height: 32px;
      border-left: 0;

      .upload-btn {
        color: #c4c6cc;
        cursor: pointer;
      }

      .file-name {
        position: relative;
        display: flex;
        align-items: center;
        height: 100%;

        .name {
          display: inline-block;
          width: calc(100% - 35px);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .icon-wrapper {
        position: absolute;
        top: 8px;
        right: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
      }

      .check-icon {
        width: 13px;
        height: 7.5px;
        border-bottom: 2px solid #2dcb56;
        border-left: 2px solid #2dcb56;
        transform: rotateZ(-45deg) translate(0px, -4px);
      }

      .clear-icon {
        z-index: 11;
        font-size: 16px;
        color: #c4c6cc;
        cursor: pointer;
      }

      .error-icon {
        font-size: 18px;
        font-weight: 600;
        color: red;
        cursor: pointer;
      }

      .progress-wrap {
        position: absolute;
        bottom: 4px;
        width: calc(100% - 9px);
        height: 2px;
        background: #dcdee5;

        div {
          width: 100%;
          height: 2px;
          background-color: #3a84ff;
        }
      }
    }
  }

  .main-file-wrap {
    position: relative;
    box-sizing: border-box;
    width: 300px;
    height: 32px;
    margin-right: 12px;
    margin-bottom: 12px;
    border: 1px dashed #c4c6cc;
  }

  .depend-file-item {
    height: 32px;
    margin-right: 12px;
    margin-bottom: 12px;

    &.last {
      margin-right: 0;
    }
  }

  .depend-upload-btn {
    position: relative;
    font-size: 12px;
    line-height: 32px;
    color: #3a84ff;
    cursor: pointer;

    &.disabled {
      color: #c4c6cc;
      cursor: not-allowed;
    }

    .icon-monitor {
      margin-right: 6px;
    }
  }

  .depend-upload-view {
    box-sizing: border-box;
    width: 300px;
    height: 100%;
    border: 1px dashed #c4c6cc;
  }

  .icon-tishi {
    margin-left: 9px;
    font-size: 14px;
    line-height: 32px;
  }

  .preview-btn {
    margin-left: 13px;
    font-size: 12px;
    line-height: 32px;
    color: #3a84ff;
    cursor: pointer;

    &.disabled {
      color: #c4c6cc;
      cursor: not-allowed;
    }
  }
}
</style>
