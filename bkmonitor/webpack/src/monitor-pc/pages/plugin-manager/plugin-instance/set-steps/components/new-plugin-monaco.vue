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
  <div class="plugin-monaco">
    <div v-show="type === 'Script'">
      <div
        ref="systemList"
        class="system-list"
      >
        <div
          v-for="(sys, index) in systemList"
          :key="index"
          class="item"
          :class="{ active: sys.name === selectedSystem.name }"
          @click="handleActiveTab(sys)"
        >
          <div class="switch-wrapper">
            <bk-switcher
              v-model="sys.enable"
              size="small"
              theme="primary"
              @change="handleSelectSwitch"
            />
          </div>
          {{ sys.name }}
        </div>
      </div>
      <ul class="language-list">
        <li
          v-for="(lang, index) in currentLanguageList"
          :key="index"
          :class="{ item: true, active: lang.name === currentLanguage.name }"
          @click="handleLangChange(lang)"
        >
          {{ lang.name }}
        </li>
      </ul>
    </div>
    <div class="conent-wrapper">
      <div class="monaco-editor">
        <monaco-editor
          ref="pluginMonaco"
          :width="editorWidth"
          :language="replacedCurrentLanguage"
          :value="currentLanguage.text"
          :full-screen="true"
          @change="handleInput"
        />
      </div>
      <div
        v-show="type === 'Script'"
        :class="{ 'editor-side-notice': true, 'require-content': sideNotice.left }"
      >
        <div
          class="side-btn"
          @click="handleSideNotice"
        >
          <i :class="['bk-icon', sideNotice.left ? 'icon-angle-double-right' : 'icon-angle-double-left']" />
          <!-- <span class="side-btn-message"> {{ $t('上报格式说明') }} </span> -->
        </div>
        <div
          v-show="sideNotice.left"
          class="side-notice"
        >
          <shell-side-notice />
        </div>
      </div>
      <div
        v-if="!selectedSystem.enable && !isOther"
        class="enable-mask"
      >
        <div
          ref="switchTips"
          class="switch-popvoer"
        >
          <span class="text">{{ $t('是否启用{0}脚本采集?', [selectedSystem.name]) }}</span>
          <span
            class="open-btn"
            @click="handleSwitchChange"
            >{{ $t('启用') }}</span
          >
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import { debounce } from 'throttle-debounce';

import MonacoEditor from '../../../../../components/editors/monaco-editor.vue';
import ShellSideNotice from '../../../../shell-collector/set-data-source/set-data-steps/shell-side-notice.vue';

import type MonitorVue from '../../../../../types/index';
import type { ILanguage, ISystem, IValues } from '../../../../../types/plugin-manager/index';

const descPanelWidth = 368;
const expandedElWidth = 25;
@Component({
  components: {
    MonacoEditor,
    ShellSideNotice,
  },
})
export default class NewPluginMonaco extends Vue<MonitorVue> {
  languageList: ILanguage[] = [
    {
      name: 'Shell',
      lang: 'shell',
      text:
        '#!/bin/sh\n' +
        '#\n' +
        'export LC_ALL=C\n' +
        'export LANG=C\n' +
        '#default language is C \n' +
        '#\n' +
        '# Text format:\n' +
        '# metric_name{label_name="lable_value"} metric_value timestamp\n' +
        '#\n' +
        '# Example:\n' +
        '# echo "disk_usage{disk_name=\\"/data\\"} 0.8"\n',
      abb: 'sh',
      active: false,
    },
    {
      name: 'Bat',
      lang: 'bat',
      abb: 'bat',
      text:
        '::\n' +
        ':: Text format:\n' +
        ':: metric_name{label_name="lable_value"} metric_value timestamp\n' +
        '::\n' +
        ':: Example:\n' +
        ':: echo disk_usage{disk_name=\\"/data\\"} 0.8\n',
      active: false,
    },
    {
      name: 'Python',
      lang: 'python',
      abb: 'py',
      text:
        '#!/usr/bin/env python\n' +
        '#\n' +
        '# Text format:\n' +
        '# metric_name{label_name="lable_value"} metric_value timestamp\n' +
        '#\n' +
        '# Example:\n' +
        '# print("disk_usage{disk_name=\\"/data\\"} 0.8")\n',
      active: false,
    },
    {
      name: 'Perl',
      lang: 'perl',
      abb: 'pl',
      text:
        '#!/usr/bin/env perl\n' +
        '#\n' +
        '# Text format:\n' +
        '# metric_name{label_name="lable_value"} metric_value timestamp\n' +
        '#\n' +
        '# Example:\n' +
        '# print "disk_usage{disk_name=\\"/data\\"} 0.8;"\n',
      active: false,
    },
    {
      name: 'Powershell',
      lang: 'powershell',
      abb: 'ps1',
      text:
        '#\n' +
        '# Text format:\n' +
        '# metric_name{label_name="lable_value"} metric_value timestamp\n' +
        '#\n' +
        '# Example:\n' +
        '# write-host "disk_usage{disk_name=`"/data`"} 0.8"\n',
      active: false,
    },
    {
      name: 'Vbs',
      lang: 'vbs',
      abb: 'vbs',
      text:
        "'\n" +
        "' Text format:\n" +
        '\' metric_name{label_name="lable_value" metric_value timestamp\n' +
        "'\n" +
        "' Example:\n" +
        '\' wscript.echo "disk_usage{disk_name=\\"/data\\"} 0.8\'\n',
      active: false,
    },
    {
      name: 'Custom',
      lang: 'custom',
      abb: '',
      text: '',
      active: false,
    },
  ];

  systemList: ISystem[] = [];
  selectedSystem: ISystem = { name: '', enable: true, languageList: [] };
  editorInstance = null;
  sideNotice: { left: boolean; width: number } = {
    left: true,
    width: 368,
  };

  otherPluginType: string[] = ['JMX', 'DataDog'];
  otherLanguage: { DataDog: ILanguage; JMX: ILanguage } = { JMX: null, DataDog: null };
  handleInput = debounce(300, (text: string) => this.scriptChange(text));
  // 传进来的系统列表
  @Prop(Array)
  systems: string[];

  @Prop(Object)
  value: IValues;

  @Prop(Number)
  width: number;

  @Prop({ type: String, default: 'Script' })
  type: string;

  @Prop({ type: String, default: 'create ' }) mode; // 新建编辑模式 create | edit

  // 当前系统下的语言列表
  get currentLanguageList(): ILanguage[] {
    if (this.otherPluginType.includes(this.type)) {
      return [];
    }
    return this.selectedSystem.languageList;
  }

  get replacedCurrentLanguage(): string {
    // 由于服务端要求提交参数需要调整，这里做一次映射。
    const languageMapping = {
      // Monaco Editor 需要 vb 参数才能高亮。
      vbs: 'vb',
    };
    return languageMapping[this.currentLanguage.lang] ?? this.currentLanguage.lang;
  }

  // 当前语言
  get currentLanguage(): ILanguage | { lang: ''; text: '' } {
    if (this.otherPluginType.includes(this.type)) {
      return this.otherLanguage[this.type];
    }
    return this.currentLanguageList.find(item => item.active) || { text: '', lang: '' };
  }

  get editorWidth(): number {
    return this.type === 'Script' ? this.width - this.sideNotice.width : this.width;
  }

  get isOther(): boolean {
    return ['JMX', 'DataDog'].includes(this.type);
  }

  @Watch('type')
  onTypechange(type: string): void {
    // 处理宽度未变化，插件类型发生变化没有重新布局的bug
    if (['Script', 'JMX', 'DataDog'].includes(type)) {
      this.editorInstance.layout();
    }
  }

  @Watch('systems')
  onSystemListChange(systems: string[]): void {
    if (systems.length) {
      systems.forEach(sys => {
        let languageList: ILanguage[] = [];
        languageList = this.languageList
          .filter(lang => sys === 'windows' || !['Yaml', 'Bat', 'Powershell', 'Vbs'].includes(lang.name))
          .map(lang => ({ ...lang }));
        if (languageList.length) {
          languageList[0].active = true;
        }
        this.systemList.push({ name: sys, enable: false, languageList });
      });
      this.selectedSystem = this.systemList[0];
      this.mode === 'create' && (this.selectedSystem.enable = true);
    }
  }

  @Watch('value', { deep: true })
  onValueChange(val) {
    this.setEditData(val);
  }

  @Watch('editorWidth')
  onEditorWidth() {
    this.$nextTick(() => {
      this.editorInstance.layout();
    });
  }

  created() {
    const language: ILanguage = {
      name: 'Yaml',
      lang: 'yaml',
      abb: 'yaml',
      text:
        'username: {{ username }}\n' +
        'password: {{ password }}\n' +
        'jmxUrl: {{ jmx_url }}\n' +
        'ssl: false\n' +
        'startDelaySeconds: 0\n' +
        'lowercaseOutputName: true\n' +
        'lowercaseOutputLabelNames: true\n' +
        'whitelistObjectNames: ["java.lang:*"]\n',
      active: true,
    };
    this.otherLanguage.JMX = { ...language };
    this.otherLanguage.DataDog = { ...language, text: '' };
  }

  mounted() {
    this.editorInstance = (this.$refs.pluginMonaco as MonacoEditor).getMonaco();
  }

  beforeDestroy() {
    this.editorInstance && (this.editorInstance = null);
  }

  /**
   * @description 激活对应的tab
   */
  handleActiveTab(sys: ISystem): void {
    this.selectedSystem = sys;
    if (!sys.enable) {
      this.handleShow(sys);
    }
  }

  /**
   * @description 显示遮罩
   */
  handleShow(sys: ISystem): void {
    this.selectedSystem = sys;
    if (sys.enable) {
      sys.enable = false;
    }
  }

  handleSelectSwitch() {
    this.$emit('switcher-change', this.systemList);
  }
  handleSwitchChange() {
    this.selectedSystem.enable = true;
    this.handleSelectSwitch();
  }

  /**
   * @description 切换语言
   */
  handleLangChange(lang: ILanguage): void {
    this.currentLanguageList.forEach(item => {
      item.active = item.name === lang.name;
    });
  }

  /**
   * @description 展开收起说明面板
   */
  handleSideNotice() {
    this.sideNotice.left = !this.sideNotice.left;
    this.sideNotice.width = this.sideNotice.left ? descPanelWidth : expandedElWidth;
    this.updateLayout();
  }

  /**
   * @description 更新布局
   */
  updateLayout() {
    this.$nextTick(() => {
      this.editorInstance.layout();
    });
  }

  /**
   * @description 脚本内容变化
   */
  scriptChange(text: string) {
    this.currentLanguage.text = text;
  }

  /**
   * @description 检查脚本内容是否为空
   * @param { ISystem } sys
   */
  checkScriptContent(sys: ISystem): { empty: boolean; lang: ILanguage | undefined; system: string } {
    const lang = sys.languageList.find(lang => lang.active);
    if (lang && !lang.text) {
      const timer: number = setTimeout(() => {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('{0}的{1}脚本内容不能为空', [sys.name, lang.name]),
        });
        clearTimeout(timer);
      });
      return { lang, empty: false, system: sys.name };
    }
    return { lang, empty: true, system: sys.name };
  }

  /**
   * @description 获取其他类型的脚本内容
   */
  getOtherScriptContent(): false | ILanguage {
    const lang: ILanguage = this.otherLanguage[this.type];
    if (!lang.text) {
      this.$bkMessage({ theme: 'error', message: `${this.type}的脚本内容不能为空` });
    }
    return lang || false;
  }

  /**
   * @description 获取脚本内容
   */
  getScriptContents(): false | ILanguage[] {
    if (this.isOther) {
      const result = this.getOtherScriptContent();
      return result ? [result] : false;
    }
    const errors: boolean[] = [];
    const langs = [];
    this.systemList.forEach(sys => {
      if (sys.enable) {
        const result = this.checkScriptContent(sys);
        errors.push(result.empty);
        langs.push(result);
      }
    });
    if (!langs.length) {
      this.$bkMessage({ theme: 'error', message: this.$t('必须开启一个采集脚本') });
      return false;
    }
    return errors.includes(false) ? false : langs;
  }

  /**
   * @description
   * @param values
   */
  setEditData(values: IValues) {
    if (!values) return;
    if (this.isOther) {
      this.otherLanguage[this.type].text = values[this.type].text;
    } else {
      this.systemList.forEach(sys => {
        const value = values[sys.name];
        if (value) {
          sys.enable = !!values[sys.name];
          sys.languageList.forEach(item => {
            if (item.lang === value.lang) {
              item.text = value.text;
              item.active = true;
            } else {
              item.active = false;
            }
          });
        }
      });
      JSON.stringify(values) !== '{}' && (this.selectedSystem = this.systemList.find(item => item.enable));
    }
  }
}
</script>
<style lang="scss" scoped>
.plugin-monaco {
  overflow: hidden;

  .system-list {
    display: flex;
    background: #f5f7fa;
    border: 1px solid #dcdee5;
    border-radius: 2px;

    .item {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 30px;
      padding: 0 21px;
      font-size: 12px;
      color: #63656e;
      cursor: pointer;
      border-right: 1px solid #dcdee5;

      .switch-wrapper {
        position: relative;
        z-index: 9;
        display: inline-block;
        margin-right: 10px;
      }

      .bk-switcher-min {
        z-index: 1;
        margin-right: 6px;
      }
    }

    .active {
      position: relative;
      background-color: #fff;

      &::after {
        position: absolute;
        top: -1px;
        left: -1px;
        display: inline-block;
        width: calc(100% + 2px);
        content: '';
        border-top: 2px solid #3a84ff;
      }
    }
  }

  .language-list {
    display: flex;
    background: #202024;

    .item {
      width: 69px;
      height: 32px;
      font-size: 12px;
      line-height: 32px;
      color: #979ba5;
      text-align: center;
      cursor: pointer;
      border-right: 1px solid #3b3c42;
    }

    .active {
      position: relative;
      color: #fff;
      border-top: 2px solid #3a84ff;
    }
  }

  .conent-wrapper {
    position: relative;
    display: flex;

    .monaco-editor {
      flex: 1;
    }

    .editor-side-notice {
      display: flex;
      flex: 0 0 25px;

      &.require-content {
        flex: 0 0 368px;
      }

      .side-btn {
        width: 25px;
        height: 320px;
        padding-top: 140px;
        font-size: 12px;
        color: #fff;
        text-align: center;
        cursor: pointer;
        background: #46464c;

        &-message {
          display: inline-block;
          width: 14px;
          margin-top: 5px;
        }
      }

      .side-notice {
        flex: 1;
        height: 320px;
        overflow: auto;
      }
    }

    .enable-mask {
      position: absolute;
      top: -32px;
      left: 0;
      z-index: 10;
      width: 100%;
      height: calc(100% + 32px);
      text-align: center;
      background: #313238;
      opacity: 0.9;
    }
  }

  :deep(.shell-side-notice) {
    width: 339px;
  }
}

.switch-popvoer {
  display: inline-block;
  width: 280px;
  height: 32px;
  margin-top: 16px;
  font-size: 12px;
  line-height: 32px;
  color: #c4c6cc;
  background: #3b3c42;
  opacity: 1;

  .text {
    padding-right: 39px;
    padding-left: 16px;
  }

  .open-btn {
    display: inline-block;
    width: 66px;
    color: #3a84ff;
    text-align: center;
    cursor: pointer;
    border-left: 1px solid #313238;
  }
}
</style>
