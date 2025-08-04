<template>
  <bk-dialog
    v-model="isShow"
    width="640"
    :title="$t('预览查询 SQL')"
    class="bv-preview-sql"
    :beforeClose="close"
    header-position="left"
  >
    <template #default>
      <pre class="per" style=" height: 424px; white-space: pre-wrap;background: #f5f7fa">
        <code v-html="$xss(highlightedCode)" class="flex-column" />
        <div class="vertical"></div>
      </pre>
    </template>
    <template #footer>
      <!-- <bk-button @click="copy" theme="primary">{{ $t("复制SQL") }}</bk-button> -->
      <bk-button @click="close">{{ $t("关闭") }}</bk-button>
    </template>
  </bk-dialog>
</template>

<script setup>
import { computed } from "vue";
// import { Button, Dialog, Message } from "bkui-vue";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();
// import hljs from "highlight.js/lib/core";
// import sql from "highlight.js/lib/languages/sql";

// import copyToClipboard from "@/utils/copyToClipboard";

// import "highlight.js/styles/github.css";

// hljs.registerLanguage("sql", sql);

const props = defineProps({
  isShow: {
    type: Boolean,
    default: false,
  },
  sqlContent: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["update:isShow"]);

// const { t } = useI18n();

// Computed property for highlighted code
const highlightedCode = computed(() => {
  // const highlighted = hljs.highlightAuto(props.sql).value;
  const highlighted = props.sqlContent;

  return addLineNumbers(highlighted);
});

// Function to add line numbers to highlighted SQL
function addLineNumbers(highlightedCode) {
  const lines = highlightedCode.split("\n");
  return (
    lines
      .map((line, index) => {
        return `
      <div class="flex-row">
        <span class="sql-line-number">${index + 1}</span>
        <div class="flex-1 pl-min">${line}</div>
      </div>
    `;
      })
      .join("\n")
  );
}

// Function to close the dialog
function close() {
  emit("update:isShow", false);
}

// Function to copy SQL to clipboard
function copy() {
  copyToClipboard(props.sql).catch(() => {
    Message({ theme: "error", message: $t("dashboards.复制失败") });
  });
}
</script>
<style lang="scss">
.flex-row {
  display: flex;

  .sql-line-number {
    z-index: 1;
    display: inline-block;
    width: 35px;
    padding-right: 12px;
    color: #8c8f99;
    text-align: right;
    user-select: none;
    background: #eaebf0;
  }

  .pl-min {
    margin-left: 12px;
    background: var(--dialog-preview-sql-bg);
  }
}

.bv-preview-sql {
  .per {
    position: relative;

    .vertical {
      position: absolute;
      top: 0;
      z-index: 0;
      width: 35px;
      height: 100%;
      background: #eaebf0;
    }
  }

  .bk-dialog-header {
    /* stylelint-disable-next-line declaration-no-important */
    padding: 16px 0 5px 24px !important;
  }

  .flex-column {
    display: flex;
    flex-direction: column;
    margin-top: -15px;
  }
}
</style>
