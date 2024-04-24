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
  <div class="square-svg">
    <div class="square-container">
      <div
        v-for="(item, index) in squares"
        :key="index"
        :class="['item', `item-${index}`, { active: index === selected }]"
      >
        <square
          :status="item.status"
          @click="squareClickHandle(index, item)"
        />
      </div>
    </div>
    <div
      v-show="!isAllNormal"
      class="svg-container"
    >
      <svg style="display: none">
        <symbol
          id="commonSvg"
          :viewBox="svgMap[curSquare.name].viewBox"
        >
          <path
            :d="svgMap[curSquare.name].d"
            :stroke="colorMap[curSquare.status]"
            stroke-dasharray="3"
            stroke-width="1.5px"
            fill="none"
          />
        </symbol>
      </svg>
      <svg
        v-show="selected !== -1"
        :class="`svg-container-${curSquare.name}`"
      >
        <use xlink:href="#commonSvg" />
      </svg>
    </div>
  </div>
</template>

<script>
import Square from '../square/square';

export default {
  name: 'BusinessAlarmSquare',
  components: { Square },
  props: {
    squares: {
      type: Array,
      default() {
        return [];
      },
    },
    status: {
      type: String,
      default: 'serious',
    },
    selectedIndex: {
      type: Number,
      default: 0,
    },
    isAllNormal: Boolean,
  },
  data() {
    return {
      selected: this.selectedIndex,
      curSquare: this.squares[this.selectedIndex],
      svgMap: {
        uptimecheck: {
          d: 'M0,91.5L0,91.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
          viewBox: '0 0 55 92',
        },
        process: {
          d: 'M0,185.5L0,185.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
          viewBox: '0 0 55 186',
        },
        os: {
          d: 'M0,232.5L0,232.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
          viewBox: '0 0 55 233',
        },
        service: {
          d: 'M0,138.5L0,138.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
          viewBox: '0 0 55 139',
        },
      },
      colorMap: {
        serious: '#DE6573',
        slight: '#FEBF81',
        unset: '#C4C6CC',
        normal: '#85CFB7',
      },
    };
  },
  methods: {
    squareClickHandle(index, { status, name }) {
      this.selected = index;
      this.curSquare = { status, name };
      this.$emit('update:selectedIndex', index);
      if (this.isAllNormal) {
        this.$emit('update:isAllNormal', false);
      }
    },
  },
};
</script>

<style scoped lang="scss">
@import '../../common/mixins';

$length: 3 !default;
$const: 47 !default;

.square-svg {
  .square-container {
    position: relative;

    @for $i from 0 through $length {
      .item-#{$i} {
        top: -20px + $i * $const;
        z-index: 6 - $i;
      }
    }
    .item {
      position: absolute;
      transition: transform 0.3s ease-in-out;
      &:hover {
        transform: translateX(25px);
        cursor: pointer;
      }
    }
    .active {
      transform: translateX(25px);
    }
  }
  .svg-container {
    &-uptimecheck {
      @include common-svg();
    }
    &-service {
      @include common-svg(139px);
    }
    &-process {
      @include common-svg(186px);
    }
    &-os {
      @include common-svg(233px);
    }
  }
}
</style>
