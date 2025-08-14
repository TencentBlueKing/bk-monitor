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
import { type PropType, defineComponent, ref } from 'vue';

import { bkTooltips, Popover } from 'bkui-vue';

import ViewParam from './view-param';

import './history-dialog.scss';

export default defineComponent({
  name: 'HistoryDialog',
  directives: {
    bkTooltips,
  },
  props: {
    showCallback: {
      type: Function as PropType<any | Promise<void>>,
      default: () => null,
    },
    list: {
      type: Array,
      default: () => [],
    },
    title: {
      type: String,
      default: window.i18n.t('变更记录'),
    },
  },
  setup(props) {
    const visible = ref(false);
    function handleHistoryClick() {
      if (props.showCallback) {
        const res = props.showCallback();
        if (res instanceof Promise && res.then) {
          res.then(() => {
            visible.value = true;
          });
        } else {
          visible.value = true;
        }
      } else {
        visible.value = true;
      }
    }

    return {
      handleHistoryClick,
      visible,
    };
  },
  render() {
    return (
      <Popover
        content={this.title}
        placement={'top'}
        popoverDelay={[300, 0]}
      >
        <div
          class='history-container'
          onClick={this.handleHistoryClick}
        >
          <span class='icon-monitor icon-lishijilu icon' />
          <ViewParam
            list={this.list}
            title={this.title}
            visible={this.visible}
            onChange={val => (this.visible = val)}
          >
            {this.$slots.default?.()}
          </ViewParam>
        </div>
      </Popover>
    );
  },
});
