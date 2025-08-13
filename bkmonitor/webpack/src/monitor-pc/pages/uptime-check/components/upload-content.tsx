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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './upload-content.scss';

interface IUploadContentEvents {
  onChangeImg?: string;
}
interface IUploadContentProps {
  imgSrc?: string;
}

@Component({
  name: 'UploadContent',
})
export default class UploadContent extends tsc<IUploadContentProps, IUploadContentEvents> {
  @Prop({ type: String, default: '' }) imgSrc: string;

  curImg = '';

  @Watch('imgSrc', { immediate: true })
  handleImgSrc(v: string) {
    this.curImg = v || '';
  }

  handleImgFileChange(e: any) {
    const eventFile = e;
    const file = e.target.files[0];
    const fileReader = new FileReader();
    fileReader.onloadend = (event: any) => {
      this.curImg = event.target.result;
      eventFile.target.value = '';
      this.handleImgChange();
    };
    fileReader.readAsDataURL(file);
  }

  // 删除图片
  handleDeleteImg(e: Event) {
    e.preventDefault();
    e.stopPropagation();
    this.curImg = '';
    this.handleImgChange();
  }
  @Emit('changeImg')
  handleImgChange() {
    return this.curImg;
  }

  render() {
    return (
      <div class='uptime-check-upload-content'>
        <div
          style={{ backgroundImage: this.curImg ? `url(${this.curImg})` : 'none' }}
          class='upload-content-img'
        >
          {!this.curImg && <span class='icon-monitor icon-upload-cloud' />}
          <div class='mask'>{this.curImg ? this.$t('点击更换') : this.$t('点击上传')}</div>
          <i
            class='bk-icon icon-close'
            onClick={this.handleDeleteImg}
          />
          <input
            class='file-input'
            accept='image/png'
            type='file'
            onChange={this.handleImgFileChange}
          />
        </div>
      </div>
    );
  }
}
