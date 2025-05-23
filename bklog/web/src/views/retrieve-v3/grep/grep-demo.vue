<template>
  <div class="grep-demo">
    <h2>Grep 语法高亮演示</h2>

    <div class="demo-section">
      <h3>1. 基础命令高亮</h3>
      <GrepCliEditor
        v-model:value="examples.basic"
        placeholder="输入 grep 命令..."
        height="40px"
        :enable-syntax-highlight="true"
      />
      <p class="example-desc">高亮 grep/egrep 命令关键字</p>
    </div>

    <div class="demo-section">
      <h3>2. 参数高亮</h3>
      <GrepCliEditor
        v-model:value="examples.arguments"
        placeholder="输入带参数的 grep 命令..."
        height="40px"
        :enable-syntax-highlight="true"
      />
      <p class="example-desc">高亮 -i, -v, -E 等参数</p>
    </div>

    <div class="demo-section">
      <h3>3. 字符串高亮</h3>
      <GrepCliEditor
        v-model:value="examples.strings"
        placeholder="输入带引号的搜索模式..."
        height="40px"
        :enable-syntax-highlight="true"
      />
      <p class="example-desc">高亮双引号和单引号字符串</p>
    </div>

    <div class="demo-section">
      <h3>4. 转义字符高亮</h3>
      <GrepCliEditor
        v-model:value="examples.escapes"
        placeholder="输入包含转义字符的模式..."
        height="40px"
        :enable-syntax-highlight="true"
      />
      <p class="example-desc">高亮 \n, \t, \", \' 等转义字符</p>
    </div>

    <div class="demo-section">
      <h3>5. 管道符组合</h3>
      <GrepCliEditor
        v-model:value="examples.pipes"
        placeholder="输入管道组合命令..."
        height="40px"
        :enable-syntax-highlight="true"
      />
      <p class="example-desc">高亮管道符和复杂组合命令</p>
    </div>

    <div class="demo-section">
      <h3>6. 正则模式高亮</h3>
      <GrepCliEditor
        v-model:value="examples.regex"
        placeholder="输入正则表达式模式..."
        height="40px"
        :enable-syntax-highlight="true"
      />
      <p class="example-desc">高亮未加引号的正则模式</p>
    </div>

    <div class="demo-section">
      <h3>7. 复杂示例</h3>
      <GrepCliEditor
        v-model:value="examples.complex"
        placeholder="输入复杂的 grep 命令..."
        height="60px"
        :enable-syntax-highlight="true"
        auto-height
        max-height="120px"
      />
      <p class="example-desc">综合展示所有语法高亮功能</p>
    </div>

    <div class="demo-section">
      <h3>8. 语法对比 (无高亮)</h3>
      <GrepCliEditor
        v-model:value="examples.complex"
        placeholder="无语法高亮版本..."
        height="60px"
        :enable-syntax-highlight="false"
        auto-height
        max-height="120px"
      />
      <p class="example-desc">对比效果 - 关闭语法高亮</p>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { reactive } from 'vue';
  import GrepCliEditor from './grep-cli-editor';

  const examples = reactive({
    basic: 'grep "error" | egrep "warning"',
    arguments: 'grep -i -v "debug" | egrep -E "critical"',
    strings: 'grep "hello world" | grep \'single quotes\' | grep mixed',
    escapes: 'grep "hello\\"world" | grep \'line\\nbreak\' | grep tab\\tchar',
    pipes: 'grep -v "info" | egrep -i "error" | grep "failed"',
    regex: 'egrep [0-9]{3}-[A-Z]{2} | grep https?:// | grep \\w+@\\w+\\.\\w+',
    complex: `grep -i "connection" | egrep -v "success|ok" | grep "timeout\\|error"`,
  });
</script>

<style scoped>
  .grep-demo {
    padding: 20px;
    max-width: 1000px;
    margin: 0 auto;
  }

  .demo-section {
    margin-bottom: 30px;
    padding: 15px;
    border: 1px solid #e1e1e1;
    border-radius: 8px;
    background-color: #fafafa;
  }

  .demo-section h3 {
    margin: 0 0 15px 0;
    color: #333;
    font-size: 16px;
    font-weight: 600;
  }

  .example-desc {
    margin: 10px 0 0 0;
    color: #666;
    font-size: 14px;
    font-style: italic;
  }

  h2 {
    text-align: center;
    color: #333;
    margin-bottom: 30px;
  }
</style>
