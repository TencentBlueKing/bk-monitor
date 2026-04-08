import $http from '../../api';

export function reportRouteLog(params: Record<string, any>, state: any) {
  const { bkBizId, spaceUid, mySpaceList: spaceList } = state;

  if (!(bkBizId || spaceUid)) {
    return;
  }
  const username = state.userMeta?.username;
  const space = spaceList?.find(item => item.space_uid === spaceUid);
  $http
    .request(
      'report/frontendEventReport',
      {
        data: {
          event_name: '用户运营数据',
          event_content: '基于前端路由的运营数据上报',
          target: 'bk_log',
          timestamp: Date.now(),
          dimensions: {
            space_id: space?.space_uid || bkBizId,
            space_name: space?.space_name || bkBizId,
            user_name: username,
            version: localStorage.getItem('retrieve_version') || 'v3',
            ...params,
          },
        },
      },
      {
        catchIsShowMessage: false,
      },
    )
    .catch(() => false);
}
