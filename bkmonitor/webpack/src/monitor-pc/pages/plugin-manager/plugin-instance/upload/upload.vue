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
          >ARM</span>
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
                @click="handleClear('main')"
                :class="['bk-icon', monitorIcon[0]]"
              />
            </div>
            <div
              v-show="fileName && progress !== 100"
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

    <div class="dependent-file-wrap">
      <div
        v-if="dependentFile.fileName"
        :class="{ 'dependent-upload-btn': true, disabled: dependentFile.disabled }"
      >
        <i class="icon-monitor icon-plus-line" />
        <span>{{ $t('执行依赖文件') }}</span>
        <input
          v-show="!dependentFile.fileName && !dependentFile.disabled"
          type="file"
          @change="handleDependentSelectFile"
        >
      </div>
      <div
        v-else
        class="upload-view dependent-upload-view"
      >
        <div class="file-icon">
          <span class="item-icon icon-monitor icon-wendang" />
        </div>
        <div
          class="upload-operator"
          @mouseover="handleMouseOver('dependent')"
          @mouseleave="dependentFile.showClearIcon = false"
        >
          <div class="file-name">
            <span class="name">{{ dependentFile.fileName }}</span>
            <div class="icon-wrapper">
              <span
                v-show="dependentFile.progress === 100 || isEdit"
                v-bk-tooltips.top="dependentFile.toolTipsConf"
                @click="handleClear('dependent')"
                :class="['bk-icon', monitorIcon[1]]"
              />
            </div>
            <div
              v-show="dependentFile.fileName && dependentFile.progress !== 100"
              class="progress-wrap"
            >
              <div :style="{ width: `${dependentFile.progress}%` }" />
            </div>
          </div>
        </div>
      </div>
      <template v-if="!dependentFile.fileName">
        <span
          class="icon-monitor icon-tishi"
          v-bk-tooltips.top="{ content: $t('对tar、tgz、gz、zip等压缩包格式文件，会自动解压到可执行文件同级目录') }"
        />
        <bk-popover
          placement="bottom"
          width="280"
          theme="light"
          trigger="click"
        >
          <span class="preview-btn">{{ $t('预览') }}</span>
          <div
            style="background-color: #f5f7fa"
            slot="content"
          >
            <bk-tree
              :data="fileTree"
              :node-key="'id'"
              :has-border="true"
            />
          </div>
        </bk-popover>
      </template>
    </div>

    <div style="display: none">
      <div ref="preview-tree">
        <bk-tree
          :data="fileTree"
          :node-key="'id'"
          :has-border="true"
        />
      </div>
    </div>
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
      dependentFile: {
        fileName: '',
        progress: 0,
        disabled: true,
        showClearIcon: false,
        toolTipsConf: {
          content: '',
          disable: true
        }
      },
      fileTree: [
        {
          name: 'tree node1',
          title: 'tree node1',
          expanded: true,
          id: 1,
          children: [
            {
              name: 'tree node 1-1',
              title: 'tree node 1-1',
              expanded: true,
              children: [
                { name: 'tree node 1-1-1', title: 'tree node 1-1-1', id: 2 },
                { name: 'tree node 1-1-2', title: 'tree node 1-1-2', id: 3 },
                { name: 'tree node 1-1-3', title: 'tree node 1-1-3', id: 4 }
              ]
            },
            {
              title: 'tree node 1-2',
              name: 'tree node 1-2',
              id: 5,
              expanded: true,
              children: [
                { name: 'tree node 1-2-1', title: 'tree node 1-2-1', id: 6 },
                { name: 'tree node 1-2-2', title: 'tree node 1-2-2', id: 7 }
              ]
            }
          ]
        }
      ]
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
      const icons = ['', ''];
      if (this.toolTipsConf.content) {
        icons[0] = 'icon-close error-icon';
      } else if (this.progress === 100 && !this.showClearIcon) {
        icons[0] = 'check-icon';
      } else if ((this.progress === 100 || this.isEdit) && this.showClearIcon) {
        icons[0] = 'icon-close-circle-shape clear-icon';
      }

      if (this.dependentFile.toolTipsConf.content) {
        icons[1] = 'icon-close error-icon';
      } else if (this.dependentFile.progress === 100 && !this.dependentFile.showClearIcon) {
        icons[1] = 'check-icon';
      } else if ((this.dependentFile.progress === 100 || this.isEdit) && this.dependentFile.showClearIcon) {
        icons[1] = 'icon-close-circle-shape clear-icon';
      }

      return icons;
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
    handleClear(type) {
      this.reset(type);
      if (type === 'main') {
        this.reset('dependent');
      }
    },

    reset(type) {
      if (type === 'main') {
        this.fileName = '';
        this.fileDesc = null;
        this.progress = 0;
        this.toolTipsConf.content = '';
        this.toolTipsConf.disable = true;
      } else {
        this.dependentFile = {
          fileName: '',
          progress: 0,
          disabled: true,
          showClearIcon: false,
          toolTipsConf: {
            content: '',
            disable: true
          }
        };
      }
    },

    setFileData(v) {
      // eslint-disable-next-line camelcase
      if (v?.file_name) {
        this.fileDesc = v;
        this.fileName = v.file_name;
        this.dependentFile.disabled = false;
      }
    },
    handleMouseOver(type) {
      if (type === 'main') {
        this.showClearIcon = this.fileName && !this.toolTipsConf.content;
      } else {
        this.dependentFile.showClearIcon = this.dependentFile.fileName && !this.dependentFile.toolTipsConf.content;
      }
    },
    handleProgress(type) {
      let t = 300;
      if (type === 'main') {
        this.progress = 0;
      } else {
        this.dependentFile.progress = 0;
      }
      const timer = setInterval(() => {
        const progress = type === 'main' ? this.progress : this.dependentFile.progress;
        if (progress < 100 && t <= 1200) {
          t += 300;
          if (type === 'main') {
            this.progress += 20;
          } else {
            this.dependentFile.progress += 20;
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
          this.$emit('change', data.datadog_check_name || '');
          this.$emit('yaml', data.config_yaml || '', this.system);
          const timer = setTimeout(() => {
            this.progress = 100;
            this.dependentFile.disabled = false;
            clearInterval(timer);
          }, 300);
        })
        .catch((e) => {
          this.progress = 100;
          this.toolTipsConf.content = e.message || this.$t('网络错误');
          this.toolTipsConf.disable = false;
        });
      e.target.value = '';
    },

    handleDependentSelectFile(e) {
      if (!e.target.files.length) return;
      const file = e.target.files[0];
      this.dependentFile.fileName = file.name;
      this.handleProgress('dependent');
      e.target.value = '';
    }
  }
};
</script>
<style lang="scss" scoped>
.upload-container {
  display: flex;
  height: 32px;

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
    height: 100%;
    border: 1px dashed #c4c6cc;
  }

  .dependent-file-wrap {
    display: flex;
    align-items: center;
    height: 100%;
    margin-left: 12px;

    .dependent-upload-btn {
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

    .dependent-upload-view {
      box-sizing: border-box;
      width: 300px;
      height: 100%;
      border: 1px dashed #c4c6cc;
    }

    .icon-tishi {
      margin-left: 9px;
      font-size: 14px;
    }

    .preview-btn {
      margin-left: 13px;
      font-size: 12px;
      color: #3a84ff;
      cursor: pointer;
    }
  }
}
</style>
