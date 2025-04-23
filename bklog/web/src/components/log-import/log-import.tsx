/*
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
 */

import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './log-import.scss';

interface LogExportProps {
  returnFileInfo: boolean;
  accept: string;
  base64: boolean;
  disabled: boolean;
}

interface LogExportEvents {
  onChange: (data: any) => void;
}

@Component
export default class LogExport extends tsc<LogExportProps, LogExportEvents> {
  @Ref('fileInput') readonly fileInputRef: HTMLElement;

  /** 是否需要文件详细信息,false 则只返回读取内容 */
  @Prop({ default: false, type: Boolean }) returnFileInfo: boolean;
  /** 文件类型 */
  @Prop({ default: '.json', type: String }) accept: string;
  /** 文件读取后是否生成的base64,false 则生成文本信息 */
  @Prop({ default: false, type: Boolean }) base64: boolean;
  /** 是否禁止上传功能 */
  @Prop({ default: false, type: Boolean }) disabled: boolean;

  @Emit('change')
  emitFile(data) {
    return data;
  }

  /**
   * @description 点击触发打开 系统文件选择菜单
   *
   */
  handleClick() {
    !this.disabled && this.fileInputRef.click();
  }

  /**
   * @description 选择文件后触发回调，读取文件内容
   * @param {Event} event
   *
   */
  handleInput(event: { target: { files: any[]; value: '' } }) {
    const [file] = Array.from(event.target.files);
    const fileName = file.name;
    let contents = {};
    new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = (e: { target: any }) => {
        try {
          if (this.returnFileInfo) {
            contents = {
              name: fileName,
              fileStr: e.target.result,
              size: file.size,
            };
          } else {
            contents = e.target.result;
          }
          resolve(contents);
          event.target.value = '';
        } catch (e) {
          resolve({});
        }
      };
      if (this.base64) {
        reader.readAsDataURL(file);
      } else {
        reader.readAsText(file, 'UTF-8');
      }
    }).then(() => {
      this.emitFile(contents);
    });
  }

  render() {
    return (
      <div
        class='log-import'
        onClick={this.handleClick}
      >
        {this.$slots.default || this.$t('导入')}
        <input
          ref='fileInput'
          accept={this.accept}
          type='file'
          // @ts-ignore
          onInput={this.handleInput}
        />
      </div>
    );
  }
}
