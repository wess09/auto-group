export type DataRow = { id: number; [key: string]: unknown }
export type GroupOption = { id: number; group_id: number; name: string; enabled: boolean }
export type PageResult<T> = { items: T[]; total: number; page: number; page_size: number }
export type PageInput = {
  page?: number
  page_size?: number
  q?: string
  group_id?: number
  enabled?: boolean
  status?: string
  job_id?: number
  start_date?: string
  end_date?: string
}
export type Selection = {
  mode: 'ids' | 'all_matching'
  ids: number[]
  q: string
  excluded_ids: number[]
  enabled?: boolean
}
export const emptySelection = (): Selection => ({ mode: 'ids', ids: [], q: '', excluded_ids: [] })
export type JobRef = { id: number; kind: string; status: string }
export type JobOut = JobRef & { summary: Record<string, unknown>; dedupe_job_id: number | null }
export type JobInput = {
  selection?: Selection
  group_id?: number
  job_id?: number
  content?: string
  file_path?: string
  name?: string
  folder_id?: string
  file_id?: string
  busid?: number
  notice_id?: string
  message_id?: number
  new_name?: string
  current_parent_directory?: string
}
export type BrowseEntry = {
  type: 'folder' | 'file'
  name: string
  folder_id?: string
  file_id?: string
  busid?: number
  size?: number
  upload_time?: number
}
export type CloudConfig = {
  secret_id: string
  secret_key_configured: boolean
  region: string
  biz_type: string
  source_language: string
  timeout_seconds: number
}
export type Summary = Record<
  | 'groups'
  | 'enabled_groups'
  | 'total_members'
  | 'join_requests'
  | 'leave_events'
  | 'announcements'
  | 'files'
  | 'essence_messages'
  | 'today_join_requests'
  | 'today_leave_events'
  | 'today_admin_actions'
  | 'today_messages'
  | 'today_active_members',
  number
>
export type Trend = {
  date: string
  messages: number
  admin_actions: number
  join_requests: number
  leave_events: number
}
export type Resource =
  | 'groups'
  | 'rules'
  | 'blacklist'
  | 'moderation'
  | 'whitelist'
  | 'recall-admins'
  | 'notices'
  | 'essence'
  | 'files'
  | 'joins'
  | 'leaves'
  | 'audits'
  | 'actions'
  | 'jobs'
  | 'job-items'
export type Editable =
  'groups' | 'rules' | 'blacklist' | 'moderation' | 'whitelist' | 'recall-admins'
export type JobKind =
  | 'groups.sync'
  | 'notices.sync'
  | 'notices.send'
  | 'notices.delete'
  | 'essence.sync'
  | 'essence.create'
  | 'essence.delete'
  | 'files.sync'
  | 'files.distribute'
  | 'files.delete'
  | 'files.rename'
  | 'files.rename-folder'
  | 'dedupe.preview'
  | 'dedupe.execute'
type Method<P, R> = { params: P; result: R }
export type ApiMethods = {
  [K in Resource as `${K}.list`]: Method<PageInput, PageResult<ResourceRows[K]>>
} & {
  [K in Exclude<Resource, 'jobs'> as `${K}.get`]: Method<{ id: number }, ResourceDetails[K]>
} & {
  [K in Editable as `${K}.create`]: Method<
    { data: ResourceInputs[K]['create'] },
    ResourceDetails[K]
  >
} & {
  [K in Editable as `${K}.update`]: Method<
    { id: number; data: ResourceInputs[K]['update'] },
    ResourceDetails[K]
  >
} & {
  [K in `${Editable}.delete`]: Method<{ id: number }, { ok: boolean }>
} & {
  [K in JobKind]: Method<JobInput, JobRef>
} & {
  'groups.options': Method<PageInput, PageResult<GroupOption>>
  'groups.move': Method<{ group_id: number; position: number }, { ok: boolean }>
  'files.browse': Method<
    PageInput & { group_id: number; folder_id?: string },
    PageResult<BrowseEntry>
  >
  'files.url': Method<{ group_id: number; file_id: string; busid: number }, { url: string }>
  'jobs.get': Method<{ id: number }, JobOut>
  'jobs.actions': Method<PageInput, PageResult<ResourceRows['actions']>>
  'jobs.findByRequestId': Method<{ request_id: string }, JobRef | null>
  'cloud.get': Method<Record<string, never>, CloudConfig>
  'cloud.update': Method<
    Omit<CloudConfig, 'secret_key_configured'> & { secret_key: string },
    CloudConfig
  >
  'image-review.get': Method<Record<string, never>, ImageReviewConfigOut>
  'image-review.update': Method<ImageReviewConfigIn, ImageReviewConfigOut>
  'dashboard.summary': Method<Record<string, never>, Summary>
  'dashboard.trends': Method<Record<string, never>, { items: Trend[] }>
  'dashboard.breakdown': Method<
    Record<string, never>,
    { items: { result: string; count: number }[] }
  >
  'dashboard.rankings': Method<
    Record<string, never>,
    {
      top_groups: ResourceRows['groups'][]
      active_groups: {
        group_id: number
        name: string
        message_count: number
        active_members: number
      }[]
      active_members: {
        group_id: number
        user_id: number
        nickname: string
        message_count: number
      }[]
    }
  >
  'dashboard.recent': Method<
    Record<string, never>,
    { leaves: ResourceRows['leaves'][]; audits: ResourceRows['audits'][] }
  >
}
import type { ResourceRows, ResourceDetails, ResourceInputs } from './generated'
import type { ImageReviewConfigIn, ImageReviewConfigOut } from './generated'
export type { ResourceRows, ResourceDetails, ResourceInputs } from './generated'
