/** Backend field metadata retained by field display and sort drafts. */
export interface FieldDefinition {
  field_name: string;
  field_type: string;
  query_alias?: string;
  is_full_text?: boolean;
  es_doc_values?: boolean;
  [property: string]: unknown;
}
export interface FieldView extends FieldDefinition {
  first_name: string;
  last_name: string;
}
export interface FieldTypeStyle {
  color?: string;
  textColor?: string;
  icon?: string;
}
export type SortPair = [string, string];
