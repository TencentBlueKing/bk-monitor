module.exports = {
  root: true,
  env: {
    node: true,
  },
  extends: [
    'plugin:vue/vue3-recommended', // 使用 Vue 3 推荐的规则
    'eslint:recommended',
    'plugin:prettier/recommended', // 加入 Prettier 推荐的规则
  ],
  parserOptions: {
    parser: 'babel-eslint', // 解析器
  },
  rules: {
    // 自定义规则
    'vue/no-unused-vars': 'warn',
    'vue/no-unused-components': 'warn',
    // 其他规则...
  },
};