/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
 */
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import yamlIcon from './assets/yaml.svg';
import {
  type FileValidator,
  type IFileCheckError,
  type IUploadedFile,
  type IValidateResult,
  createUuid,
  FILE_ENCODING_INVALID,
  formatAcceptText,
  formatFileSize,
  hasAcceptedExtension,
  hasBusinessErrors,
  parseApiError,
  readFileAsUtf8,
} from './utils/multi-file-upload-utils';

import './multi-file-upload.scss';

export interface IUploadStatus {
  /** 未通过校验的文件数 + 集合级错误数 */
  invalid: number;
  /** 校验中的文件数 */
  pending: number;
}

interface IEvents {
  onChange: (files: IUploadedFile[]) => void;
  onStatusChange: (status: IUploadStatus) => void;
}

interface IFileRow {
  content: string;
  errors: IFileCheckError[];
  filename: string;
  /** 本地校验（大小/类型/编码/空文件）未通过，不参与远程校验 */
  localError?: boolean;
  size: number;
  status: RowStatus;
  uid: string;
}

interface IProps {
  accept?: string;
  configName?: string;
  icon?: string;
  maxSize?: number;
  multiple?: boolean;
  revalidateOnInit?: boolean;
  tip?: string;
  validateKey?: string;
  validator?: FileValidator;
  value?: IUploadedFile[];
}

type RowStatus = 'invalid' | 'valid' | 'validating';

/** 校验请求限流：合并同一批文件选择产生的多次触发 */
const VALIDATE_DEBOUNCE = 100;

/**
 * 多文件上传（基于 bk-upload 的交互层，列表区域自行渲染）
 * - value 为通过校验的文件集合 `{ uid, filename, content }[]`
 * - 本地校验：类型 / 大小 / UTF-8 / 空文件 / 全文重复；
 * - 远程校验：传入 validator 后，对当前完整集合整体校验，旧响应不会覆盖新结果。
 */
@Component({ name: 'MultiFileUpload' })
export default class MultiFileUpload extends tsc<IProps, IEvents> {
  /** 通过校验的文件集合 */
  @Prop({ type: Array, default: () => [] }) value: IUploadedFile[];
  /** 允许的文件后缀，形如 `.yaml,.yml` */
  @Prop({ type: String, default: '' }) accept: string;
  /** 业务文件类别名，用于提示文案；不传则按通用「文件」表述 */
  @Prop({ type: String, default: '' }) configName: string;
  /** 文件图标；默认使用 yaml 图标，传空字符串可退回通用图标 */
  @Prop({ type: String, default: yamlIcon }) icon: string;
  /** 单文件大小上限（MB） */
  @Prop({ type: Number, default: 5 }) maxSize: number;
  /** 是否允许多文件上传；由后端 config_json 的 multiple 字段传入 */
  @Prop({ type: Boolean, default: true }) multiple: boolean;
  /** 首次回填的文件是否需要重新校验（如克隆：回填内容按新建重新校验） */
  @Prop({ type: Boolean, default: false }) revalidateOnInit: boolean;
  /** 上传区域提示文案（完整句）；不传则按 configName 与 multiple 生成整句 */
  @Prop({ type: String, default: '' }) tip: string;
  /** 对完整文件集合做校验；不传则本地校验通过即视为有效 */
  @Prop({ type: Function, default: null }) validator: FileValidator;
  /** 校验所依赖的外部参数标识，变化时对当前集合重新校验 */
  @Prop({ type: String, default: '' }) validateKey: string;

  rows: IFileRow[] = [];
  /** 集合级校验错误 */
  collectionErrors: IFileCheckError[] = [];
  /** 校验请求进行中 */
  requesting = false;
  /** 校验请求本身失败（网络/服务异常） */
  requestFailed = false;

  /** 已排队、尚未发出的校验 */
  validateScheduled = false;
  validateSeq = 0;
  validateTimer: ReturnType<typeof setTimeout> = null;
  /** 最近一次对外输出的集合，用于区分外部回填与自身回写 */
  lastEmitted: IUploadedFile[] = null;
  isDestroyed = false;

  /** 提示文案里的名称短语；未传业务名时统一按「文件」表述 */
  get namePhrases() {
    const file = this.$t('文件') as string;
    const { configName } = this;
    if (!configName) return { error: file, short: file, full: file };
    return {
      error: ` ${configName} ${file}`,
      short: ` ${configName}`,
      full: ` ${this.$t('{name} 配置', { name: configName })}`,
    };
  }

  /** 处于「校验中」状态的文件数 */
  get validatingCount() {
    return this.rows.filter(row => row.status === 'validating').length;
  }

  /** 校验未通过的文件数 */
  get invalidCount() {
    return this.rows.filter(row => row.status === 'invalid').length;
  }

  /** 是否存在尚未完成的校验（等待发起、请求中或有文件在校验中） */
  get isPending() {
    return this.validateScheduled || this.requesting || this.validatingCount > 0;
  }

  /** 上传区域提示：外部 tip 为完整文案；否则按 configName 与 multiple 生成整句 */
  get tipText() {
    if (this.tip) return this.tip;
    if (!this.accept) return '';
    const accept = formatAcceptText(this.accept, this.$t('或') as string);
    if (!this.configName || !this.multiple) return this.$t('仅支持 {accept} 文件', { accept }) as string;
    return this.$t('支持同时上传多个{name}配置，仅支持 {accept} 文件', {
      name: this.configName,
      accept,
    }) as string;
  }

  /**
   * @description value 由外部回填时重建列表并同步状态；自身回写的同一引用不再处理
   * @param value 外部传入的文件集合
   */
  @Watch('value')
  handleValueChange(value: IUploadedFile[]) {
    if (value === this.lastEmitted) return;
    this.initRows(value);
    this.emitState();
  }

  /**
   * @description 校验依赖的外部参数变化时，对当前集合重新校验
   */
  @Watch('validateKey')
  handleValidateKeyChange() {
    if (this.rows.some(row => !row.localError)) this.scheduleValidate();
  }

  created() {
    this.initRows(this.value);
    if (this.revalidateOnInit && this.validator && this.rows.length) {
      for (const row of this.rows) row.status = 'validating';
      this.scheduleValidate();
    }
  }

  beforeDestroy() {
    this.isDestroyed = true;
    clearTimeout(this.validateTimer);
  }

  /**
   * @description 以外部传入的集合重建列表（均视为已通过校验），并清理进行中的校验
   * @param value 外部传入的文件集合
   */
  initRows(value: IUploadedFile[]) {
    clearTimeout(this.validateTimer);
    this.validateScheduled = false;
    this.validateSeq += 1;
    this.requesting = false;
    this.requestFailed = false;
    this.collectionErrors = [];
    this.rows = (Array.isArray(value) ? value : []).map(file => ({
      ...file,
      size: new Blob([file.content || '']).size,
      status: 'valid' as RowStatus,
      errors: [],
    }));
  }

  /**
   * @description 向外输出通过校验的文件集合，以及 pending / invalid 汇总状态
   */
  emitState() {
    const files = this.rows
      .filter(row => row.status === 'valid')
      .map(({ uid, filename, content }) => ({ uid, filename, content }));
    this.lastEmitted = files;
    this.$emit('change', files);
    this.$emit('statusChange', {
      pending: this.isPending ? Math.max(this.validatingCount, 1) : 0,
      invalid: this.invalidCount + this.collectionErrors.length,
    });
  }

  /**
   * @description bk-upload 自定义上传：只做本地读取与校验，不请求上传接口
   * @param fileObj bk-upload 文件对象，origin 为原始 File
   * @param onDone 处理完成后的回调，通知 bk-upload 结束处理
   */
  async handleCustomRequest({ fileObj, onDone }) {
    // 标记完成，避免 bk-upload 在后续批次中重复处理该文件
    fileObj.done = true;
    try {
      await this.processFile(fileObj.origin as File);
    } finally {
      onDone(fileObj);
    }
  }

  /**
   * @description bk-upload 自身拦截的错误（如超出大小限制）：转为一条本地错误行
   * @param fileObj 错误文件对象，含 name / originSize / errorMsg
   */
  handleBkError(fileObj) {
    if (!fileObj?.errorMsg || fileObj.handled) return;
    fileObj.handled = true;
    fileObj.done = true;
    this.rows.push(this.createInvalidRow(fileObj.name, fileObj.originSize, fileObj.errorMsg));
    this.emitState();
  }

  /**
   * @description 构造一条本地校验失败的文件行，localError 标记使其不参与远程校验
   * @param filename 文件名
   * @param size 文件大小（字节）
   * @param message 错误提示文案
   * @returns 失效文件行
   */
  createInvalidRow(filename: string, size: number, message: string): IFileRow {
    return {
      uid: createUuid(),
      filename,
      size,
      content: '',
      status: 'invalid',
      localError: true,
      errors: [{ message }],
    };
  }

  /**
   * @description 读取并校验单个文件：扩展名、UTF-8 编码、空内容、全文重复；通过后加入列表并触发集合校验
   * @param file 待处理的原始文件
   */
  async processFile(file: File) {
    if (this.isDestroyed) return;
    if (!hasAcceptedExtension(file.name, this.accept)) {
      const message = this.$t('仅支持 {accept} 文件，请重新选择{name}。', {
        accept: formatAcceptText(this.accept, this.$t('或') as string),
        name: this.namePhrases.error,
      }) as string;
      this.rows.push(this.createInvalidRow(file.name, file.size, message));
      this.emitState();
      return;
    }
    let content = '';
    try {
      content = await readFileAsUtf8(file);
    } catch (error) {
      const message =
        error?.message === FILE_ENCODING_INVALID
          ? (this.$t('文件不是有效的 UTF-8 编码') as string)
          : (this.$t('读取文件失败') as string);
      this.rows.push(this.createInvalidRow(file.name, file.size, message));
      this.emitState();
      return;
    }
    if (this.isDestroyed) return;
    if (!content.trim()) {
      this.rows.push(this.createInvalidRow(file.name, file.size, this.$t('文件内容为空') as string));
      this.emitState();
      return;
    }
    const duplicated = this.rows.find(row => !row.localError && row.content === content);
    if (duplicated) {
      this.$bkMessage({
        theme: 'warning',
        message: this.$t('文件「{name}」与「{other}」内容重复，已忽略', {
          name: file.name,
          other: duplicated.filename,
        }) as string,
        ellipsisLine: 0,
      });
      return;
    }
    this.rows.push({
      uid: createUuid(),
      filename: file.name,
      size: file.size,
      content,
      status: this.validator ? 'validating' : 'valid',
      errors: [],
    });
    this.emitState();
    this.scheduleValidate();
  }

  /**
   * @description 合并同一批文件选择产生的多次校验触发，延时发起集合校验并作废旧请求
   */
  scheduleValidate() {
    if (!this.validator) return;
    clearTimeout(this.validateTimer);
    // 作废进行中的旧请求，由新一轮完整集合校验接管
    this.validateSeq += 1;
    this.validateScheduled = true;
    this.validateTimer = setTimeout(this.runValidate, VALIDATE_DEBOUNCE);
    this.emitState();
  }

  /**
   * @description 对当前完整集合发起校验；通过版本号丢弃过期响应
   */
  async runValidate() {
    const candidates = this.rows.filter(row => !row.localError);
    this.validateScheduled = false;
    this.validateSeq += 1;
    const seq = this.validateSeq;
    this.requestFailed = false;
    if (!candidates.length) {
      this.requesting = false;
      this.collectionErrors = [];
      this.emitState();
      return;
    }
    this.requesting = true;
    // 重试时让上次失败的文件回到校验中状态
    for (const row of candidates) {
      if (row.status === 'invalid' && row.errors.some(item => item.code === 'VALIDATE_REQUEST_FAILED')) {
        row.status = 'validating';
        row.errors = [];
      }
    }
    try {
      const result = await this.validator(candidates.map(({ uid, filename, content }) => ({ uid, filename, content })));
      if (this.isDestroyed || seq !== this.validateSeq) return;
      this.applyResult(result, candidates);
    } catch (error) {
      if (this.isDestroyed || seq !== this.validateSeq) return;
      const parsed = parseApiError(error);
      if (hasBusinessErrors(parsed)) {
        // 接口以失败形式返回的业务错误（如源版本冲突）：按标识回填到集合/对应文件，不显示为请求失败
        this.applyResult({ valid: false, errors: parsed.errors, files: parsed.files }, candidates);
      } else {
        this.requestFailed = true;
        for (const row of candidates) {
          if (row.status === 'validating') {
            row.status = 'invalid';
            row.errors = [{ code: 'VALIDATE_REQUEST_FAILED', message: this.$t('校验请求失败') as string }];
          }
        }
      }
    }
    this.requesting = false;
    this.emitState();
  }

  /**
   * @description 将校验结果写回候选文件行并更新集合级错误；响应中缺失的文件视为未通过
   * @param result 整体校验结果
   * @param candidates 本轮参与校验的文件行
   */
  applyResult(result: IValidateResult, candidates: IFileRow[]) {
    const resultMap = new Map((result?.files || []).map(item => [item.uid, item]));
    for (const row of candidates) {
      const item = resultMap.get(row.uid);
      if (!item) {
        row.status = 'invalid';
        row.errors = [{ message: this.$t('校验未通过') as string }];
        continue;
      }
      row.status = item.valid ? 'valid' : 'invalid';
      row.errors = item.errors || [];
    }
    this.collectionErrors = result?.errors || [];
  }

  /**
   * @description 删除指定文件行并同步状态；无待校验文件时清理进行中的请求与集合错误
   * @param uid 文件行标识
   */
  handleDelete(uid: string) {
    const target = this.rows.find(row => row.uid === uid);
    if (!target) return;
    this.rows = this.rows.filter(row => row.uid !== uid);
    this.emitState();
    if (target.localError) return;
    if (this.rows.some(row => !row.localError)) {
      this.scheduleValidate();
    } else {
      // 没有需要校验的文件了，作废进行中的请求并清理集合错误
      clearTimeout(this.validateTimer);
      this.validateSeq += 1;
      this.requesting = false;
      this.requestFailed = false;
      this.collectionErrors = [];
      this.emitState();
    }
  }

  /**
   * @description 顶部汇总提示：校验中 / 全部通过 / 存在失败
   * @returns 汇总提示节点
   */
  renderSummary() {
    const total = this.rows.length;
    let type: 'error' | 'info' | 'success' = 'error';
    let content: JSX.Element | string = '';
    if (this.isPending) {
      type = 'info';
      content = (
        <i18n path='正在上传并逐个校验 {0} 个{1}…'>
          <span class='is-strong'>{this.validatingCount || total}</span>
          <span>{this.namePhrases.short}</span>
        </i18n>
      );
    } else if (this.requestFailed) {
      content = this.$t('校验请求失败') as string;
    } else if (this.invalidCount) {
      content = (
        <i18n path='已上传 {0} 个{1}，{2} 个通过，{3} 个未通过需要处理'>
          <span class='is-strong'>{total}</span>
          <span>{this.namePhrases.full}</span>
          <span class='is-strong'>{total - this.invalidCount}</span>
          <span class='is-strong is-danger'>{this.invalidCount}</span>
        </i18n>
      );
    } else if (this.collectionErrors.length) {
      content = this.$t('文件集合校验未通过') as string;
    } else {
      type = 'success';
      content = (
        <i18n path='已上传 {0} 个{1}，全部校验通过'>
          <span class='is-strong'>{total}</span>
          <span>{this.namePhrases.full}</span>
        </i18n>
      );
    }
    return (
      <div class={['file-summary', `is-${type}`]}>
        <i
          class={[
            'bk-icon',
            'file-summary-icon',
            {
              'icon-info-circle': type === 'info',
              'icon-check-circle': type === 'success',
              'icon-exclamation-circle': type === 'error',
            },
          ]}
        />
        <span class='file-summary-text'>{content}</span>
        {this.requestFailed && !this.requesting && (
          <bk-button
            theme='primary'
            text
            onClick={this.runValidate}
          >
            {this.$t('重试')}
          </bk-button>
        )}
      </div>
    );
  }

  /**
   * @description 渲染单个文件行：图标、名称、大小、校验状态、错误提示与删除按钮
   * @param row 文件行数据
   * @returns 文件行节点
   */
  renderRow(row: IFileRow) {
    const isValidating = row.status === 'validating';
    const isValid = row.status === 'valid';
    return (
      <div
        key={row.uid}
        class={['file-item', `is-${row.status}`]}
      >
        {isValid || isValidating ? (
          this.icon ? (
            <img
              class='file-icon'
              alt=''
              src={this.icon}
            />
          ) : (
            <i class='icon-monitor icon-mc-file file-icon' />
          )
        ) : (
          <i class='bk-icon icon-exclamation-circle-shape file-icon is-error' />
        )}
        <div class='file-info'>
          <div class='file-info-head'>
            <span
              class='file-name'
              title={row.filename}
            >
              {row.filename}
            </span>
            {isValidating && <span class='file-size'>{formatFileSize(row.size)}</span>}
          </div>
          {isValidating && (
            <div class='file-progress'>
              <div class='file-progress-bar' />
            </div>
          )}
          {isValid && (
            <span class='file-tip is-success'>
              <i class='icon-monitor icon-mc-check-small file-tip-icon' />
              {this.$t('上传成功，并校验通过')}
            </span>
          )}
          {row.status === 'invalid' &&
            row.errors.map((error, index) => (
              <span
                key={index}
                class='file-tip is-error'
              >
                {error.message}
              </span>
            ))}
        </div>
        {isValid && <span class='file-size is-hover-hide'>{formatFileSize(row.size)}</span>}
        {!isValidating && (
          <i
            class={['bk-icon', 'icon-delete', 'file-delete', { 'is-hover-show': isValid }]}
            onClick={() => this.handleDelete(row.uid)}
          />
        )}
      </div>
    );
  }

  render() {
    return (
      <div class='multi-file-upload'>
        <bk-upload
          class='multi-file-upload-control'
          accept={this.accept}
          custom-request={this.handleCustomRequest}
          multiple={this.multiple}
          on={{ 'on-error': this.handleBkError }}
          size={this.maxSize}
          theme='draggable'
          tip={this.tipText}
        />
        {this.rows.length > 0 && (
          <div class='file-list'>
            {this.renderSummary()}
            {this.collectionErrors.length > 0 && (
              <ul class='collection-errors'>
                {this.collectionErrors.map((error, index) => (
                  <li
                    key={index}
                    class='collection-error'
                  >
                    {error.message}
                  </li>
                ))}
              </ul>
            )}
            {this.rows.map(row => this.renderRow(row))}
          </div>
        )}
      </div>
    );
  }
}
