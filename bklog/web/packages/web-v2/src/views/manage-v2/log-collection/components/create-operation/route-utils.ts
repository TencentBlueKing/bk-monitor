export const COLLECTION_EDIT_ROUTES = ['collectEdit', 'collectField', 'collectStorage'] as const;

export const isCollectionEditRoute = (routeName: unknown) => {
  return COLLECTION_EDIT_ROUTES.includes(String(routeName ?? '') as (typeof COLLECTION_EDIT_ROUTES)[number]);
};
