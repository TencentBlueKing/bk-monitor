import { defineConfig } from 'taze';

export default defineConfig({
  recursive: true,
  packageMode: {
    'eslint-plugin-perfectionist': 'minor',
    'bk-magic-vue': 'minor',
    'monaco-editor': 'minor',
    vue: 'minor',
    'vue-class-component': 'minor',
    'vue-property-decorator': 'minor',
    'vue-tsx-support': 'minor',
    'vue-i18n': 'minor',
    'vue-router': 'minor',
    vuex: 'minor',
    'vuex-module-decorators': 'minor',
    axios: 'minor',
    '@antv/g6': 'minor',
    vant: 'minor',
    'async-validator': 'minor',
    'memoize-one': 'minor',
    reselect: 'minor',
  },
  depFields: {
    overrides: false,
  },
});
