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
  <div
    :class="['auto-complete-input', { 'password-input': isPasswordInput }]"
    ref="wrap"
  >
    <!-- 文本类型 -->
    <template v-if="!['file', 'boolean', 'list', 'switch', 'tag_list', 'code'].includes($attrs.type)">
      <!-- 新增判断是否为密码框，若为密码框则不显示密码，根据密码的有无显示placeholder为"已配置/未配置" -->
      <bk-input
        :class="['input-text', { password: isPasswordInput }]"
        ref="input"
        v-model="params"
        :placeholder="computedPlaceholder"
        :readonly="isPasswordInput && passwordInputReadonly"
        :type="isPasswordInput ? 'password' : 'text'"
        @input="handleInput"
      >
        <template slot="prepend">
          <slot name="prepend" />
        </template>
      </bk-input>
      <!-- 为密码框的情况新增用于重置密码的按钮 -->
      <template v-if="isPasswordInput">
        <bk-button
          class="ml5"
          @click="handleResetPassword"
          >{{ $t('重置') }}</bk-button
        >
      </template>
      <!-- <span ref="tempSpan" class="temp-span">{{params}}</span> -->
      <div v-show="false">
        <ul
          ref="list"
          class="auto-complete-input-list"
        >
          <li
            @mousedown="handleMousedown(item, index)"
            class="list-item"
            v-for="(item, index) in tipsData"
            :key="item.name + index"
            v-show="!params || item.name.includes(keyword)"
          >
            {{ item.name }}
            <span class="item-desc">{{ item.description }}</span>
          </li>
        </ul>
      </div>
    </template>
    <div
      v-else-if="$attrs.type === 'file'"
      class="file-input-wrap"
    >
      <template v-if="config.key === 'yaml'">
        <div
          v-bkloading="{ isLoading: loading, size: 'mini' }"
          class="auto-complete-input-file"
        >
          <bk-input
            v-if="allConfig.key === 'yaml'"
            ref="input"
            v-model="params"
            :placeholder="$t('点击上传mib转换后的yaml配置文件')"
          >
            <template slot="prepend">
              <slot name="prepend" />
            </template>
          </bk-input>
          <bk-input
            v-else
            ref="input"
            v-model="params"
          >
            <template slot="prepend">
              <slot name="prepend" />
            </template>
          </bk-input>
          <input
            class="auto-complete-input-file-input"
            type="file"
            ref="upload"
            accept=".yaml,.yml"
            @change="fileChange"
          />
        </div>
      </template>
      <template v-else>
        <div class="prepend">
          <slot name="prepend" />
        </div>
        <div class="file-name">
          <import-file
            class="import-file"
            :file-name="config.default"
            :file-content="config.file_base64"
            @error-message="handleErrorMessage"
            @change="handleFileChange"
          />
        </div>
      </template>
    </div>
    <div
      v-else-if="$attrs.type === 'switch'"
      class="switch-input-wrap"
    >
      <div class="prepend">
        <slot name="prepend" />
      </div>
      <div class="file-name switch-wrap">
        <bk-switcher
          true-value="true"
          false-value="false"
          @change="handleSwitchChange"
          v-model="params"
        />
      </div>
    </div>
    <template v-else-if="$attrs.type === 'code'">
      <div class="auto-complete-input-select code-select">
        <slot name="prepend" />
        <MonacoEditor
          class="code-select-editor"
          style="height: 250px"
          :value="config.default"
          :language="'json'"
          :theme="'vs-light'"
          :height="250"
          :options="config.options || { minimap: { enabled: false }, fontSize: 12 }"
          @change="handleCodeChange"
        />
      </div>
    </template>
    <template v-else-if="$attrs.type === 'tag_list'">
      <div class="auto-complete-input-select">
        <slot name="prepend" />
        <bk-select
          :clearable="false"
          :disabled="false"
          v-model="params"
          multiple
          @change="handleTagListChange"
          ext-cls="select-custom"
          ext-popover-cls="select-popover-custom"
          :allow-create="false"
          :display-tag="true"
        >
          <bk-option
            v-for="option in config.election"
            :key="option.id"
            :id="option.id"
            :name="option.name"
          />
        </bk-select>
      </div>
    </template>
    <!-- list类型 下拉列表 -->
    <template v-else-if="$attrs.type === 'list'">
      <!-- 当前为security_level选项 -->
      <template v-if="allConfig.key === 'security_level'">
        <div class="auto-complete-input-select">
          <slot name="prepend" />
          <bk-select
            :clearable="false"
            :disabled="false"
            v-model="params"
            @change="handleSelectSecurity"
            ext-cls="select-custom"
            ext-popover-cls="select-popover-custom"
          >
            <bk-option
              v-for="option in allConfig.election"
              :key="option"
              :id="option.id"
              :name="option"
            />
          </bk-select>
        </div>
      </template>
      <!-- 普通选项 -->
      <template v-else>
        <div class="auto-complete-input-select">
          <slot name="prepend" />
          <bk-select
            :disabled="false"
            v-model="params"
            @change="handleSelect"
            ext-cls="select-custom"
            ext-popover-cls="select-popover-custom"
          >
            <bk-option
              v-for="option in allConfig?.auth_priv?.[curAuthPriv]?.need
                ? allConfig.auth_priv[curAuthPriv].election
                : allConfig.election"
              :key="option"
              :id="option?.id ? option.id : option"
              :name="option?.name ? option.name : option"
            />
          </bk-select>
        </div>
      </template>
    </template>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import ImportFile from '../../../plugin-manager/plugin-instance/set-steps/components/import-file.vue';
import MonacoEditor from '../../../../components/editors/monaco-editor.vue';

interface IPopoverInstance {
  hide: (time: number) => void | boolean;
  show: (time: number) => void | boolean;
  destroy: () => void;
  set: (options: any) => void | IPopoverInstance;
}
interface ITipsItem {
  name: string;
  description: string;
}
@Component({
  name: 'auto-complete-input',
  components: {
    ImportFile,
    MonacoEditor,
  },
})
export default class StrategySetTarget extends Vue {
  // bkPopover实例对象
  popoverInstance: IPopoverInstance;
  // 关键词
  keyword = '';
  // 对外输出参数
  params = '';

  authPriv = '';

  allConfig = {};
  // 补全提示列表offsetX/offsetY
  offsetX = 0;
  offsetY = 0;
  // 输入旧值
  oldVal = '';
  // 光标在关键字的起始位置
  startIndex = 0;
  // 光标的当前位置
  curIndex = 0;

  FileNode = null;

  // 文件类型loading
  loading = false;

  passwordInputReadonly = true;

  changedPasswordValue = false; // 密码输入框是否发生过变更
  customPlaceholder = '';

  // 当前authPriv
  @Prop({
    type: String,
    default: 'noAuthNoPriv',
  })
  curAuthPriv: string;

  // 传入的value
  @Prop({
    type: [String, Boolean, Array, Number, Object],
    default: '',
  })
  value: string;

  @Prop({
    type: [Object, String],
    default: '',
  })
  config: {};

  // 补全输入数据
  @Prop({
    default() {
      return [];
    },
  })
  tipsData: ITipsItem[];

  @Watch('curAuthPriv')
  handleCurAuthPriv(v) {
    this.authPriv = v;
  }

  @Watch('config', {
    immediate: true,
  })
  onConfigChange(v) {
    if (v.default !== undefined) {
      this.allConfig = v;
      if (v.type === 'file') {
        this.params = v.default.filename;
      } else {
        if (this.isPasswordInput) {
          // 密码输入框的情况下无需显示密码内容
          this.params = '';
        } else {
          this.params = v.default;
        }
      }
    }
  }

  @Emit('file-change')
  handleFileChange(file) {
    return file;
  }

  @Emit('error-message')
  handleErrorMessage(msg: string) {
    return msg;
  }

  created() {
    this.passwordInputReadonly = !(this.$route.name === 'collect-config-add'); // 新建时，默认可输入
  }

  beforeDestroy() {
    this.handleDestroyPopover();
  }

  get isPasswordInput() {
    return ['encrypt', 'password'].includes(this.$attrs.type);
  }

  // 密码框的情况下根据是否有密码值判断placeholder的内容，不是密码框则显示默认placeholder '输入'
  get computedPlaceholder() {
    // 首先判断输入框是否为密码框，不是则为默认placeholder"请输入"
    // 然后判断密码框是否已经有值，有值则为"已配置"，无值则为"未配置"
    // 有值的情况下，如果点击了"重置"按钮则显示为"未配置"，并将密码设置成空字符串
    if (this.isPasswordInput) {
      if (this.customPlaceholder) {
        return this.$t(this.customPlaceholder);
      }
      if (this.config.default) {
        if (this.changedPasswordValue) {
          return this.params ? this.$t('已配置') : this.$t('未配置');
        }
        return this.$t('已配置');
      }
      return this.$t('未配置');
    }
    return this.$t('请输入');
  }

  // 处理输入
  handleInput(val: string, evt: any): void {
    // 输入内容的情况下将该值进行清空
    val && (this.customPlaceholder = '');
    this.handleInputEvt(evt);
    this.getOffset();
    if (!this.params || !this.tipsData.find(item => item.name.includes(this.keyword))) {
      return this.handleDestroyPopover();
    }
    this.handlePopoverShow();
  }

  // 处理重置密码，将密码框从只读状态变为可编辑状态，并将密码框绑定的params置空
  handleResetPassword() {
    this.passwordInputReadonly = false;
    this.params = '';
    this.customPlaceholder = '未配置';
    this.changedPasswordValue = true;
    this.$emit('passwordInputName', this.config.name);
    this.emitData(this.params);
  }

  // 处理输入事件数据
  handleInputEvt(evt): void {
    // 最新值
    const { target } = evt;
    const newVal: string = target.value;
    this.getIndex(newVal, this.oldVal);
    this.keyword = this.handleKeyword();
    this.oldVal = newVal;
    this.emitData(newVal);
    // 是密码输入框的情况下，将发生变更的密码框的名字传递给父组件，并将标志位changedPasswordValue设置为true
    if (this.isPasswordInput) {
      this.changedPasswordValue = true;
      this.$emit('passwordInputName', this.config.name);
    }
  }
  // 处理下拉选项类型
  handleSelect(newVal): void {
    this.emitData(newVal);
  }
  // 处理Security联动
  handleSelectSecurity(newVal): void {
    this.emitData(newVal);
    this.$emit('curAuthPriv', newVal);
  }
  handleTagListChange(val: string[]) {
    this.emitData(val);
  }
  handleCodeChange(val: string) {
    this.emitData(val);
  }
  fileChange(e): void {
    if (e.target.files[0]) {
      this.loading = true;
      // eslint-disable-next-line prefer-destructuring
      const file = e.target.files[0];
      const fileName = file.name;
      this.params = fileName;
      const reader = new FileReader();
      reader.readAsText(file, 'gbk');
      reader.onload = ev => {
        // 读取完毕后输出结果
        try {
          const { result } = ev.target;
          this.emitData({ filename: fileName, value: result });
          this.loading = false;
        } catch (e) {
          this.$bkMessage({
            theme: 'error',
            message: e || this.$t('解析文件失败'),
          });
          this.loading = false;
        } finally {
          // eslint-disable-next-line
          this.$refs.upload.value = '';
        }
      };
    }
  }
  // 处理开关
  handleSwitch(newVal): void {
    this.emitData(newVal);
  }

  // 处理关键字
  handleKeyword(): string {
    return this.params
      .slice(this.startIndex, this.curIndex + 1)
      .replace(/({)|(})/g, '')
      .trim();
  }

  // 获取光标的位置
  getIndex(newVal: string, oldVal: string): number {
    const tempStr = newVal.length > oldVal.length ? newVal : oldVal;
    let diffIndex = 0;
    tempStr.split('').find((_item, idx) => {
      diffIndex = idx;
      return oldVal[idx] !== newVal[idx];
    });
    this.curIndex = diffIndex;
    if (newVal[diffIndex] === '{' && newVal[diffIndex - 1] === '{') {
      this.startIndex = diffIndex - 1;
    }
    // 当出现{{{{
    if (this.curIndex) {
      if (newVal.indexOf('{{{{') > -1) {
        this.curIndex = this.curIndex - 2;
        this.startIndex = this.startIndex - 2;
      }
    }
    return diffIndex;
  }

  // 隐藏
  handleDestroyPopover(): void {
    if (this.popoverInstance) {
      this.popoverInstance.hide(0);
      this.popoverInstance.destroy?.();
      this.popoverInstance = null;
    }
  }

  // 提示列表显示方法
  handlePopoverShow(): void {
    // if (!this.$refs.list || this.$refs.wrap) return
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.$refs.wrap, {
        content: this.$refs.list,
        arrow: false,
        flip: false,
        flipBehavior: 'bottom',
        trigger: 'manul',
        placement: 'top-start',
        theme: 'light auto-complete',
        maxWidth: 520,
        duration: [200, 0],
        offset: `${this.offsetX}, ${this.offsetY}`,
      });
    } else {
      // 更新提示的位置
      this.popoverInstance.set({
        offset: `${this.offsetX}, ${this.offsetY}`,
      });
    }
    // 显示
    this.popoverInstance.show(100);
  }

  // 点击选中
  handleMousedown(item: ITipsItem): void {
    const paramsArr = this.params.split('');
    paramsArr.splice(this.startIndex, this.curIndex - this.startIndex + 1, item.name);
    this.params = paramsArr.join('');
    this.$emit('input', this.params);
    this.oldVal = this.params;
  }

  handleSwitchChange() {
    this.$emit('input', this.params);
  }

  // 计算补全列表的offsetX
  getOffset(): void {
    this.$nextTick(() => {
      const ref: any = this.$refs.input;
      const bkInputLeft = ref.$el.getBoundingClientRect().left;
      const inputRectLeft = ref.$el.getElementsByTagName('input')[0].getBoundingClientRect().left;
      this.offsetX = inputRectLeft - bkInputLeft;
    });
  }

  // 发送数据
  emitData(val): void {
    this.$emit('input', val);
    this.$emit('autoHandle', val);
  }
}
</script>

<style lang="scss">
.auto-complete-theme {
  padding: 0;
  font-size: 12px;
  pointer-events: all;
  background-color: transparent;
  border-radius: 0;

  /* stylelint-disable-next-line declaration-no-important */
  box-shadow: none !important;
}
</style>

<style lang="scss" scoped>
@import '../../../../theme/mixin.scss';

.password-input {
  display: flex;
}

.auto-complete-input {
  position: relative;

  .code-select {
    align-items: flex-start;
  }

  .temp-span {
    position: absolute;
    top: 0;
    right: -9999px;
    opacity: 0;
  }

  :deep(.input-text) {
    &.password {
      .control-icon {
        display: none;
      }
    }
  }

  &-list {
    @include template-list;
  }

  &-select {
    display: flex;
    flex-direction: row;
    align-items: center;

    .bk-tooltip {
      margin-right: 10px;
    }

    :deep(.bk-tooltip) {
      margin-right: 0;
    }

    :deep(.prepend-text) {
      position: relative;
      top: 2px;
      padding: 0 20px;
      overflow: hidden;
      text-overflow: ellipsis;
      line-height: 30px;
      white-space: nowrap;
      background: #fafbfd;
      border: 1px solid#c4c6cc;
      border-right: 0;
    }
  }

  .file-input-wrap,
  .switch-input-wrap {
    display: flex;
    align-items: center;
    height: 32px;

    :deep(.prepend-text) {
      padding: 0 20px;
    }

    .prepend {
      flex-shrink: 0;
      height: 30px;
      line-height: 30px;
      // padding: 0 20px;
      background-color: #f2f4f8;
    }

    .file-name {
      display: flex;
      flex: 1;
      align-items: center;
      height: 30px;
    }

    .switch-wrap {
      padding: 0 10px;
    }
  }

  .file-input-wrap {
    .prepend {
      border: 1px solid #c4c6cc;
      border-right: 0;
      border-top-left-radius: 2px;
      border-bottom-left-radius: 2px;
    }

    .auto-complete-input-file {
      position: relative;
      width: 100%;

      &-input {
        position: absolute;
        top: 0;
        right: 0;
        width: 77%;
        height: 100%;
        cursor: pointer;
        opacity: 0;
      }
    }

    .import-file {
      display: flex;
      align-items: center;
      vertical-align: middle;
    }
  }

  .switch-input-wrap {
    border: 1px solid #c4c6cc;

    .prepend {
      border-right: 1px solid #c4c6cc;
    }
  }
}
</style>
<style lang="scss">
.password-input + .tooltips-icon {
  /* stylelint-disable-next-line declaration-no-important */
  right: 80px !important;
}

.auto-complete-input {
  position: relative;

  .code-select {
    align-items: flex-start;

    .prepend-text {
      /* stylelint-disable-next-line declaration-no-important */
      border-right: 1px solid #c4c6cc !important;
    }

    &-editor {
      height: 300px;
      margin-top: 2px;
      margin-left: 4px;
      border: 1px solid #c4c6cc;
    }
  }
}
</style>
