import type { Editable } from '../api/types'
export type Field = {
  key: string
  label: string
  type?: 'number' | 'switch' | 'textarea' | 'select' | 'group'
  required?: boolean
  options?: { title: string; value: string }[]
  hint?: string
}
export type Config = {
  title: string
  subtitle: string
  fields: Field[]
  defaults: Record<string, unknown>
  columns: { title: string; key: string; sortable: boolean }[]
}
const columns = (items: [string, string][]) =>
  items.map(([title, key]) => ({ title, key, sortable: false }))
const enabled: Field = { key: 'enabled', label: '启用', type: 'switch' }
const group: Field = { key: 'group_id', label: '作用群（留空为全局）', type: 'group' }
const patterns: Field = {
  key: 'patterns',
  label: '匹配表达式',
  type: 'textarea',
  required: true,
  hint: '每行一条；正则模式使用 Python 正则语法',
}
export const configs: Record<Editable, Config> = {
  'recall-admins': {
    title: '批量撤回',
    subtitle:
      '添加可使用 /大记忆清除数 的 QQ 管理员。命令只撤回当前群的最近消息，省略条数默认 500，最多 20000；无法撤回的消息自动跳过。',
    fields: [
      { key: 'user_id', label: 'QQ 号', type: 'number', required: true },
      enabled,
      { key: 'note', label: '备注', type: 'textarea' },
    ],
    defaults: { user_id: 0, enabled: true, note: '' },
    columns: columns([
      ['QQ', 'user_id'],
      ['备注', 'note'],
      ['状态', 'enabled'],
      ['操作', 'actions'],
    ]),
  },
  groups: {
    title: '群配置',
    subtitle: '设置群优先级、容量、QQ 等级门槛和答错自动拉黑。优先级越高，越优先推荐。',
    fields: [
      { key: 'group_id', label: '群号', type: 'number', required: true },
      { key: 'name', label: '群名称' },
      enabled,
      { key: 'priority', label: '优先级', type: 'number' },
      { key: 'max_members', label: '最大成员数（0 表示不限）', type: 'number' },
      { key: 'current_members', label: '当前成员数', type: 'number' },
      { key: 'join_url', label: '入群链接' },
      {
        key: 'min_qq_level',
        label: '最低 QQ 等级（0 表示不限）',
        type: 'number',
        hint: '无法取得等级时拒绝本次申请，不累计答错次数',
      },
      {
        key: 'max_wrong_answers',
        label: '答错拉黑次数（0 表示关闭）',
        type: 'number',
        hint: '本群内达到此次数时加入全局加群黑名单；通过验证或停用黑名单后重新计数',
      },
      {
        key: 'wrong_answer_window_hours',
        label: '答错统计窗口（小时）',
        type: 'number',
        hint: '只统计窗口内的答案错误；等级不足、分流和接口异常不计入',
      },
      {
        key: 'redirect_message_template',
        label: '分流提示模板',
        type: 'textarea',
        hint: '支持 {group_name}、{group_id}、{join_url}',
      },
      { key: 'note', label: '备注', type: 'textarea' },
    ],
    defaults: {
      group_id: 0,
      name: '',
      priority: 100,
      enabled: true,
      max_members: 0,
      current_members: 0,
      join_url: '',
      min_qq_level: 0,
      max_wrong_answers: 0,
      wrong_answer_window_hours: 24,
      redirect_message_template: '请申请推荐群：{group_name}（{group_id}）。入群链接：{join_url}',
      note: '',
    },
    columns: columns([
      ['排序', 'drag'],
      ['群名称', 'name'],
      ['群号', 'group_id'],
      ['优先级', 'priority'],
      ['成员数', 'current_members'],
      ['容量', 'max_members'],
      ['最低等级', 'min_qq_level'],
      ['答错上限', 'max_wrong_answers'],
      ['状态', 'enabled'],
      ['操作', 'actions'],
    ]),
  },
  rules: {
    title: '入群规则',
    subtitle: '按群配置答案匹配规则；留空作用群表示应用到全部群。',
    fields: [
      { key: 'name', label: '规则名称', required: true },
      enabled,
      group,
      {
        key: 'match_mode',
        label: '匹配方式',
        type: 'select',
        options: [
          { title: '包含', value: 'contains' },
          { title: '完全匹配', value: 'exact' },
          { title: '正则', value: 'regex' },
        ],
      },
      {
        key: 'logic_mode',
        label: '表达式关系',
        type: 'select',
        options: [
          { title: '任意匹配（OR）', value: 'any' },
          { title: '全部匹配（AND）', value: 'all' },
        ],
      },
      patterns,
    ],
    defaults: {
      name: '',
      enabled: true,
      group_id: null,
      match_mode: 'contains',
      logic_mode: 'any',
      patterns: '',
    },
    columns: columns([
      ['名称', 'name'],
      ['作用群', 'group_id'],
      ['匹配方式', 'match_mode'],
      ['关系', 'logic_mode'],
      ['表达式', 'patterns'],
      ['状态', 'enabled'],
      ['操作', 'actions'],
    ]),
  },
  blacklist: {
    title: '加群黑名单',
    subtitle: '启用黑名单后，该 QQ 的所有加群申请会被拒绝。',
    fields: [
      { key: 'user_id', label: 'QQ 号', type: 'number', required: true },
      enabled,
      { key: 'reason', label: '拒绝原因', type: 'textarea' },
      { key: 'note', label: '备注', type: 'textarea' },
    ],
    defaults: { user_id: 0, enabled: true, reason: '你已被加入黑名单，无法申请入群。', note: '' },
    columns: columns([
      ['QQ', 'user_id'],
      ['拒绝原因', 'reason'],
      ['备注', 'note'],
      ['状态', 'enabled'],
      ['操作', 'actions'],
    ]),
  },
  whitelist: {
    title: '去重白名单',
    subtitle: '白名单成员以及群主、管理员始终受到去重保护。',
    fields: [
      { key: 'user_id', label: 'QQ 号', type: 'number', required: true },
      enabled,
      { key: 'note', label: '备注', type: 'textarea' },
    ],
    defaults: { user_id: 0, enabled: true, note: '' },
    columns: columns([
      ['QQ', 'user_id'],
      ['备注', 'note'],
      ['状态', 'enabled'],
      ['操作', 'actions'],
    ]),
  },
  moderation: {
    title: '消息审查',
    subtitle: '配置正则、图片 OCR、腾讯云文本审核与 LLM 图片审核，按规则撤回或禁言。',
    fields: [
      { key: 'name', label: '规则名称', required: true },
      enabled,
      group,
      { ...patterns, required: false, hint: '每行一条 Python 正则；只用 LLM 图片审核时可留空' },
      { key: 'cloud_review_enabled', label: '腾讯云 AI 二次审核', type: 'switch' },
      { key: 'ocr_enabled', label: '图片 OCR', type: 'switch' },
      { key: 'image_review_enabled', label: 'LLM 多模态图片审核（无需正则命中）', type: 'switch' },
      {
        key: 'action',
        label: '处理动作',
        type: 'select',
        options: [
          { title: '撤回', value: 'recall' },
          { title: '禁言', value: 'mute' },
          { title: '撤回并禁言', value: 'recall_and_mute' },
        ],
      },
      { key: 'mute_duration_seconds', label: '禁言秒数', type: 'number', required: true },
      { key: 'note', label: '备注', type: 'textarea' },
    ],
    defaults: {
      name: '',
      enabled: true,
      group_id: null,
      patterns: '',
      cloud_review_enabled: false,
      ocr_enabled: false,
      image_review_enabled: false,
      action: 'recall',
      mute_duration_seconds: 600,
      note: '',
    },
    columns: columns([
      ['名称', 'name'],
      ['作用群', 'group_id'],
      ['表达式', 'patterns'],
      ['AI 审核', 'cloud_review_enabled'],
      ['OCR', 'ocr_enabled'],
      ['图片审核', 'image_review_enabled'],
      ['动作', 'action'],
      ['状态', 'enabled'],
      ['操作', 'actions'],
    ]),
  },
}
