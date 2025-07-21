<script setup>
import { EditorView, minimalSetup } from 'codemirror';
import { EditorState } from '@codemirror/state';
import { json } from '@codemirror/lang-json';
import { foldGutter } from '@codemirror/language';
import { jsonValue } from './data';
import { onMounted, ref } from 'vue';

const refRoot = ref(null);
let instance = null;
const createEditor = () => {
  instance = new EditorView({
    parent: refRoot.value,
    doc: jsonValue,
    extensions: [
      minimalSetup,
      json(),
      foldGutter({
        openText: '-',
        closedText: '+',
      }),
      EditorState.readOnly.of(true),
    ],
  });
};

onMounted(() => {
  createEditor();
});
</script>
<template>
  <div class="playground-container">
    <div ref="refRoot"></div>
  </div>
</template>
<style lang="scss" scoped>
  .playground-container {
    height: calc(100vh - 60px);
    overflow: auto;
  }
</style>
