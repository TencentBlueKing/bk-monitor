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
  <div class="empty-target">
    <top-hint
      v-if="tipShow"
      class="target-hint"
    >
      <slot>
        {{ $t('本次下发覆盖') }}
        {{ targetString ? targetString : targetMessage.title + targetMessage.subTitle }}
        <i
          class="icon-monitor icon-mc-close"
          @click="tipShow = !tipShow"
        />
      </slot>
    </top-hint>
    <div class="empty-container">
      <div class="register-dialog">
        <div
          v-if="!taskReady.failMsg"
          class="loading"
        >
          <svg-loading-icon />
        </div>
        <div>
          <div class="register-msg">
            {{ taskReady.msg }}
          </div>
          <div
            v-if="!taskReady.failMsg"
            class="wait"
          >
            {{ $t('等待中') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { transformDataKey } from 'monitor-common/utils/utils';

import SvgLoadingIcon from '../../../../components/svg-loading-icon/svg-loading-icon';
import TopHint from './top-hint';

const { i18n } = window;
export default {
  name: 'TaskReady',
  components: {
    TopHint,
    SvgLoadingIcon,
  },
  props: {
    taskReady: {
      type: Object,
      default: {
        msg: i18n.t('准备中...'),
      },
    },
    target: {
      type: Object,
      default: () => ({}),
    },
    targetString: {
      type: String,
    },
  },
  data() {
    return {
      targetMessage: {
        title: '',
        subTitle: '',
      },
      tipShow: true,
    };
  },
  watch: {
    target: {
      handler(v) {
        const result = transformDataKey(v);
        const { target, bkTargetType, bkObjType } = result;
        const textMap = {
          TOPO: '{0}个拓扑节点',
          SERVICE_TEMPLATE: '{0}个服务模板',
          SET_TEMPLATE: '{0}个集群模板',
        };
        if (target?.length) {
          let len = target.length;
          if (['SERVICE_TEMPLATE', 'SET_TEMPLATE', 'TOPO'].includes(bkTargetType)) {
            const count = target.reduce((list, cur) => {
              const allTargets = cur.allHost || [];
              return Array.from(new Set([...list, ...allTargets]));
            }, []).length;
            // 服务模板和集群模板比较特殊，不能直接取target的长度作为数量
            if (['SET_TEMPLATE', 'SERVICE_TEMPLATE'].includes(bkTargetType)) {
              const name = bkTargetType.replace('_', '');
              len = target.reduce(
                (all, cur) => (cur[name] ? Array.from(new Set([...all, cur[name]])) : all),
                []
              ).length;
            }
            this.targetMessage.title = this.$t(textMap[bkTargetType], [len]);
            const res = bkObjType === 'SERVICE' ? '个实例' : '台主机';
            this.targetMessage.subTitle = `(${this.$t(`共{0}${res}`, [count])})`;
          } else {
            this.targetMessage.title = this.$t('{0}台主机', [len]);
          }
        } else {
          this.targetMessage.title = `0${textMap[bkTargetType]}`;
        }
      },
      immediate: true,
      deep: true,
    },
  },
};
</script>

<style lang="scss" scoped>
.empty-target {
  height: 500px;
  margin-bottom: 20px;

  .target-hint {
    margin-bottom: 10px;

    :deep(.hint-text) {
      display: flex;
      justify-content: space-between;
      padding-right: 13px;

      .icon-mc-close {
        position: relative;
        top: -2px;
        font-size: 18px;
        cursor: pointer;
      }
    }
  }

  .empty-container {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 452px;
    background: #fff;
    border: 1px dashed #dcdee5;
    border-radius: 2px;
  }

  .register-dialog {
    .loading {
      margin-bottom: 9px;
      text-align: center;
    }

    .register-msg {
      margin-bottom: 7px;
      font-size: 24px;
      line-height: 1.3;
      color: #313238;
      text-align: center;
    }

    .wait {
      margin-bottom: 12px;
      font-size: 14px;
      color: #444;
      text-align: center;
    }
  }
}
</style>
