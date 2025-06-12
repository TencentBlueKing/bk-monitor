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
import { type Ref, computed, defineComponent, ref, nextTick, onMounted, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { Collapse } from 'bkui-vue';

import './trouble-shooting.scss';

export default defineComponent({
  name: 'TroubleShooting',
  props: {
    steps: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['chooseOperation', 'changeTab'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const activeIndex = shallowRef([0, 1]);
    const dimensional = shallowRef([
      {
        name: '异常维度（组合）1',
        content: '拥有支撑数百款腾讯业务的经验沉淀，兼容各种复杂的系统架构，生于运维 · 精于运维',
      },
      {
        name: '异常维度（组合）2',
        content:
          '从配置管理，到作业执行、任务调度和监控自愈，再通过运维大数据分析辅助运营决策，全方位覆盖业务运营的全周期保障管理。',
      },
      {
        name: '异常维度（组合）3',
        content: '开放的PaaS，具备强大的开发框架和调度引擎，以及完整的运维开发培训体系，助力运维快速转型升级。',
      },
    ]);
    const renderDisposal = () => (
      <div>
        基于历史故障知识库的处置建议
        <div>该故障内您共有 3 个未恢复告警待处理。分别的建议处置建议：</div>
        <div>1. XXXXXXXXXXXXXXXXXX 前往处理 </div>
        <div>2. XXXXXXXXXXXXXXXXXX </div>
        <div>3. XXXXXXXXXXXXXXXXXX </div>
      </div>
    );
    const renderDimensional = () => (
      <div>
        <span>故障关联的告警，统计出最异常的维度（组合）：</span>
        <Collapse
          class='dimensional-collapse'
          // v-model={this.activeIndex}
          // v-slots={{
          //   default: item => titleSlot(item),
          //   content: item => contentSlot(item),
          // }}
          list={dimensional.value}
        />
      </div>
    );
    const list = shallowRef([
      {
        name: t('处置建议'),
        icon: 'icon-chulijilu',
        render: renderDisposal,
      },
      {
        name: t('告警异常维度分析'),
        icon: 'icon-dimension-line',
        render: renderDimensional,
      },
    ]);

    return {
      t,
      activeIndex,
      list,
    };
  },
  render() {
    const titleSlot = item => (
      <span class='collapse-item-title'>
        <i class={`icon-monitor ${item.icon} title-icon-circle`} />
        <span class='field-name'>{item.name}</span>
      </span>
    );
    const contentSlot = item => item.render();
    return (
      <div class='failure-trouble-shooting'>
        <div class='trouble-shooting-header'>
          {this.t('诊断分析')}
          <i class='icon-monitor icon-zhankai2 icon-btn' />
        </div>
        <div class='trouble-shooting-main'>
          <div class='ai-card'>
            <div class='ai-card-title'>
              <span class='ai-card-title-icon' />
              {this.t('故障总结')}
            </div>
            <div class='ai-card-main'>
              根因节点和影响范围（结合图谱的实体回答：服务、模块），触发的告警情况、影响面积分析文本占位文本占位。查看详情
            </div>
          </div>
          <Collapse
            class='failure-collapse'
            v-model={this.activeIndex}
            v-slots={{
              default: item => titleSlot(item),
              content: item => contentSlot(item),
            }}
            header-icon='right-shape'
            list={this.list}
          />
        </div>
      </div>
    );
  },
});
