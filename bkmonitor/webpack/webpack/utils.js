const transformDistDir = app => {
  switch (app) {
    case 'mobile':
      return 'weixin';
    case 'fta':
    case 'apm':
    case 'email':
    case 'trace':
    case 'external':
      return app;
    default:
      return 'monitor';
  }
};
const transformAppDir = app => {
  switch (app) {
    case 'mobile':
      return 'monitor-mobile';
    case 'fta':
      return 'fta-solutions';
    case 'apm':
      return 'apm';
    case 'trace':
      return 'trace';
    default:
      return 'monitor-pc';
  }
};
const mobileBuildVariates = `
<script>
    window.site_url = "\${WEIXIN_SITE_URL}"
    window.static_url = "\${WEIXIN_STATIC_URL}"
    window.cc_biz_id = \${BK_BIZ_ID}
    window.user_name = "\${UIN}"
    window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
    window.csrf_token = "\${csrf_token}"
    window.userInfo = {
        username: "\${UIN}",
        isSuperuser: \${IS_SUPERUSER},
    }
    window.ageisId = "\${TAM_ID}"
    window.graph_watermark = "\${GRAPH_WATERMARK}" == "True" ? true : false
</script>`;

const pcBuildVariates = `
<script>
window.site_url = "\${SITE_URL}"
window.static_url = "\${STATIC_URL}"
window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
</script>`;

const externalBuildVariates = `
<script>
<%
import json
def to_json(val):
    return json.dumps(val)
%>
window.site_url = "\${SITE_URL}"
window.static_url = "\${STATIC_URL}"
window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
window.bk_biz_ids = \${to_json(BK_BIZ_IDS) | n}
</script>`;

module.exports = {
  transformDistDir,
  transformAppDir,
  mobileBuildVariates,
  pcBuildVariates,
  externalBuildVariates,
};
