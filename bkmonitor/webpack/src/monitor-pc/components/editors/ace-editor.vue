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
  <div :style="{ height: calcSize(height), width: width }" />
</template>

<script>
export default {
  name: 'AceEditor',
  props: {
    value: {
      type: String,
      default: '',
    },
    width: {
      type: [Number, String],
      default: '100%',
    },
    height: {
      type: [Number, String],
      default: 320,
    },
    lang: {
      type: String,
      default: 'javascript',
    },
    theme: {
      type: String,
      default: 'monokai',
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    fullScreen: {
      type: Boolean,
      default: false,
    },
    hasError: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      $ace: null,
    };
  },
  watch: {
    fullScreen() {
      this.$el.classList.toggle('ace-full-screen');
      this.$ace.resize();
    },
  },
  mounted() {
    const { ace } = window;
    this.$ace = ace.edit(this.$el);
    const { $ace, lang, theme, readOnly } = this;
    $ace.$blockScrolling = Number.POSITIVE_INFINITY;
    $ace.getSession().setMode(`ace/mode/${lang}`);
    $ace.getSession().setNewLineMode('unix');
    $ace.setTheme(`ace/theme/${theme}`);
    $ace.setOptions({
      enableBasicAutocompletion: true,
      enableSnippets: true,
      enableLiveAutocompletion: true,
      fontSize: '12pt',
    });
    $ace.setReadOnly(readOnly); // 设置是否为只读模式
    $ace.setShowPrintMargin(false); // 不显示打印边距
    $ace.setValue(this.value, 1);
    // 绑定输入事件回调
    $ace.on('change', ($editor, $fn) => {
      this.$emit('input', $ace.getValue(), $editor, $fn);
    });

    // $ace.on('blur', ($editor, $fn) => {
    //     var content = $ace.getValue()
    //     // this.$emit('update:hasError', !content)
    //     this.$emit('blur', content, $editor, $fn)
    // })

    // session.on('changeAnnotation', (args, instance) => {
    //     const annotations = instance.$annotations
    //     if (annotations && annotations.length) {
    //         this.$emit('change-annotation', annotations)
    //     }
    // })
  },
  methods: {
    calcSize(size) {
      const _size = size.toString();

      if (_size.match(/^\d*$/)) return `${size}px`;
      if (_size.match(/^[0-9]?%$/)) return _size;

      return '100%';
    },
  },
};
</script>
