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
  <article
    class="config-upload"
    :class="{ 'content-hover': beforeUpload, isdrag: isdrag }"
  >
    <!--上传界面-->
    <section
      v-if="beforeUpload"
      class="config-upload-content"
    >
      <slot
        name="upload-content"
        v-bind="{ acceptTips }"
      >
        <span class="content-icon"><i class="icon-monitor icon-upload-cloud" /></span>
        <span class="content-drop"> {{ $t('点击选择或拖拽文件至此') }} </span>
        <span class="content-tip">{{ acceptTips }}</span>
      </slot>
    </section>
    <!--上传过程-->
    <section
      v-else
      class="config-upload-file"
    >
      <slot
        name="upload-file"
        v-bind="{ beforeAbortUpload, file }"
      >
        <span class="file-abort"
          ><i
            class="icon-monitor icon-mc-close"
            @click="beforeAbortUpload"
        /></span>
        <div class="file-info">
          <span class="info-icon"><i class="icon-monitor icon-mc-file" /></span>
          <div class="info-name">
            <span>{{ file.name || '' }}</span>
          </div>
          <div class="info-progress">
            <div
              class="progress-bar"
              :class="{ 'fail-background': file.hasError }"
              :style="{ width: file.percentage || 0 }"
            />
          </div>
          <span
            class="info-status"
            :class="{ 'fail-message': file.hasError }"
            >{{ fileStatusMap[file.status] || file.errorMsg }}</span
          >
        </div>
      </slot>
    </section>
    <!--上传文件框-->
    <section
      v-show="beforeUpload || file.hasError"
      class="config-upload-input"
    >
      <slot
        name="upload-input"
        v-bind="{ file, handleChange, accept }"
      >
        <input
          ref="uploadel"
          :class="{ 'input-hide': file.hasError }"
          :accept="accept"
          :multiple="false"
          :name="name"
          title=""
          :disabled="!beforeUpload && !isdrag"
          type="file"
          @change="handleChange"
        />
      </slot>
    </section>
    <!--上传提示-->
    <section class="config-upload-footer">
      <slot name="upload-footer">
        <div class="footer-explain" />
      </slot>
    </section>
  </article>
</template>

<script>
export default {
  name: 'ImportConfigurationUpload',
  props: {
    // 上传至服务器的名称
    name: {
      type: String,
      default: 'file_data',
    },
    // mime类型
    accept: {
      type: String,
      default: '.bz2,.gz,.tgz,.tbz2',
    },
    // 接受类型提示信息
    acceptTips: {
      type: String,
      default() {
        return this.$t('仅支持导入".gz .tgz .bz2 .tbz2"gzip或bzip2压缩格式文件');
      },
    },
    // URL
    action: {
      required: true,
      type: String,
    },
    // 最大文件大小
    maxSize: {
      type: Number,
      default: 500, // 单位M
    },
    // 请求头
    headers: {
      type: [Array, Object],
    },
    withCredentials: {
      type: Boolean,
      default: false,
    },
    // 文件状态
    fileStatusMap: {
      type: Object,
      default() {
        return {
          ready: this.$t('准备中...'),
          uploading: this.$t('正在上传...'),
        };
      },
    },
    // 上传失败回调
    onUploadError: {
      type: Function,
      default: () => {},
    },
    // 上传成功回调
    onUploadSuccess: {
      type: Function,
      default: () => {},
    },
    // 上传进度回调
    onUploadProgress: {
      type: Function,
      default: () => {},
    },
  },
  data() {
    return {
      isdrag: false, // 是否在拖拽
      file: {}, // 当前文件对象
      reqsMap: {}, // 文件请求Map（用于终止）
      beforeUpload: true, // 文件上传步骤
      fileIndex: 1, // 文件索引
    };
  },
  mounted() {
    // 注册拖拽事件
    const uploadEl = this.$refs.uploadel;
    uploadEl.addEventListener('dragenter', () => {
      this.isdrag = true;
    });
    uploadEl.addEventListener('dragleave', () => {
      this.isdrag = false;
    });
    uploadEl.addEventListener('dragend', () => {
      this.isdrag = false;
    });
  },
  methods: {
    // 文件变更
    handleChange(e) {
      this.isdrag = false;
      const { files } = e.target;
      const [file] = Array.from(files);
      if (this.validateFile(file)) {
        this.file = {};
        this.handleUploadFiles(file);
      } else {
        this.$refs.uploadel.value = '';
      }
    },
    // 组装文件对象，添加额外属性
    handleAssembleFile(file) {
      return {
        name: file.name,
        type: file.type,
        size: file.size,
        percentage: 0,
        uid: Date.now() + (this.fileIndex += 1),
        originFile: file,
        status: 'ready',
        hasError: false,
        errorMsg: '',
      };
    },
    // 文件名
    fileType(file) {
      const { name } = file;
      const names = name.split('.');
      const type = names[names.length - 1];
      return `.${type}`;
    },
    // 校验文件
    validateFile(file) {
      if (!file) return false;
      const validate = {
        message: '',
        success: true,
      };
      if (file.size > this.maxSize * 1024 * 1024) {
        validate.success = false;
        validate.message = this.$t('文件不能超过{size}MB', { size: this.maxSize });
      }
      if (!this.accept.split(',').includes(this.fileType(file))) {
        validate.success = false;
        validate.message = this.acceptTips;
      }
      if (!validate.success) {
        this.$bkMessage({
          theme: 'error',
          message: validate.message,
          ellipsisLine: 0,
        });
      }
      return validate.success;
    },
    // 上传文件
    handleUploadFiles(file) {
      this.beforeUpload = false;
      // 修改原file对象的属性
      this.file = this.handleAssembleFile(file);
      const { originFile, uid } = this.file;
      this.$refs.uploadel.value = null;
      const options = {
        headers: this.headers,
        withCredentials: this.withCredentials,
        file: originFile,
        filename: this.name,
        action: this.action,
        onProgress: e => {
          this.handleHttpProgress(e, originFile);
        },
        onSuccess: res => {
          this.handleHttpSuccess(res, originFile);
          delete this.reqsMap[uid];
        },
        onError: err => {
          this.handleHttpError(err, originFile);
          delete this.reqsMap[uid];
        },
      };
      const req = this.handleHttpRequest(options);
      this.reqsMap[uid] = req;
    },
    beforeAbortUpload() {
      if (this.file.hasError) {
        this.handleAbortUpload();
      } else {
        this.$bkInfo({
          title: this.$t('确定要终止上传?'),
          maskClose: true,
          confirmFn: () => {
            this.handleAbortUpload();
          },
        });
      }
    },
    // 终止文件上传
    handleAbortUpload() {
      if (this.file.uid && this.reqsMap[this.file.uid]) {
        this.reqsMap[this.file.uid].abort();
        delete this.reqsMap[this.file.uid];
      }
      this.file = {};
      this.beforeUpload = true;
    },
    // 发送HTTP请求
    handleHttpRequest(option) {
      if (typeof XMLHttpRequest === 'undefined') return;

      const xhr = new XMLHttpRequest();
      if (xhr.upload) {
        xhr.upload.onprogress = e => {
          if (e.total > 0) {
            e.percent = Math.round((e.loaded * 100) / e.total);
          }
          option.onProgress(e);
        };
      }

      const formData = new FormData();
      formData.append(option.filename, option.file, option.file.name);
      formData.append('bk_biz_id', this.$store.getters.bizId);
      xhr.onerror = e => {
        option.onError(e);
      };

      const { action } = option;
      xhr.onload = () => {
        if (xhr.status < 200 || xhr.status >= 300 || !JSON.parse(xhr.response).result) {
          return option.onError(this.onError(action, xhr));
        }
        option.onSuccess(this.onSuccess(xhr));
      };
      xhr.open('post', action, true);

      if ('withCredentials' in xhr) {
        xhr.withCredentials = option.withCredentials;
      }
      const { headers } = option;
      if (headers) {
        if (Array.isArray(headers)) {
          headers.forEach(head => {
            const headerKey = head.name;
            const headerVal = head.value;
            xhr.setRequestHeader(headerKey, headerVal);
          });
        } else {
          const headerKey = headers.name;
          const headerVal = headers.value;
          xhr.setRequestHeader(headerKey, headerVal);
        }
      }
      xhr.send(formData);
      return xhr;
    },
    // 默认失败回调
    onError(action, xhr) {
      let msg;
      if (xhr.response) {
        msg = `${JSON.parse(xhr.response).message || xhr.response}`;
      } else if (xhr.responseText) {
        msg = `${xhr.responseText}`;
      } else {
        msg = `fail to post ${action} ${xhr.status}`;
      }

      const err = new Error(msg);
      err.status = xhr.status;
      err.method = 'post';
      err.url = action;
      return err;
    },
    // 默认成功回调
    onSuccess(xhr) {
      const text = xhr.responseText || xhr.response;
      if (!text) return text;

      try {
        return JSON.parse(text);
      } catch (e) {
        return text;
      }
    },
    // 获取进度并触发props函数
    handleHttpProgress(e, postFiles) {
      this.file.percentage = `${e.percent}%`;
      this.file.status = 'uploading';
      this.onUploadProgress(e, postFiles);
    },
    // 成功处理并触发props函数
    handleHttpSuccess(res, postFiles) {
      this.file.status = 'success';
      this.onUploadSuccess(res, postFiles);
    },
    // 失败处理并触发props函数
    handleHttpError(err, postFiles) {
      this.file.hasError = true;
      this.file.errorMsg = err.message;
      this.file.status = 'error';
      this.onUploadError(err, postFiles);
    },
  },
};
</script>

<style lang="scss" scoped>
@import '../../../theme/index';
$contentBackground: #f5f9ff;
$whiteBackground: #fff;
$contentTipColor: #979ba5;
$grayBackground: #f0f1f5;

@mixin layout-flex($flexDirection, $alignItems, $justifyContent) {
  display: flex;
  flex-direction: $flexDirection;
  align-items: $alignItems;
  justify-content: $justifyContent;
}

@mixin content-hover {
  background: $contentBackground;

  @include border-dashed-1px($primaryFontColor);
}

.content-hover {
  cursor: pointer;

  &:hover {
    @include content-hover;
  }
}

article {
  .isdrag {
    @include content-hover;
  }
}

.config-upload {
  position: relative;
  width: 836px;
  height: 420px;
  border-radius: 2px;
  background: $whiteBackground;

  @include layout-flex(column, center, flex-start);
  @include border-dashed-1px($unsetColor);

  &-content {
    @include layout-flex(column, center, flex-start);

    .content-icon {
      margin-top: 126px;
      height: 64px;
      width: 64px;
      font-size: 64px;
      color: $slightFontColor;

      .icon-upload-cloud {
        font-size: inherit;
      }
    }

    .content-drop {
      margin-top: 10px;
      line-height: 19px;
      font-size: 14px;
      font-weight: bold;
      color: $defaultFontColor;
    }

    .content-tip {
      margin-top: 6px;
      line-height: 16px;
      color: $contentTipColor;
    }
  }

  &-file {
    width: 100%;

    .file-abort {
      position: absolute;
      right: 7px;
      top: 7px;
      width: 32px;
      height: 32px;
      line-height: 32px;
      font-size: 32px;
      color: $slightFontColor;
      z-index: 2;
      cursor: pointer;

      &:hover {
        background: $grayBackground;
        border-radius: 50%;
      }
    }

    .file-info {
      width: 100%;

      @include layout-flex(column, center, flex-start);

      .info-icon {
        margin-top: 130px;
        height: 56px;
        width: 48px;
        font-size: 56px;
        color: $primaryFontColor;
      }

      .info-name {
        margin-top: 14px;
        font-size: 14px;
        font-weight: bold;
        color: $defaultFontColor;
        line-height: 19px;
      }

      .info-progress {
        margin-top: 21px;
        width: 76%;
        height: 6px;
        background: $grayBackground;
        border-radius: 3px;

        .progress-bar {
          width: 10%;
          height: 6px;
          border-radius: 3px;
          background: $primaryFontColor;
          transition: width 0.3s ease-in-out;
        }

        .fail-background {
          background: $failFontColor;
        }
      }

      .info-status {
        margin-top: 17px;
        padding: 0 20px;
        line-height: 16px;
        color: $primaryFontColor;
        word-break: break-all;
      }

      .fail-message {
        color: $failFontColor;
      }
    }
  }

  &-input {
    input {
      position: absolute;
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      cursor: pointer;
      opacity: 0;
    }

    .input-hide {
      cursor: default;
    }
  }

  &-footer {
    position: absolute;
    bottom: 20px;

    .footer-explain {
      line-height: 16px;
      color: $unsetIconColor;

      &-button {
        color: $primaryFontColor;
        cursor: pointer;
        z-index: 2;
      }
    }
  }
}
</style>
