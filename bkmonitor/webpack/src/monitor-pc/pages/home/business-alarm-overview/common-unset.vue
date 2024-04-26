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
  <section class="common-unset">
    <div class="title">
      {{ unset.title }}
      <a
        v-if="alarm.name === 'uptimechecold'"
        class="title-guide"
        >{{ $t('推荐接⼊') }}</a
      >
    </div>
    <div class="content">
      <div class="content-title">
        {{ $t('接入指引') }}
      </div>
      <div class="content-wrap">
        <div v-if="alarm.name === 'uptimecheck'">
          <div class="content-wrap-item">
            {{ $t('第1步：配置拨测节点') }}
            <svg-icon
              v-if="alarm.step > 1"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              v-if="alarm.step <= 1"
              class="guide"
              @click="alarm.step === 1 && gotoUptimeCheckPage(0)"
            >
              {{ $t('立即配置') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第2步：创建拨测任务') }}
            <svg-icon
              v-if="alarm.step > 2"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              @click="gotoUptimeCheckPage(1)"
              >{{ alarm.step > 2 ? $t('创建完成') : $t('立即创建') }}</a
            >
          </div>
          <!-- <div class="content-wrap-item"> {{ $t('文档链接：') }} <a class="doc-link" href="https://bk.tencent.com/docs/" target="_blank">https://bk.tencent.com/docs/</a> -->
          <!-- <svg-icon v-if="alarm.step > 2" class="icon-check" icon-name="check-circle"></svg-icon>
                        <a class="guide" @click="gotoUptimeCheckPage(1)">{{alarm.step > 2 ? $t('创建完成') : $t('立即创建')}}</a> -->
          <!-- </div> -->
        </div>
        <div v-else-if="alarm.name === 'service'">
          <div class="content-wrap-item">
            {{ $t('第1步：创建对应的采集任务获取数据') }}
            <svg-icon
              v-if="alarm.step > 1"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              @click="gotoSpeciallyRoute('service', 'collector')"
            >
              {{ $t('新建采集') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第2步：前往仪表盘配置个性化视图') }}
            <svg-icon
              v-if="alarm.step > 2"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              @click="gotoDashboardPage"
            >
              {{ $t('配置 Dashboard') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第3步：配置监控策略，时刻保障服务正常运行') }}
            <svg-icon
              v-if="alarm.step > 3"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              @click="gotoSpeciallyRoute('service', 'strategy')"
            >
              {{ $t('创建策略') }}
            </a>
          </div>
        </div>
        <div v-else-if="alarm.name === 'process'">
          <div class="content-wrap-item">
            {{ $t('第一步：了解进程的配置方法') }}
            <a
              class="guide"
              @click="handleGotoLink('processMonitor')"
            >
              {{ $t('前往查看') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第二步：前往配置平台录入服务的完整信息') }}
            <svg-icon
              v-if="alarm.step > 1"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              @click="gotoCMDBPage"
            >
              {{ $t('立即录入') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第三步：在主机监控页面查看服务进程状态') }}
            <svg-icon
              v-if="alarm.step > 1"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              @click="gotoSpeciallyRoute('process', 'performance')"
            >
              {{ $t('前往查看') }}
            </a>
          </div>
        </div>
        <div v-else-if="alarm.name === 'os'">
          <div class="content-wrap-item">
            {{ $t('第1步：给你的主机安装蓝鲸Agent') }}
            <svg-icon
              v-if="alarm.step > 1"
              class="icon-check"
              icon-name="check-circle"
            />
            <a
              class="guide"
              :class="{ 'guide-done': alarm.step > 1 }"
              @click="alarm.step === 1 && gotoOtherPage()"
              >{{ alarm.step > 1 ? $t('部署完成') : $t('立即部署') }}</a
            >
          </div>
          <div class="content-wrap-item">
            {{ $t('第2步：查看主机列表') }}
            <a
              class="guide"
              @click="gotoHostPage"
            >
              {{ $t('前往查看') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第3步：系统默认配置的全局告警策略') }}
            <a
              class="guide"
              @click="gotoStrategy"
            >
              {{ $t('前往查看') }}
            </a>
          </div>
          <div class="content-wrap-item">
            {{ $t('第4步：开启主机基础进程端口告警') }}
            <a
              class="guide"
              @click="handleGotoLink('processMonitor')"
            >
              {{ $t('立即开启') }}
            </a>
          </div>
        </div>
      </div>
    </div>
    <div
      class="footer"
      :class="{
        'footer-border':
          alarm.name === 'uptimecheck' || alarm.name === 'process' || alarm.name === 'service' || alarm.name === 'os',
      }"
    >
      <div v-if="alarm.name === 'uptimecheck'">
        <div class="footer-content">
          {{ $t('5分钟快速上手“服务拨测”功能') }}
          <a
            class="guide"
            @click="gotoOtherPage"
          >
            {{ $t('前往查看') }}
          </a>
        </div>
      </div>
      <div v-else-if="alarm.name === 'service'">
        <div class="footer-content">
          {{ $t("了解'快速接入'方法") }}
          <a
            class="guide"
            @click="gotoOtherPage"
          >
            {{ $t('前往查看') }}
          </a>
        </div>
        <div class="footer-content">
          {{ $t('内置的不够用？快速制作自己的插件！') }}
          <a
            class="guide"
            @click="gotoSpeciallyRoute('service', 'plugin')"
          >
            {{ $t('立即导入') }}
          </a>
        </div>
      </div>
      <!-- <div v-if="alarm.name === 'process'">
                <div class="footer-content">
                    蓝鲸组件监控能⼒说明 <a class="guide" @click="gotoOtherPage(1)"> {{ $t('前往查看') }} </a>
                </div>
                <div class="footer-content">
                    自研中间件也能接? <a class="guide" @click="gotoOtherPage(2)">立即接入</a>
                </div>
            </div>
            <div v-if="alarm.name === 'os'">
                <div class="footer-content">
                    蓝鲸监控的OS监控指标大全 <a class="guide" @click="gotoOtherPage(1)">立即查看</a>
                </div>
            </div> -->
    </div>
  </section>
</template>

<script>
import { gotoPageMixin } from '../../../common/mixins';
import SvgIcon from '../../../components/svg-icon/svg-icon';
import documentLinkMixin from '../../../mixins/documentLinkMixin';

// const routes = {
//   service: {
//     collector: { name: 'collect-config-add' },
//     strategy: { name: 'strategy-config-add' },
//     plugin: { name: 'plugin-manager' }
//   },
//   process: {
//     performance: { name: 'performance' }
//   }
// };
const hrefs = {
  service: {
    collector: '/collect-config/add',
    strategy: '/strategy-config/add',
    plugin: '/plugin-manager',
  },
  process: {
    performance: '/performance',
  },
};
export default {
  name: 'CommonUnset',
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
      defaultComponentList: ['apache', 'mysql', 'nginx', 'tomcat', 'redis', 'consul', this.$t('更多')],
      unsetMap: {
        uptimecheck: {
          title: this.$t(
            '【服务拨测】作为比较贴近用户体验层的监控功能，能够模拟处于不同运营商网络的用户访问你的业务的质量，第一时间掌握用户端对产品业务体验的反馈。'
          ),
        },
        service: {
          title: this.$t(
            '【服务监控】支持各类开源和自研的中间件、组件等服务接入，使用内置或自研的采集器捕获服务的数据，展示丰富的指标图表并配置完善的告警策略进行防护。'
          ),
        },
        process: {
          title: this.$t(
            '【进程监控】进程是上承服务、下接OS的连接器，在关联分析模型中也起着重要的作用！蓝鲸监控基于配置平台服务模块对服务实例的管理，能够将服务的进程运行状态和相关服务实例更好的衔接监控起来。'
          ),
        },
        os: {
          title: this.$t(
            '蓝鲸监控支持对市面上常见的类Unix和Windows操作系统进行监控（企业版支持AIX），包括OS的基础性能指标和系统事件告警。'
          ),
        },
      },
    };
  },
  computed: {
    unset() {
      return this.unsetMap[this.alarm.name];
    },
  },
  methods: {
    gotoCMDBPage() {
      window.open(`${this.$store.getters.cmdbUrl}/#/business/index`);
    },
    gotoSpeciallyRoute(moduleName, routeName) {
      this.customBizIdGotoPage(this.homeItemBizId, hrefs[moduleName][routeName]);
      // this.$router.push(routes[moduleName][routeName]);
      // this.$router.push({ name: 'strategy-config-add' })
    },
    gotoUptimeCheckPage(type) {
      this.customBizIdGotoPage(this.homeItemBizId, !type ? '/uptime-check/node-add' : '/uptime-check/task-add');
      // this.$router.push({
      //   name: !type ? 'uptime-check-node-add' : 'uptime-check-task-add',
      //   params: {
      //     bizId: this.homeItemBizId
      //   }
      // });
    },
    gotoDashboardPage() {
      this.customBizIdGotoPage(this.homeItemBizId, '/grafana');
      // this.$router.push({
      //   name: 'grafana'
      // });
    },
    gotoCustomPage(type) {
      if (!type) {
        this.commonGotoPage('datasource/');
      } else {
        this.commonGotoPage('dashboard/');
      }
    },
    gotoComponentPage(name) {
      this.commonGotoPage(`component/?component=${name}`);
    },
    gotoHostPage() {
      this.customBizIdGotoPage(this.homeItemBizId, '/performance');
      // this.$router.push({
      //   name: 'performance'
      // });
    },
    gotoStrategy() {
      this.customBizIdGotoPage(this.homeItemBizId, '/strategy-config');
      // this.$router.push({
      //   name: 'strategy-config'
      // });
    },
    gotoOtherPage(type) {
      if (this.alarm.name === 'uptimecheck') {
        this.handleGotoLink('quickStartDial');
      } else if (this.alarm.name === 'service') {
        this.handleGotoLink('bestPractices');
      } else if (this.alarm.name === 'process') {
        if (type === 1) {
          window.open(
            'https://docs.bk.tencent.com/product_white_paper/bk_monitor/Component_Monitor_desc.html',
            '_blank'
          );
        } else {
          this.commonGotoPage('component/?type=custom');
        }
      } else if (this.alarm.name === 'os') {
        if (type === 1) {
          window.open('https://docs.bk.tencent.com/product_white_paper/bk_monitor/Host_monitor_desc.html', '_blank');
        } else {
          window.open(window.agent_setup_url, '_blank');
        }
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

@mixin content-item() {
  font-size: 12px;
  color: $defaultFontColor;
  line-height: 27px;

  .icon-check {
    margin-bottom: 2px;
    color: #2dcb56;
    font-size: 16px;
  }

  .guide {
    @include content-dec();
  }

  .guide-more {
    /* stylelint-disable-next-line declaration-no-important */
    color: #3a84ff !important;
  }
}

.common-unset {
  padding-right: 40px;

  .title {
    min-width: 450px;
    font-size: 12px;
    color: $defaultFontColor;
    line-height: 19px;
    padding-bottom: 17px;
    border-bottom: 1px solid $defaultBorderColor;

    &-guide {
      @include content-dec();
    }
  }

  .content {
    padding: 13px 0;

    &-title {
      font-size: $fontSmSize;
      font-weight: bold;
      color: $defaultFontColor;
      line-height: 23px;
      margin-bottom: 3px;
    }

    &-wrap {
      height: auto;
      display: block;

      &-item {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;

        @include content-item();

        .guide-done {
          color: $defaultFontColor;

          &:hover {
            /* stylelint-disable-next-line declaration-no-important */
            cursor: default !important;
          }
        }

        .doc-link {
          text-decoration: none;
          color: #3a84ff;
        }

        .list {
          padding: 0;
          max-height: 100px;
          overflow: auto;

          .item {
            margin: 5px 0;
            font-size: 12px;
            color: $defaultFontColor;
            float: left;
            width: 110px;
            text-align: left;

            &:hover {
              cursor: pointer;
              color: #3a84ff;
            }

            &-icon {
              margin-right: 6px;
              width: 18px;
              height: 18px;
              color: #3a84ff;
            }

            &-icon-serious {
              color: $seriousFontColor;
            }

            &-icon-normal {
              color: $normalFontColor;
            }

            &-icon-unset,
            &-icon-default {
              color: $normalFontColor;
            }
          }
        }
      }
    }
  }

  .footer {
    padding: 13px 0;

    &-content {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;

      @include content-item();
    }
  }

  .footer-border {
    border-top: 1px solid $defaultBorderColor;
  }
}
</style>
