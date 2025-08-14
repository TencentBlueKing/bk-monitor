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
import type { CreateElement } from 'vue';

import { Component, Prop, Vue } from 'vue-property-decorator';

@Component({ name: 'unresolve-list' })
export default class UnresolveList extends Vue {
  @Prop({ default: () => [], type: Array }) readonly list: any[];

  private statusMap = {
    1: window.i18n.t('致命'),
    2: window.i18n.t('预警'),
    3: window.i18n.t('提醒'),
  };

  render(h: CreateElement) {
    return h(
      'ul',
      {
        class: 'unresolve-list',
      },
      this.list.map(item => {
        const desc = `${this.statusMap[item.level]}(${item.count || 0})`;
        const status = `item-${item.level}`;
        return h(
          'li',
          {
            class: 'unresolve-list-item',
          },
          [
            h('span', {
              class: {
                'item-status': true,
                [status]: true,
              },
            }),
            h(
              'span',
              {
                class: 'item-name',
              },
              desc
            ),
          ]
        );
      })
    );
  }
}
</script>

<style scoped lang="scss">
@import '../../home/common/mixins';

$colors: $deadlyAlarmColor $warningAlarmColor $remindAlarmColor;

.unresolve-list {
  padding: 0;
  margin: 0;

  &-item {
    display: flex;
    align-items: center;
    width: 120px;
    padding: 10px 6px 10px;
    color: #fff;
    @for $i from 1 through length($colors) {
      .item-#{$i} {
        /* stylelint-disable-next-line function-no-unknown */
        background: nth($colors, $i);
      }
    }

    .item-status {
      flex: 0 0 14px;
      height: 14px;
      margin-right: 8px;
      border-radius: 50%;
    }
  }
}
</style>
