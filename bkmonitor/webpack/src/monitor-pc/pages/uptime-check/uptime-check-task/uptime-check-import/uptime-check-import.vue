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
  <div class="uptime-check-import">
    <bk-sideslider
      :title="$t('批量导入')"
      :width="640"
      :is-show.sync="options.isShow"
      :before-close="close"
      @hidden="handleHidden"
    >
      <div
        slot="content"
        class="import-content"
      >
        <div class="import-content-body">
          <div class="file-container">
            <div
              v-show="status === 'import'"
              :class="['file-wrapper', { 'is-drap': isDrap }]"
            >
              <i class="icon-monitor icon-upload-cloud upload-icon" />
              <div class="upload-text">
                <span class="drop-upload"> {{ $t('拖拽到此处上传或点击上传') }} </span>
              </div>
              <input
                ref="uploadRef"
                type="file"
                :accept="accept"
                title=""
                @dragenter="isDrap = true"
                @dragleave="isDrap = false"
                @drop="handleDrop($event)"
                @change="handleFileChange($event)"
              />
            </div>
            <div
              v-show="status === 'uploading' || status === 'parsing'"
              class="file-result"
            >
              <div class="icon-monitor icon-xls xlsx-icon" />
              <div class="file-name">
                {{ file.name }}
              </div>
              <div
                v-show="status === 'uploading'"
                class="upload-process"
              >
                <div
                  class="process-done"
                  :style="{ width: uploadProcess + '%' }"
                />
              </div>
              <div
                v-show="status === 'parsing'"
                class="file-size"
              >
                {{ file.size | fileSizeFormat }}
              </div>
              <i
                class="bk-icon icon-close"
                @click="deleteFile"
              />
            </div>
            <div
              v-show="status === 'import' || status === 'uploading'"
              class="file-desc"
            >
              <div class="file-text">
                {{ $t('只支持“xlsx”格式的文件') }}
              </div>
              <div class="file-download">
                <div class="download-text">
                  {{ $t('模板下载') }}
                </div>
                <bk-select
                  :value="'模板下载'"
                  style="width: 150px"
                  :clearable="false"
                  @change="handleDloadTem"
                >
                  <bk-option
                    v-for="option in downloadList"
                    :id="option.id"
                    :key="option.id"
                    :name="option.name"
                  />
                </bk-select>
              </div>
            </div>
            <div
              v-show="status === 'parsing'"
              class="file-parsing"
            >
              <div
                v-show="parsingRes === 'parsing'"
                class="parsing-loading"
              >
                <svg
                  class="loading-svg"
                  viewBox="0 0 64 64"
                >
                  <g>
                    <path
                      d="M20.7,15c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0l-2.8-2.8c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L20.7,15z"
                    />
                    <path d="M12,28c2.2,0,4,1.8,4,4s-1.8,4-4,4H8c-2.2,0-4-1.8-4-4s1.8-4,4-4H12z" />
                    <path
                      d="M15,43.3c1.6-1.6,4.1-1.6,5.7,0c1.6,1.6,1.6,4.1,0,5.7l-2.8,2.8c-1.6,1.6-4.1,1.6-5.7,0s-1.6-4.1,0-5.7L15,43.3z"
                    />
                    <path d="M28,52c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V52z" />
                    <path
                      d="M51.8,46.1c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0L43.3,49c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L51.8,46.1z"
                    />
                    <path d="M56,28c2.2,0,4,1.8,4,4s-1.8,4-4,4h-4c-2.2,0-4-1.8-4-4s1.8-4,4-4H56z" />
                    <path
                      d="M46.1,12.2c1.6-1.6,4.1-1.6,5.7,0s1.6,4.1,0,5.7l0,0L49,20.7c-1.6,1.6-4.1,1.6-5.7,0c-1.6-1.6-1.6-4.1,0-5.7L46.1,12.2z"
                    />
                    <path d="M28,8c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V8z" />
                  </g>
                </svg>
                <span class="parsing-text">{{ $t('解析中...') }}...</span>
              </div>
              <div
                v-show="parsingRes === 'error'"
                class="parsing-result"
              >
                <i class="bk-icon icon-exclamation-circle-shape icon-error" />
                <span class="error-text"> {{ $t('文件已损坏') }} </span>
              </div>
            </div>
          </div>
          <div
            v-show="taskList.length > 0"
            class="data-preview"
          >
            <div class="preview-title">
              {{ $t('预览') }}
            </div>
            <div class="preview-content">
              <bk-table
                class="task-table"
                :data="taskList"
              >
                <bk-table-column
                  :label="$t('任务名')"
                  prop="name"
                  show-overflow-tooltip
                />
                <bk-table-column
                  :label="$t('类型')"
                  prop="protocol"
                />
                <bk-table-column :label="$t('创建状态')">
                  <template slot-scope="scope">
                    <bk-popover v-if="scope.row.status === 'fail'">
                      <span :class="scope.row.status">
                        {{ importStatus[scope.row.status] }}
                      </span>
                      <div slot="content">
                        <pre class="hint-content"
                          >{{ scope.row.errMsg }}
</pre
                        >
                      </div>
                    </bk-popover>
                    <span
                      v-else
                      :class="scope.row.status"
                    >
                      {{ importStatus[scope.row.status] }}
                    </span>
                  </template>
                </bk-table-column>
              </bk-table>
            </div>
          </div>
        </div>
        <div class="import-content-footer">
          <bk-button
            class="button-complete"
            theme="primary"
            :disabled="!canComplete"
            @click="complete"
          >
            {{ $t('button-完成') }}
          </bk-button>
          <bk-button @click="cancel">
            {{ $t('取消') }}
          </bk-button>
        </div>
      </div>
    </bk-sideslider>
  </div>
</template>

<script>
import { fileImportUptimeCheck, fileParse } from 'monitor-api/modules/uptime_check';
import { read, utils } from 'xlsx';

export default {
  name: 'UptimeCheckImport',
  filters: {
    // 文件大小转换过滤器：`val` 单位为 B
    fileSizeFormat(val) {
      const SIZE_1KB = 1024;
      const SIZE_1MB = 1024 ** 2;
      const SIZE_1GB = 1024 ** 3;
      const SIZE_1TB = 1024 ** 4;
      const SIZE_1PB = 1024 ** 5;
      let size = '';
      switch (true) {
        case !val || isNaN(val):
          size = '-';
          break;
        case val >= 0 && val < SIZE_1KB: // 小于 1KB
          size = `${val}B`;
          break;
        case val >= SIZE_1KB && val < SIZE_1MB: // 小于 1MB
          size = `${Math.round(val / 1024)}KB`;
          break;
        case val >= SIZE_1MB && val < SIZE_1GB: // 小于 1GB
          size = `${Math.round(val / SIZE_1MB)}MB`;
          break;
        case val >= SIZE_1GB && val < SIZE_1TB: // 小于 1TB
          size = `${Math.round(val / SIZE_1GB)}GB`;
          break;
        case val >= SIZE_1TB && val < SIZE_1PB: // 小于 1PB
          size = `${Math.round(val / SIZE_1TB)}TB`;
          break;
        default:
          // 大于 1PB
          size = `${Math.round(val / SIZE_1PB)}PB`;
          break;
      }
      return size;
    },
  },
  props: {
    options: {
      type: Object,
      default: () => ({
        isShow: false,
      }),
    },
  },
  data() {
    const url =
      process.env.NODE_ENV === 'development'
        ? process.env.proxyUrl + window.static_url
        : location.origin + window.static_url;
    return {
      file: {},
      uploadProcess: 0,
      maxFileSize: 100,
      accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      isDrap: false,
      status: 'import', // 状态：'import'-导入，'uploading'-上传中，'parsing'-解析中
      parsingRes: 'parsing', // 文件解析结果：'parsing'-解析中，'error'-解析错误
      importStatus: {
        pending: this.$t('导入中'),
        success: this.$t('成功'),
        fail: this.$t('失败'),
      },
      baseUrl: url,
      downloadList: [
        {
          id: 'HTTP(S)',
          name: 'HTTP(S)',
          url: 'example/uptime_check/bk_monitor_http_template.xlsx',
          downloadName: 'bk_monitor_http_template',
        },
        {
          id: 'TCP',
          name: 'TCP',
          url: 'example/uptime_check/bk_monitor_tcp_template.xlsx',
          downloadName: 'bk_monitor_tcp_template',
        },
        {
          id: 'UDP',
          name: 'UDP',
          url: 'example/uptime_check/bk_monitor_udp_template.xlsx',
          downloadName: 'bk_monitor_udp_template',
        },
        {
          id: 'ICMP',
          name: 'ICMP',
          url: 'example/uptime_check/bk_monitor_icmp_template.xlsx',
          downloadName: 'bk_monitor_icmp_template',
        },
      ],
      rulesMap: new Map(),
      taskList: [],
    };
  },
  computed: {
    // 能否点击完成
    canComplete() {
      return this.taskList.length && !this.taskList.find(item => item.status !== 'success');
    },
  },
  methods: {
    handleDloadTem(value) {
      const url = this.downloadList.find(item => item.name === value);
      const element = document.createElement('a');
      element.setAttribute('href', this.baseUrl + url.url);
      element.setAttribute('download', url.downloadName);
      element.style.display = 'none';
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    },
    complete() {
      const res = this.taskList.filter(item => item.status === 'success').length;
      this.$bkMessage({
        theme: 'success',
        message: this.$t('成功导入 {num} 个拨测任务', { num: res }),
      });
      this.close();
      this.$emit('complete');
    },
    cancel() {
      this.close();
    },
    close() {
      this.$emit('close');
      this.options.isShow = false; // eslint-disable-line
    },
    handleDrop(ev) {
      this.isDrap = false;
      ev.preventDefault();
      ev.stopPropagation();
      this.handleFile(ev.dataTransfer.files);
    },
    handleFileChange(ev) {
      this.handleFile(ev.target.files);
    },
    async handleFile(files) {
      if (files.length) {
        const [file] = files;
        this.file = file;
        await this.validateFile(this.getFileInfo(file));
        this.status = 'uploading';
        const parseRes = await this.parseFile(file);
        this.status = 'parsing';
        this.parsingRes = 'parsing';
        const { taskList } = this;
        const parseResData = parseRes.data;
        let item = {};
        let task = {};
        for (let index = 0, { length } = parseResData; index < length; index++) {
          item = parseResData[index];
          const rule = await this.getRules(item[this.$t('协议（必填）')]);
          if (rule.success) {
            // 该协议的规则存在
            task = this.getExcelRowData(rule.data, item);
            task = this.validateExcelRowData(rule.data, task);
            taskList.push(task);
            if (task.status === 'pending') {
              // 规则校验通过
              // 后台导入
              this.importTask([task]).then(data => {
                if (data.success.total === 1) {
                  taskList[index].status = 'success';
                } else {
                  const detail = data.failed.detail?.[0];
                  taskList[index].status = 'fail';
                  taskList[index].errMsg = detail.error_mes;
                }
              });
            }
          } else {
            taskList.push({
              name: item[this.$t('任务名称（必填）')],
              protocol: item[this.$t('协议（必填）')],
              errMsg: rule.message || this.$t('不支持该协议'),
              status: 'fail',
            });
          }
        }
        this.parsingRes = 'finish';
      }
    },
    getFileInfo(file) {
      const fileName = file.name;
      const index = fileName.lastIndexOf('.');
      const suffix = fileName.slice(index + 1);

      return {
        name: fileName,
        originSize: file.size,
        size: file.size / 1024, // 单位 KB
        type: file.type,
        suffix, // 文件名后缀
        origin: file,
      };
    },
    validateFile(file) {
      const valid = {
        success: true,
        message: '',
      };
      if (file.size > this.maxFileSize * 1024) {
        valid.success = false;
        valid.message = `${this.$t('文件不能超过{size}MB', { size: this.maxFileSize })}`;
      }
      if (this.fileName && !this.fileName.test(file.name)) {
        valid.success = false;
        valid.message = `${this.$t('文件不能超过{size}MB', { size: this.maxFileSize })}`;
      }
      if (file.type !== this.accept) {
        valid.success = false;
        valid.message = this.$t('只支持“xlsx”格式的文件');
      }
      return new Promise((resolve, reject) => {
        if (valid.success) {
          resolve(valid);
        } else {
          this.$bkMessage({
            theme: 'error',
            message: valid.message,
            ellipsisLine: 0,
          });
          reject(valid.message);
        }
      });
    },
    parseFile(file) {
      const res = {
        success: true,
        message: '',
        data: [],
      };
      const fileReader = new FileReader();
      return new Promise((resolve, reject) => {
        fileReader.onload = ev => {
          try {
            const data = ev.target.result;
            const workbook = read(data, {
              type: 'binary', // 以二进制流方式读取得到整份excel表格对象
            });
            Object.keys(workbook.Sheets).forEach((sheet, index) => {
              if (index === 0) {
                res.data.push(...utils.sheet_to_json(workbook.Sheets[sheet]));
              }
            });
            setTimeout(() => {
              resolve(res);
            }, 300);
          } catch (e) {
            setTimeout(() => {
              this.$bkMessage({
                theme: 'error',
                message: e || this.$t('解析文件失败'),
                ellipsisLine: 0,
              });
              this.parsingRes = 'error';
              reject(e);
            }, 300);
          }
        };
        fileReader.onprogress = ev => {
          setTimeout(() => {
            this.uploadProcess = Number.parseInt((ev.loaded / ev.total) * 100, 10);
          }, 300);
        };
        fileReader.readAsBinaryString(file);
      });
    },
    async getRules(type) {
      const rule = {
        success: true,
        message: '',
        data: [],
      };
      if (!type) {
        rule.success = false;
        rule.message = this.$t('注意: 必填字段不能为空');
        return rule;
      }
      if (!this.rulesMap.has(type)) {
        const res = await this.requestRules(type);
        if (res.success) {
          rule.data = res.data;
          this.rulesMap.set(type, res.data);
        } else {
          rule.success = false;
          rule.message = res.message;
        }
      } else {
        rule.data = this.rulesMap.get(type);
      }
      return rule;
    },
    requestRules(type) {
      return new Promise(resolve =>
        fileParse({ protocol: type }, { needRes: true })
          .then(res => {
            if (res.result) {
              resolve({ success: true, data: res.data });
            } else {
              resolve({ success: false, message: res.message });
            }
          })
          .catch(err => {
            resolve({ success: false, message: err.responseJSON.data });
          })
      );
    },
    isNullOrEmpty(v) {
      return typeof v === 'undefined' || v === '' || v === null;
    },
    getExcelRowData(rules, row) {
      const data = {};
      rules.forEach(item => {
        if (item.is_dict && !this.isNullOrEmpty(row[item.cnkey])) {
          data[item.enkey] = JSON.parse(row[item.cnkey]);
        } else if (item.default && this.isNullOrEmpty(row[item.cnkey])) {
          data[item.enkey] = item.default;
        } else if (['node_list', 'url_list'].includes(item.enkey)) {
          data[item.enkey] = (row[item.cnkey] ?? '').toString();
        } else {
          data[item.enkey] = row[item.cnkey] ?? '';
        }
      });
      return data;
    },
    validateExcelRowData(rules, row) {
      row.status = 'pending';
      for (const item of rules) {
        if (item.required) {
          // 必填项校验
          if (this.isNullOrEmpty(row[item.enkey])) {
            row.status = 'fail';
            row.errMsg = this.$t('字段“{key}”必填不能为空', { key: item.cnkey });
            break;
          }
          if (item.regex && !new RegExp(item.regex).test(row[item.enkey])) {
            // 正则校验
            row.status = 'fail';
            row.errMsg = this.$t('字段“{key}”正则匹配错误，正则为：{reg}', { key: item.cnkey, reg: item.regex });
            break;
          }
        } else if (!this.isNullOrEmpty(row[item.enkey])) {
          if (item.regex && !new RegExp(item.regex).test(row[item.enkey])) {
            // 正则校验
            row.status = 'fail';
            row.errMsg = this.$t('字段“{key}”正则匹配错误，正则为：{reg}', { key: item.cnkey, reg: item.regex });
            break;
          }
          // 期望响应时间最小值大于0ms校验
          if (item.enkey === 'timeout' && Number(item.default) <= 0) {
            row.status = 'fail';
            row.errMsg = this.$t('字段“{key}”请确保大于0', { key: item.cnkey });
            break;
          }
        }
      }
      return row;
    },
    importTask(data) {
      return fileImportUptimeCheck({
        task_list: data,
      });
    },
    handleHidden() {
      this.file = {};
      this.uploadProcess = 0;
      this.status = 'import';
      this.parsingRes = 'parsing';
      this.taskList = [];
      if (this.$refs.uploadRef) {
        this.$refs.uploadRef.value = '';
      }
    },
    deleteFile() {
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确定删除文件？'),
        confirmFn: () => this.handleHidden(),
      });
    },
  },
};
</script>

<style lang="scss" scoped>
@import '../../../home/common/mixins';

.uptime-check-import {
  width: 640px;

  .import-content {
    height: calc(100vh - 100px);
    padding: 20px 25px 20px 30px;

    .import-content-body {
      .file-container {
        .file-wrapper {
          position: relative;
          width: 100%;
          height: 80px;
          font-size: 14px;
          line-height: 80px;
          text-align: center;
          background: #fafbfd;
          border: 1px dashed #c4c6cc;
          border-radius: 2px;

          &.is-drap {
            border: 1px solid #0082ff;
          }

          .upload-icon {
            position: absolute;
            top: 22px;
            left: calc(50% - 10px);
            display: block;
            width: 21px;
            height: 18px;
            font-size: 21px;
            line-height: 1;
            color: #c4c6cc;
          }

          .upload-text {
            position: absolute;
            bottom: 18px;
            left: calc(50% - 74px);
            width: 148px;
            height: 16px;
            font-size: 12px;
            line-height: 16px;

            .drop-upload {
              color: #737987;
            }

            .click-upload {
              color: #3a84ff;
            }
          }

          input[type='file'] {
            position: absolute;
            top: 0;
            left: 0;
            z-index: 10;
            width: 100%;
            height: 100%;
            cursor: pointer;
            opacity: 0;
          }
        }

        .file-result {
          position: relative;
          width: 100%;
          height: 80px;
          font-size: 14px;
          line-height: 80px;
          background: #fff;
          border: 1px solid #dcdee5;
          border-radius: 2px;

          .xlsx-icon {
            position: absolute;
            top: 19px;
            left: 18px;
            width: 42px;
            height: 42px;
            font-size: 44px;
            line-height: 1;
            color: #2dcb56;
          }

          .file-name {
            position: absolute;
            top: 21px;
            left: 71px;
            height: 16px;
            font-size: 14px;
            font-weight: bold;
            line-height: 16px;
            color: #63656e;
          }

          .file-size {
            position: absolute;
            top: 42px;
            left: 71px;
            height: 19px;
            font-size: 12px;
            line-height: 19px;
            color: #979ba5;
          }

          .upload-process {
            position: absolute;
            top: 51px;
            left: 71px;
            width: 495px;
            height: 4px;
            background: #f0f1f5;
            border-radius: 2px;

            .process-done {
              height: 4px;
              background: #3a84ff;
              border-radius: 2px;
            }
          }

          .icon-close {
            position: absolute;
            top: 7px;
            right: 7px;
            width: 18px;
            height: 18px;
            color: #979ba5;
            cursor: pointer;
          }
        }

        .file-desc {
          display: flex;
          align-items: center;
          margin-top: 12px;
          font-size: 12px;
          line-height: 19px;

          .file-text {
            flex: 1;
            color: #63656e;
          }

          .file-download {
            position: relative;
            text-align: right;

            .download-text {
              position: absolute;
              top: 1px;
              left: 1px;
              width: 124px;
              height: 30px;
              padding-left: 10px;
              line-height: 30px;
              text-align: left;
              // z-index: 2;
              pointer-events: none;
              background: #fff;
            }

            :deep(.bk-select-name) {
              opacity: 0;
            }
          }
        }

        .file-parsing {
          margin-top: 12px;

          .parsing-loading {
            display: inline-flex;
            align-items: center;
            height: 19px;

            @keyframes done-loading {
              0% {
                transform: rotate(0deg);
              }

              100% {
                transform: rotate(-360deg);
              }
            }

            .loading-svg {
              width: 18px;
              height: 18px;
              animation: done-loading 1s linear 0s infinite;

              g {
                @for $i from 1 through 8 {
                  :nth-child(#{$i}) {
                    opacity: #{$i * 0.125};
                    fill: $primaryFontColor;
                  }
                }
              }
            }

            .parsing-text {
              margin-left: 8px;
              font-size: 14px;
              color: #737987;
            }
          }

          .parsing-result {
            display: inline-flex;
            align-items: center;
            height: 19px;

            .icon-error {
              width: 16px;
              height: 16px;
              line-height: 1;
              color: #ea3636;
            }

            .error-text {
              height: 19px;
              margin-left: 8px;
              font-size: 14px;
              line-height: 19px;
              color: #737987;
            }
          }
        }
      }

      .data-preview {
        .preview-title {
          height: 19px;
          margin-top: 18px;
          font-size: 14px;
          font-weight: bold;
          line-height: 19px;
          color: #737987;
        }

        .preview-content {
          margin-top: 8px;

          .task-table {
            .pending {
              color: #3a84ff;
            }

            .success {
              color: #2dcb56;
            }

            .fail {
              color: #ea3636;
              cursor: pointer;
            }
          }
        }
      }
    }

    .import-content-footer {
      margin-top: 17px;

      .button-complete {
        margin-right: 10px;
      }
    }
  }
}

body {
  :deep(.hint-content) {
    padding: 0;
    margin: 0;
    color: #fff;
    background: #333;
    border: 0;
  }
}
</style>
