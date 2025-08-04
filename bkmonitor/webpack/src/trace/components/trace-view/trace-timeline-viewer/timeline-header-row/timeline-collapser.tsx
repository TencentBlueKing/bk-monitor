/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, defineComponent } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import AngleDoubleDownIcon from '../../icons/angle-double-down.svg';
import AngleDoubleRightIcon from '../../icons/angle-double-right.svg';
import AngleDownIcon from '../../icons/angle-down.svg';
import AngleRightIcon from '../../icons/angle-right.svg';

import './timeline-collapser.scss';

const CollapserProps = {
  onCollapseAll: Function as PropType<() => void>,
  onCollapseOne: Function as PropType<() => void>,
  onExpandOne: Function as PropType<() => void>,
  onExpandAll: Function as PropType<() => void>,
};

export default defineComponent({
  name: 'TimelineCollapser',
  props: CollapserProps,
  setup(props, { emit }) {
    const { t } = useI18n();

    const { onCollapseAll, onCollapseOne, onExpandOne, onExpandAll } = props;

    return {
      t,
    };
  },
  render() {
    const { onCollapseAll, onCollapseOne, onExpandOne, onExpandAll } = this.$props;

    return (
      <div class='timeline-collapser'>
        <Popover
          content={this.t('展开 1 层')}
          placement='top'
          popoverDelay={[500, 0]}
          theme='dark'
        >
          <div
            class='collapser-btn'
            onClick={onExpandOne}
          >
            <img
              alt='down'
              src={AngleDownIcon}
            />
          </div>
        </Popover>
        <Popover
          content={this.t('收起 1 层')}
          placement='top'
          popoverDelay={[500, 0]}
          theme='dark'
        >
          <div
            class='collapser-btn'
            onClick={onCollapseOne}
          >
            <img
              alt='right'
              src={AngleRightIcon}
            />
          </div>
        </Popover>
        <Popover
          content={this.t('全部展开')}
          placement='top'
          popoverDelay={[500, 0]}
          theme='dark'
        >
          <div
            class='collapser-btn'
            onClick={onExpandAll}
          >
            <img
              alt='double-down'
              src={AngleDoubleDownIcon}
            />
          </div>
        </Popover>
        <Popover
          content={this.t('全部收起')}
          placement='top'
          popoverDelay={[500, 0]}
          theme='dark'
        >
          <div
            class='collapser-btn'
            onClick={onCollapseAll}
          >
            <img
              alt='double-right'
              src={AngleDoubleRightIcon}
            />
          </div>
        </Popover>
      </div>
    );
  },
});
