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
<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

@Component({ name: 'MonitorSkeleton' })
export default class MonitorSkeleton extends Vue {
  // 是否显示骨架屏
  @Prop({ default: true }) loading: boolean;
  // 是否启用动画
  @Prop({ default: true }) animate: boolean;
  // 内容区行数 也可设置宽度的数组
  @Prop({ default: 4 }) rows: number | number[] | string[];
  // 是否需要titlie
  @Prop({ default: true }) needTitle: boolean;
  // 是否需要header
  @Prop({ default: false }) needHeader: boolean;

  header() {
    if (this.$slots.header) {
      return this.$slots.header;
    }
  }
  content(h) {
    if (this.$slots.content) {
      return this.$slots.content;
    }
    return h(
      'div',
      {
        class: {
          'monitor-skeleton-content': true,
        },
      },
      [this.title(h), this.rowList(h)]
    );
  }
  title(h) {
    if (this.$slots.title) {
      return this.$slots.title;
    }
    return h('h3', {
      class: {
        'content-title': true,
        'title-animate': this.animate,
      },
      style: {
        width: '38%',
      },
    });
  }
  rowList(h) {
    let itemList = [];
    if (Array.isArray(this.rows)) {
      itemList = this.rows.map(width => this.row(h, width));
    } else {
      for (let i = 0; i < this.rows; i++) {
        itemList.push(this.row(h, '100%'));
      }
    }
    return h(
      'ul',
      {
        class: {
          'content-list': true,
        },
      },
      itemList
    );
  }
  row(h, width) {
    return h('li', {
      class: {
        'content-list-item': true,
        'item-animate': this.animate,
      },
      style: {
        width,
      },
    });
  }
  render(h) {
    if (!this.loading) {
      return this.$slots.default;
    }
    return h(
      'div',
      {
        class: {
          'monitor-skeleton': true,
        },
      },
      [this.header(h), this.content(h)]
    );
  }
}
</script>
<style lang="scss" scoped>
@mixin skeleton-row {
  flex: 0 0 16px;
  width: 100%;
  height: 16px;
  background: #f2f2f2;
}
@mixin skeleton-row-animate {
  background: linear-gradient(90deg, #f2f2f2 25%, #e6e6e6 37%, #f2f2f2 63%);
  background-size: 400% 100%;
  animation: monitor-skeleton-animate 1.4s ease infinite;
}

.monitor-skeleton {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;

  @keyframes monitor-skeleton-animate {
    0% {
      background-position: 100% 50%;
    }

    to {
      background-position: 0 50%;
    }
  }

  &-content {
    display: flex;
    flex: 1;
    flex-direction: column;

    .content-title {
      width: 38%;
      padding: 0;
      margin: 16px 0 0 0;

      @include skeleton-row();

      &.title-animate {
        @include skeleton-row-animate;
      }
    }

    .content-list {
      display: flex;
      flex: 1;
      flex-direction: column;
      padding: 0;
      margin: 24px 0 0 0;
      list-style: none;

      & > li + li {
        margin-top: 16px;
      }

      &-item {
        flex: 1;

        @include skeleton-row();

        &.item-animate {
          @include skeleton-row-animate;
        }
      }
    }
  }
}
</style>
