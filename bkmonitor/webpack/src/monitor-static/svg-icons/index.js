import Vue from 'vue';
import SvgIcon from '../../monitor-pc/components/svg-icon/svg-icon.vue';
// register globally
Vue.component('svg-icon', SvgIcon);
const req = require.context('./icons', false, /\.svg$/);
const requireAll = requireContext => requireContext.keys().map(requireContext);
requireAll(req);
