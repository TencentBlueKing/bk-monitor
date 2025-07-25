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
  <section class="common-normal">
    <div class="title">
      {{ normal.title }}
    </div>
    <div class="content">
      <div v-if="alarm.name === 'uptimecheck'">
        <div
          v-for="item in alarm.notice_task"
          :key="item.task_id"
          class="content-item"
        >
          <a
            class="guide"
            @click="gotoUpcheckTimePage('task', item.task_id)"
          >
            {{ $t('立即查看') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ item.task_name }} {{ $t('当前服务可用率') }} <span class="item-warning">{{ item.available }}</span
            >，{{ $t('建议您关注') }}
          </div>
        </div>
        <div
          v-for="item in alarm.warning_task"
          :key="item.task_id"
          class="content-item"
        >
          <a
            class="guide"
            @click="gotoUpcheckTimePage('task', item.task_id)"
          >
            {{ $t('立即查看') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ item.task_name }} {{ $t('当前可用率仅') }} <span class="item-warning">{{ item.available }}</span
            >，{{ $t('服务质量较差，请及时处理') }}
          </div>
        </div>
        <div
          v-if="alarm.single_supplier"
          class="content-item"
        >
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{
              $t(
                '检测到当前仅配置了1个运营商节点，为了更全面的反应不同网络环境用户的访问质量，建议您接入更多其他类型的网络运营商节点，覆盖更全面。'
              )
            }}
            <a
              class="into"
              @click="gotoUpcheckTimePage('node')"
            >
              {{ $t('立即接入') }}
            </a>
            {{ $t('（点击跳转到拨测节点页面）') }}
          </div>
        </div>
      </div>
      <div v-else-if="alarm.name === 'service'">
        <div
          v-if="alarm.should_config_strategy"
          class="content-item"
        >
          <a
            class="guide"
            @click="gotoStrategy"
          >
            {{ $t('前往添加') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{
              $t(
                '检测到告警策略 未配置监控目标，创建好策略后别忘了添加目标才可生效喔。自研的中间件也能接入蓝鲸监控吗？'
              )
            }}
          </div>
        </div>
        <div class="content-item">
          <a
            class="guide"
            @click="handleGotoLink('scriptCollect')"
          >
            {{ $t('马上了解') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('如何使用脚本进行服务监控？') }}
          </div>
        </div>
        <div class="content-item">
          <a
            class="guide"
            @click="handleGotoLink('multiInstanceMonitor')"
          >
            {{ $t('马上了解') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('如何实现多实例采集？') }}
          </div>
        </div>
        <div class="content-item">
          <a
            class="guide"
            @click="handleGotoLink('componentMonitor')"
          >
            {{ $t('马上了解') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('如何对开源组件进行监控？') }}
          </div>
        </div>
      </div>
      <div v-else-if="alarm.name === 'process'">
        <div class="content-item">
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('未发现有异常运行的进程。') }}
          </div>
        </div>
        <div
          v-if="!alarm.has_monitor"
          class="content-item"
        >
          <a
            class="guide"
            @click="gotoStrategy"
          >
            {{ $t('立即配置') }}
          </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('检测到未配置进程/端口监控策略，请尽快配置方能及时的发现风险/故障。') }}
          </div>
        </div>
      </div>
      <div v-else-if="alarm.name === 'host'">
        <div class="content-item">
          <a class="guide"> {{ $t('快速设置') }} </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('检测到你对“CPU使用率、应用内容使用量、磁盘利用率”未做全局告警策略配置') }}
          </div>
        </div>
        <div class="content-item">
          <a class="guide"> {{ $t('快速设置') }} </a>
          <svg-icon
            class="item-icon"
            icon-name="hint"
          />
          <div class="item-content">
            {{ $t('检测到你的多个主机监控指标未配置告警策略') }}
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { gotoPageMixin } from '../../../common/mixins';
import SvgIcon from '../../../components/svg-icon/svg-icon';
import documentLinkMixin from '../../../mixins/documentLinkMixin';

export default {
  name: 'CommonNormal',
  components: {
    SvgIcon,
  },
  mixins: [gotoPageMixin, documentLinkMixin],
  inject: ['homeItemBizId'],
  props: {
    alarm: {
      type: Object,
      default() {
        return {};
      },
    },
  },
  data() {
    return {
      commonMap: {
        uptimecheck: {
          title: this.$t('当前拨测任务状态良好，无告警事件产生'),
        },
        service: {
          title: this.$t('当前被监控的服务运行正常，无告警产生'),
        },
        process: {
          title: this.$t('当前进程状态正常，无告警产生'),
        },
        os: {
          title: this.$t('当前主机状态正常，无告警事件产生'),
        },
      },
    };
  },
  computed: {
    normal() {
      return this.commonMap[this.alarm.name];
    },
  },
  methods: {
    gotoUpcheckTimePage(type, taskId) {
      if (type === 'node') {
        const url = `${location.origin}${location.pathname}?bizId=${this.homeItemBizId}#/uptime-check?dashboardId=uptime-check-node`;
        location.href = url;
      } else {
        const url = `${location.origin}${location.pathname}?bizId=${this.homeItemBizId}#/uptime-check/task-detail/${taskId}`;
        location.href = url;
      }
    },
    gotoStrategy() {
      const url = `${location.origin}${location.pathname}?bizId=${this.homeItemBizId}#/strategy-config/add`;
      location.href = url;
    },
    gotoCustomPage() {
      localStorage.setItem('configListIndex', 1);
      this.commonGotoPage('config');
    },
    gotoComponentPage(name) {
      if (name) {
        this.commonGotoPage(`component/?type=${name}`);
      } else {
        this.commonGotoPage('config');
      }
    },
  },
};
</script>

<style scoped lang="scss">
@import '../common/mixins';

@mixin content-dec {
  color: #3a84ff;

  &:hover {
    cursor: pointer;
  }
}

.common-normal {
  padding-right: 40px;

  .title {
    min-width: 450px;
    padding-bottom: 17px;
    font-size: 12px;
    line-height: 19px;
    color: $defaultFontColor;
    border-bottom: 1px solid $defaultBorderColor;

    &-guide {
      @include content-dec();
    }
  }

  .content {
    padding: 13px 0;

    > div {
      max-height: 260px;
      overflow: auto;
    }

    &-item {
      margin: 10px 0;
      overflow: hidden;
      font-size: 12px;
      color: $defaultFontColor;

      .item-icon {
        float: left;
        margin-top: 1px;
        font-size: $fontNormalSize;
        color: #979ba5;
      }

      .item-content {
        min-width: 340px;
        margin-right: 60px;
        margin-left: 25px;

        .into {
          color: #3a84ff;
          cursor: pointer;
        }
      }

      .guide {
        float: right;

        @include content-dec();
      }

      .item-warning {
        color: #ff9c01;
      }
    }
  }
}
</style>
