import { defineComponent } from 'vue';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';

export default defineComponent({
  setup() {
    return () => (
      <div>
        <GrepCli />
        <GrepCliResult></GrepCliResult>
      </div>
    );
  },
});
