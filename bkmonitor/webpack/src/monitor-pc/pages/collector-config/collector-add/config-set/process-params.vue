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
  <div class="process-params">
    <div
      class="form-item"
      v-show="false"
    >
      <!-- 插件选择部分优先级提高，故隐藏此处 -->
      <label class="item-label required">{{ $t('插件') }}</label>
      <div class="item-content">
        <bk-input
          :value="pluginDisplayName"
          readonly
        />
      </div>
    </div>
    <div class="form-item">
      <label class="item-label required">{{ $t('进程匹配') }}</label>
      <div class="item-content">
        <bk-radio-group
          class="process-match"
          v-model="params.match_type"
        >
          <bk-radio value="command">
            {{ $t('命令行匹配') }}
          </bk-radio>
          <bk-radio
            class="ml20"
            value="pid"
          >
            {{ $t('PID文件') }}
          </bk-radio>
        </bk-radio-group>
        <div v-if="params.match_type === 'command'">
          <verify-input
            class="small-input validate-icon"
            :show-validate.sync="rules.match_pattern"
            :validator="{ content: $t('必填项') }"
            position="right"
          >
            <bk-input
              class="mt10 small-input"
              v-model="params.match_pattern"
              :placeholder="$t('进程关键字')"
            >
              <template slot="prepend">
                <div class="group-text">
                  {{ $t('包含') }}
                </div>
              </template>
            </bk-input>
          </verify-input>
          <bk-input
            class="mt10 small-input"
            v-model="params.exclude_pattern"
            :placeholder="$t('进程排除正则')"
          >
            <template slot="prepend">
              <div class="group-text">
                {{ $t('排除') }}
              </div>
            </template>
          </bk-input>
          <bk-input
            class="mt10 small-input"
            v-model="params.extract_pattern"
            :placeholder="$t('维度提取')"
          >
            <template slot="prepend">
              <div class="group-text">
                {{ $t('维度提取') }}
              </div>
            </template>
          </bk-input>
        </div>
        <template v-else-if="params.match_type === 'pid'">
          <verify-input
            class="small-input validate-icon"
            :show-validate.sync="rules.pid_path"
            :validator="{ content: $t('必填项') }"
            position="right"
          >
            <bk-input
              class="mt10 small-input"
              v-model="params.pid_path"
              :placeholder="$t('PID的绝对路径')"
            />
          </verify-input>
        </template>
      </div>
    </div>
    <div class="form-item">
      <label class="item-label">{{ $t('进程名') }}</label>
      <div class="item-content">
        <bk-input
          v-model="params.process_name"
          :placeholder="$t('留空默认以二进制名称，可以手动指定或者取值')"
        />
      </div>
    </div>
    <div class="form-item">
      <label class="item-label">{{ $t('端口探测') }}</label>
      <div class="item-content">
        <bk-switcher
          v-model="params.port_detect"
          :off-text="$t('关')"
          :on-text="$t('开')"
          size="small"
          theme="primary"
          show-text
        />
      </div>
    </div>
  </div>
</template>
<script>
import VerifyInput from '../../../../components/verify-input/verify-input.vue';

export default {
  name: 'ProcessParams',
  components: {
    VerifyInput,
  },
  props: {
    processParams: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      params: Object.assign(
        {
          match_type: 'pid',
          pid_path: '',
          process_name: '',
          match_pattern: '',
          exclude_pattern: '',
          extract_pattern: '',
          port_detect: true,
          labels: {},
        },
        this.processParams
      ),
      rules: {
        pid_path: false,
        match_pattern: false,
      },
      pluginDisplayName: this.$t('进程采集插件'),
    };
  },
  watch: {
    params: {
      deep: true,
      handler(newValue, oldValue) {
        this.$emit('change', newValue, oldValue);
      },
    },
  },
  methods: {
    // 校验
    validate() {
      if (this.params.match_type === 'pid') {
        this.rules.pid_path = !this.params.pid_path;
        return !!this.params.pid_path;
      }
      this.rules.match_pattern = !this.params.match_pattern;
      return !!this.params.match_pattern;
    },
  },
};
</script>
<style lang="scss" scoped>
.small-input {
  width: 320px;

  &.validate-icon {
    :deep(.tooltips-icon) {
      top: 18px;
      right: 5px;
    }
  }
}

.form-item {
  display: flex;
  margin-bottom: 20px;

  .item-label {
    position: relative;
    min-width: 75px;
    height: 32px;
    margin-right: 34px;
    line-height: 32px;
    text-align: right;

    &.required {
      &::after {
        position: absolute;
        right: -9px;
        font-size: 12px;
        color: #f00;
        content: '*';
      }
    }
  }

  .item-content {
    width: 500px;

    :deep(.bk-radio-text) {
      font-size: 12px;
    }
  }
}
</style>
