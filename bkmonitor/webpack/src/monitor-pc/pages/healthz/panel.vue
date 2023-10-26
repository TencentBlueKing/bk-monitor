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
  <el-card
    :shadow="shadow"
    :body-style="_bodyStyle"
  >
    <div
      slot="header"
      class="cf"
      :style="{ cursor: hiddenAble ? 'pointer' : 'normal' }"
      @click="trigger"
    >
      <slot name="header" />
      <i
        v-if="hiddenAble"
        style="float: right; margin-top: 3px"
        :class="{ 'el-icon-arrow-down': true, 'rotate-after': isHidden, 'rotate-before': !isHidden }"
      />
    </div>
    <!-- <el-collapse-transition> -->
    <div
      v-show="!isHidden"
      style="padding: 20px"
    >
      <slot />
    </div>
    <!-- </el-collapse-transition> -->
  </el-card>
</template>

<script>
import { Card } from 'element-ui';

export default {
  name: 'MoPanel',
  components: {
    ElCard: Card
  },
  props: {
    shadow: {
      type: String,
      default: 'always'
    },
    bodyStyle: {
      type: Object,
      default() {
        return {};
      }
    },
    hiddenAble: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      isHidden: false
    };
  },
  computed: {
    _bodyStyle() {
      const body = { display: this.isHidden ? 'none' : 'block' };
      Object.keys(this.bodyStyle).forEach((key) => {
        body[key] = this.bodyStyle[key];
      });
      return body;
    }
  },
  methods: {
    trigger() {
      if (this.hiddenAble) {
        this.isHidden = !this.isHidden;
      }
    }
  }
};
</script>

<style lang="scss">
$rotateTime: .3s ease-out;

.el-card__header {
  padding: 0;
}

.el-card__body {
  padding: 0;
}

.cf {
  padding: 12px 20px;
}

.cf:before,
.cf:after {
  display: table;
  content: '';
}

.cf:after {
  clear: both;
}

.rotate-after {
  transition: transform $rotateTime;
  transform: rotate(180deg);
  transform-origin: center center;
}

.rotate-before {
  transition: transform $rotateTime;
  transform: rotate(0deg);
  transform-origin: center center;
}
</style>
