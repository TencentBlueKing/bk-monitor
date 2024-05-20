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
    <div class="upload-view">
      <div class="file-icon">
        <span
          v-if="system === 'linux_aarch64'"
          class="item-icon icon-arm"
          >ARM</span
        >
        <span
          v-else
          :class="['item-icon', 'icon-monitor', `icon-${system}`]"
        >
          <!-- <span class="set-mark">
                        <span class="set-mark-font">64</span>
                    </span> -->
        </span>
      </div>
      <div
        class="upload-operator"
        @mouseover="handleMouseOver"
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
              v-bk-tooltips.top="toolTipsConf"
              :class="['bk-icon', monitorIcon]"
              @click="handleClear"
            />
            <span v-show="progress && progress !== 100">{{ `${progress}%` }} </span>
          </div>
          <div
            v-show="fileName"
            class="progress"
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
    />
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
      default: false,
    },
  },
  data() {
    return {
      fileName: '',
      fileDesc: null,
      showClearIcon: false,
      progress: 0,
      toolTipsConf: {
        content: '',
        disable: true,
      },
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
      if (this.toolTipsConf.content) return 'icon-close error-icon';
      if (this.progress === 100 && !this.showClearIcon) {
        return 'icon-monitor icon-mc-check-fill';
      }
      if ((this.progress === 100 || this.isEdit) && this.showClearIcon) {
        return 'icon-close-circle-shape clear-icon';
      }
      return '';
    },
  },
  watch: {
    collector: {
      handler(v) {
        this.setFileData(v);
      },
      deep: true,
    },
  },
  created() {
    this.setFileData(this.collector);
  },
  methods: {
    handleClear() {
      if (this.showClearIcon || this.toolTipsConf.content) {
        this.fileName = '';
        this.fileDesc = null;
        this.progress = 0;
        this.toolTipsConf.content = '';
        this.toolTipsConf.disable = true;
      }
    },
    setFileData(v) {
      if (v?.file_name) {
        this.fileDesc = v;
        this.fileName = v.file_name;
      }
    },
    handleMouseOver() {
      this.showClearIcon = this.fileName && !this.toolTipsConf.content;
    },
    handleProgress() {
      let t = 300;
      this.progress = 0;
      const timer = setInterval(() => {
        if (this.progress < 100 && t <= 1200) {
          t += 300;
          this.progress += 20;
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
        os: this.system,
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
      this.handleProgress();
      ajax(params)
        .then(data => {
          this.fileDesc = {
            file_name: data.actual_filename || data.file_name,
            file_id: data.file_id,
            md5: data.file_md5 || data.md5,
          };
          if (isDataDog) {
            this.fileDesc.datadog_check_name = data.datadog_check_name;
          }
          this.$emit('change', data.datadog_check_name || '');
          this.$emit('yaml', data.config_yaml || '', this.system);
          const timer = setTimeout(() => {
            this.progress = 100;
            clearInterval(timer);
          }, 300);
        })
        .catch(e => {
          this.progress = 100;
          this.toolTipsConf.content = e.message || this.$t('网络错误');
          this.toolTipsConf.disable = false;
        });
      e.target.value = '';
    },
  },
};
</script>
<style lang="scss" scoped>
.upload-container {
  position: relative;
  box-sizing: border-box;
  height: 32px;
  border: 1px dashed #c4c6cc;

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
            transform: scale(0.8);
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

      .icon-mc-check-fill {
        font-size: 16px;
        color: #2dcb56;
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

      .progress {
        position: absolute;
        bottom: 4px;
        width: 100%;
        height: 2px;
        padding-right: 9px;
        background: #fff;

        div {
          width: 100%;
          height: 2px;
          background-color: #10c178;
        }
      }
    }
  }
}
</style>
