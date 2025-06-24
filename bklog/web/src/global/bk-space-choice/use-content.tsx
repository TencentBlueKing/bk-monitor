import { defineComponent } from "vue";
import List from '../biz-select/list';
import './use-content.scss';
import { ref, onMounted } from "vue";

export default defineComponent({
  name: 'BizMenuContent',
  props: {
    theme: {
      type: String,
      default: 'dark'
    },
    isExpand: {
      type: Boolean,
      default: true
    },
    showBizList: {
      type: Boolean,
      default: false
    },
    keyword: {
      type: String,
      default: ''
    },
    showSpaceTypeIdList: {
      type: Boolean,
      default: false
    },
    spaceTypeIdList: {
      type: Array,
      default: () => []
    },
    searchTypeId: {
      type: String,
      default: ''
    },
    generalList: {
      type: Array,
      default: () => []
    },
    groupList: {
      type: Array,
      default: () => []
    },
    canSetDefaultSpace: {
      type: Boolean,
      default: true
    },
    localValue: {
      type: String,
      default: ''
    },
    bizBoxWidth: {
      type: Number,
      default: 320
    },
    isExternal: {
      type: Boolean,
      default: false
    },
    demoUid: {
      type: String,
      default: ''
    }
  },
  emits: [
    'handleBizSearchDebounce',
    'handleSearchType',
    'handleScroll',
    'handleClickOutSide',
    'handleClickMenuItem',
    'experienceDemo'
  ],
  setup(props, { emit }) {
    // 聚焦输入框
    const menuSearchInputRef = ref();
    const menuSearchInput = () => {
      setTimeout(() => {
        menuSearchInputRef.value?.focus();
      }, 100);
    };

    return () => (
      props.isExpand && (
        <div
          style={{ display: props.showBizList ? 'flex' : 'none' }}
          class="menu-select-list"
        >
          {/* 业务搜索框 */}
          <bk-input
            ref={menuSearchInputRef}
            class="menu-select-search"
            clearable={false}
            placeholder="搜索"
            value={props.keyword}
            left-icon="bk-icon icon-search"
            onChange={(val: string) => emit('handleBizSearchDebounce', val)}
            onClear={() => emit('handleBizSearchDebounce')}
          />
          {/* space空间选择栏 */}
          
          {/* 业务列表 */}
        </div>
      )
    );
  }
});