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
    class="square"
    @click.stop="clickHandle"
  >
    <div :class="`square-${status}`">
      <div class="front" />
      <div class="bottom" />
      <div class="back" />
      <div class="top" />
      <div class="left" />
      <div class="right" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'Square',
  props: {
    status: {
      type: String,
      default: 'unset',
    },
  },
  methods: {
    clickHandle() {
      this.$emit('click', this.status);
    },
  },
};
</script>

<style scoped lang="scss">
@import '../../common/mixins';

@mixin square(
  $frontColor: #fcfffc,
  $topColor: #fcfffc,
  $leftColor: #fcfffc,
  $backColor: #fcfffc,
  $rightColor: #fcfffc,
  $bottomColor: #fcfffc
) {
  position: relative;
  width: 150px;
  height: 35px;
  box-sizing: border-box;
  transform-style: preserve-3d;
  transform: rotateX(-20deg) rotateY(45deg) rotateZ(0deg);
  margin: 0px auto;
  div {
    position: absolute;
  }
  .front {
    width: 150px;
    height: 35px;
    transform: translateZ(75px);
    background: $frontColor;
  }
  .bottom {
    width: 150px;
    height: 150px;
    transform: rotateX(270deg) translateZ(-40px);
    background: $bottomColor;
  }
  .back {
    width: 150px;
    height: 35px;
    transform: translateZ(-75px);
    background: $backColor;
  }
  .top {
    width: 150px;
    height: 150px;
    transform: rotateX(90deg) translateZ(75px);
    background: $topColor;
  }
  .left {
    width: 150px;
    height: 35px;
    transform: rotateY(270deg) translateZ(75px);
    background: $leftColor;
  }
  .right {
    width: 150px;
    height: 35px;
    transform: rotateY(90deg) translateZ(75px);
    background: $rightColor;
  }
}

.square {
  &-serious {
    @include square(#eb8995, #ffdddd, #de6573);
  }
  &-slight {
    @include square(#ffe7a3, #fff2cc, #febf81);
  }
  &-normal {
    @include square(#bce4b7, #dcffe2, #85cfb7);
  }
  &-unset {
    @include square(#fcfffc, #ffffff, #f8fff9);
    .front {
      @include border-dashed-1px(#c4c6cc);
    }
    .left {
      border-right: 0;

      /* stylelint-disable-next-line scss/at-extend-no-missing-placeholder */
      @extend .front;
    }
    .top {
      border-left: 0;
      border-bottom: 0;

      /* stylelint-disable-next-line scss/at-extend-no-missing-placeholder */
      @extend .front;
    }
  }
}
</style>
