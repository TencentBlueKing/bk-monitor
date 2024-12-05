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
  <div class="step-set-done">
    <div class="step-set-done-body">
      <div
        v-if="loading"
        class="done-loading"
      >
        <svg
          class="loading-svg"
          viewBox="0 0 64 64"
        >
          <g>
            <path
              d="M20.7,15c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0l-2.8-2.8c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L20.7,15z"
            />
            <path d="M12,28c2.2,0,4,1.8,4,4s-1.8,4-4,4H8c-2.2,0-4-1.8-4-4s1.8-4,4-4H12z" />
            <path
              d="M15,43.3c1.6-1.6,4.1-1.6,5.7,0c1.6,1.6,1.6,4.1,0,5.7l-2.8,2.8c-1.6,1.6-4.1,1.6-5.7,0s-1.6-4.1,0-5.7L15,43.3z"
            />
            <path d="M28,52c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V52z" />
            <path
              d="M51.8,46.1c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0L43.3,49c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L51.8,46.1z"
            />
            <path d="M56,28c2.2,0,4,1.8,4,4s-1.8,4-4,4h-4c-2.2,0-4-1.8-4-4s1.8-4,4-4H56z" />
            <path
              d="M46.1,12.2c1.6-1.6,4.1-1.6,5.7,0s1.6,4.1,0,5.7l0,0L49,20.7c-1.6,1.6-4.1,1.6-5.7,0c-1.6-1.6-1.6-4.1,0-5.7L46.1,12.2z"
            />
            <path d="M28,8c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V8z" />
          </g>
        </svg>
        <div class="loading-message-container">
          <h4 class="message-title">
            {{ $t('保存插件中，请稍后...') }}
          </h4>
        </div>
      </div>
      <div
        v-else
        class="done-result"
      >
        <div
          v-if="status"
          class="result-success"
        >
          <svg
            class="success-svg"
            viewBox="0 0 64 64"
          >
            <path
              d="M32,4c15.5,0,28,12.5,28,28S47.5,60,32,60S4,47.5,4,32S16.5,4,32,4z M32,8C18.7,8,8,18.7,8,32c0,13.3,10.7,24,23.9,24.1c6.4,0,12.5-2.5,17.1-7.1c9.4-9.4,9.4-24.6,0.1-33.9c0,0,0,0-0.1-0.1C44.5,10.5,38.4,8,32,8z"
            />
            <polygon points="44,22 47,25 28,44 17,33 20,30 28,38" />
          </svg>
          <div class="success-message">
            <template v-if="data.type === 'edit'">
              <h4 class="message-title">
                {{ $t('编辑插件完成') }}
              </h4>
              <p class="message-tip">
                {{ $t('经过努力，新的插件生成了，恭喜') }}
              </p>
            </template>
            <template v-else>
              <h4 class="message-title">
                {{ $t('创建插件完成') }}
              </h4>
              <p class="message-tip">
                {{ $t('经过努力，终于拥有了完全属于你自己的插件，加油') }}
              </p>
            </template>
          </div>
        </div>
        <div
          v-else
          class="result-fail"
        >
          <svg
            class="fail-svg"
            viewBox="0 0 64 64"
          >
            <g>
              <path
                d="M32,8c13.3,0,24,10.7,24,24S45.3,56,32,56S8,45.3,8,32S18.7,8,32,8 M32,4C16.5,4,4,16.5,4,32s12.5,28,28,28s28-12.5,28-28S47.5,4,32,4z"
              />
              <path
                d="M40.5,20.7l2.8,2.8L34.8,32l8.5,8.5l-2.8,2.8L32,34.8l-8.5,8.5l-2.8-2.8l8.5-8.5l-8.5-8.5l2.8-2.8l8.5,8.5L40.5,20.7z"
              />
            </g>
          </svg>
          <div class="fail-message">
            <h4 class="message-title">
              {{ data.type === 'edit' ? $t('插件编辑失败') : $t('插件新建失败') }}
            </h4>
            <p class="message-tip">
              {{ error }}
            </p>
          </div>
        </div>
      </div>
    </div>
    <div
      v-if="!loading"
      class="step-set-done-footer"
    >
      <bk-button
        class="mr10"
        @click="close"
      >
        {{ $t('button-关闭') }}
      </bk-button>
      <bk-button
        v-if="needUpdataPlugin"
        class="mr10"
        theme="primary"
        @click="goToCollectConfig"
        >{{ $t('前往采集配置升级插件') }}</bk-button
      >
      <bk-button
        theme="primary"
        @click="goToCollectConfigAdd"
        >{{ $t('新建采集配置') }}</bk-button
      >
    </div>
  </div>
</template>

<script>
import { releaseCollectorPlugin } from 'monitor-api/modules/model';

export default {
  name: 'StepSetDone',
  inject: ['authority', 'handleShowAuthorityDetail', 'pluginManageAuth'],
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    fromRoute: {
      type: String,
    },
  },
  data() {
    return {
      loading: true,
      status: true,
      error: '',
    };
  },
  computed: {
    needUpdataPlugin() {
      const {
        config_version: configVersion,
        config_version_old: configVersionOld,
        related_conf_count: relatedConfCount,
      } = this.data;
      // 配置版本更新 并且 有关联配置的显示去更新插件按钮
      return (
        configVersionOld &&
        configVersion !== configVersionOld &&
        configVersion > configVersionOld &&
        relatedConfCount > 0
      );
    },
  },
  async activated() {
    this.loading = true;
    const { data } = this;
    const { saveData } = data;
    if (saveData.from === 'save') {
      // 从【保存插件】按钮进来
      if (data.type === 'create') {
        // 新建
        this.releasePlugin(this.data);
      } else {
        // 编辑
        if (data.token?.length) {
          this.releasePlugin(this.data);
        } else {
          this.simRelease('success');
        }
      }
    } else {
      // 否则，取缓存里的结果
      this.simRelease(saveData.status, saveData.message);
    }
  },
  methods: {
    goToCollectConfig() {
      this.$router.push({
        name: 'collect-config',
        params: {
          searchType: 'upgrade',
          pluginId: this.data.plugin_id,
        },
      });
    },
    goToCollectConfigAdd() {
      this.$router.push({
        name: 'collect-config-add',
        params: {
          objectId: this.data.label,
          pluginType: this.data.plugin_type,
          pluginId: this.data.plugin_id,
        },
      });
    },
    close() {
      // 采集新增页面特殊处理
      if (this.fromRoute === 'collect-config-add') {
        this.$router.push({
          name: this.fromRoute,
          params: {
            objectId: this.data.label,
            pluginType: this.data.plugin_type,
            pluginId: this.data.plugin_id,
          },
        });
      } else {
        this.$router.push({
          name: 'plugin-manager',
        });
      }
    },
    releasePlugin(params) {
      releaseCollectorPlugin(params.plugin_id, {
        config_version: params.config_version,
        info_version: params.info_version,
        token: params.token,
      })
        .then(() => {
          this.status = true;
          this.saveData('success');
        })
        .catch(err => {
          this.status = false;
          this.saveData('fail', err.message);
        })
        .finally(() => {
          this.loading = false;
        });
    },
    simRelease(status, message) {
      setTimeout(() => {
        this.loading = false;
        if (status === 'fail') {
          this.error = message;
        }
      }, 1000);
    },
    saveData(status, message) {
      const { saveData } = this;
      saveData.status = status;
      saveData.message = message;
    },
    getCollectionAuth() {
      if (this.data.status === 'normal') {
        return !this.authority.COLLECTION_VIEW_AUTH;
      }
      return !this.authority.COLLECTION_MANAGE_AUTH;
    },
  },
};
</script>

<style scoped lang="scss">
@import '../../../home/common/mixins';

@mixin message-title {
  height: 21px;
  font-size: 16px;
  font-weight: bold;
  line-height: 21px;
  color: #000;
}

@mixin message-tip {
  width: auto;
  height: 16px;
  font-size: 12px;
  line-height: 16px;
  color: #63656e;
}

.step-set-done {
  display: flex;
  flex-direction: column;
  justify-content: center;

  .step-set-done-body {
    margin-top: 84px;

    .done-loading {
      display: flex;
      flex-direction: column;
      align-items: center;

      @keyframes done-loading {
        0% {
          transform: rotate(0deg);
        }

        100% {
          transform: rotate(-360deg);
        }
      }

      .loading-svg {
        width: 58px;
        height: 58px;
        animation: done-loading 1s linear 0s infinite;

        g {
          @for $i from 1 through 8 {
            :nth-child(#{$i}) {
              opacity: #{$i * 0.125};
              fill: $primaryFontColor;
            }
          }
        }
      }

      .loading-message-container {
        .message-title {
          height: 21px;
          font-size: 16px;
          font-weight: bold;
          line-height: 21px;
          color: #000;
        }
      }
    }

    .done-result {
      display: flex;
      flex-direction: column;
      align-items: center;

      .result-success {
        text-align: center;

        .success-svg {
          width: 58px;
          height: 58px;
          fill: #2dcb56;
        }

        .success-message {
          .message-title {
            @include message-title();
          }

          .message-tip {
            @include message-tip();
          }
        }
      }

      .result-fail {
        text-align: center;

        .fail-svg {
          width: 58px;
          height: 58px;
          fill: #ea3636;
        }

        .fail-message {
          .message-title {
            @include message-title();
          }
        }
      }
    }
  }

  .step-set-done-footer {
    display: flex;
    justify-content: center;
    margin-top: 26px;
  }
}
</style>
