import { defineComponent, ref } from 'vue';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';
import './grep-cli.scss';

export default defineComponent({
  name: 'GrepView',
  components: {
    GrepCli,
    GrepCliResult,
  },
  setup() {
    const searchValue = ref('');
    const matchMode = ref({
      caseSensitive: false,
      regexMode: false,
      wordMatch: false,
    });
    const currentIndex = ref(0);
    const totalMatches = ref(0);

    // 处理搜索更新
    const handleSearchUpdate = (data: any) => {
      searchValue.value = data.searchValue;
      matchMode.value = data.matchMode;
      if (data.currentIndex) {
        currentIndex.value = data.currentIndex;
      }
    };

    // 处理匹配模式更新
    const handleMatchModeUpdate = (mode: any) => {
      matchMode.value = mode;
    };

    // 处理总匹配数更新
    const handleTotalMatchesUpdate = (total: number) => {
      totalMatches.value = total;
    };

    return () => (
      <div class='grep-view'>
        <GrepCli
          on-search-change={handleSearchUpdate}
          on-match-mode={handleMatchModeUpdate}
        />
        <GrepCliResult
          searchValue={searchValue.value}
          matchMode={matchMode.value}
          currentIndex={currentIndex.value}
          onUpdate:total-matches={handleTotalMatchesUpdate}
        />
      </div>
    );
  },
});
