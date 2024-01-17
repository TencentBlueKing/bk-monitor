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
    class="log-wrapper"
    @mouseover="handleMouseOver"
    @mouseleave="showMask = false"
    @click="handleOpenUpload"
    :class="{ solid: file.show }"
  >
    <div
      class="mask"
      v-show="showMask"
    >{{ file.base64 ? $t('点击更换') : $t('点击上传') }}</div>
    <div
      v-if="!file.show"
      class="log"
    ><span class="text">LOGO</span></div>
    <img
      class="log-img"
      v-if="file.show && file.base64.length > 1"
      :src="file.base64"
      alt="logo"
    >
    <span
      class="word-logo"
      v-if="file.show && file.base64.length === 1"
    >{{ file.base64.toUpperCase() }}</span>
    <input
      ref="uploadImage"
      accept=".png,.jpg,.jpeg"
      type="file"
      style="display: none"
      @change="getImageFile"
    >
  </div>
</template>
<script>
export default {
  name: 'Logo',
  props: {
    logo: {
      type: String
    }
  },
  data() {
    return {
      file: {
        base64: '',
        show: false
      },
      showMask: false
    };
  },
  watch: {
    logo(val) {
      this.file.base64 = val;
      this.file.show = Boolean(val);
    }
  },
  methods: {
    handleMouseOver() {
      this.showMask = true;
    },
    handleOpenUpload() {
      this.$refs.uploadImage.click();
    },
    getImageFile(e) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (e) => {
        const { result } = e.target;
        this.graphLogo(result);
      };
      reader.readAsDataURL(file);
      e.target.value = '';
    },
    graphLogo(result) {
      const img = new Image();
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      img.onload = () => {
        const originWidth = img.width;
        const originHeight = img.height;
        let renderWidth = 78;
        let renderHeight = 78;
        if (originWidth < renderWidth) {
          renderWidth = originWidth;
        }
        if (originHeight < renderHeight) {
          renderHeight = originHeight;
        }
        canvas.width = renderWidth;
        canvas.height = renderHeight;
        context.clearRect(0, 0, renderWidth, renderHeight);
        context.drawImage(img, 0, 0, renderWidth, renderWidth);
        this.file.base64 = canvas.toDataURL();
        this.file.show = true;
        this.$emit('update:logo', this.file.base64);
      };
      img.src = result;
    }
  }
};
</script>
<style lang="scss" scoped>
@import '../../../../theme/index';

.log-wrapper {
  position: relative;
  z-index: 2;
  width: 84px;
  height: 84px;
  background-color: #fafbfd;
  border: 1px dashed #dcdee5;
  border-radius: 2px;

  @include content-center;

  &.solid {
    border-style: solid;
  }

  .mask {
    position: absolute;
    top: -1px;
    left: -1px;
    width: 84px;
    height: 84px;
    font-size: 12px;
    color: #fff;
    background-color: #63656e;
    opacity: .6;

    @include content-center;
  }

  &:hover {
    cursor: pointer;

    .text {
      display: none;
    }
  }

  .log {
    width: 78px;
    height: 78px;
    font-size: 12px;
    line-height: 78px;
    color: #979ba5;
    text-align: center;
    background-color: #fff;
    border: 1px dashed #dcdee5;
    border-radius: 50%;
  }

  .log-img {
    width: 78px;
    height: 78px;
  }

  .word-logo {
    width: 78px;
    height: 78px;
    font-size: 36px;
    color: #fff;
    cursor: pointer;
    background-color: #63656e;

    @include content-center;
  }
}
</style>
