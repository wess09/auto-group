import {
  mdiViewDashboardOutline,
  mdiAccountGroupOutline,
  mdiShieldCheckOutline,
  mdiAccountCancelOutline,
  mdiMessageAlertOutline,
  mdiBullhornOutline,
  mdiFolderOutline,
  mdiStarOutline,
  mdiAccountMultipleRemoveOutline,
  mdiTextBoxOutline,
  mdiProgressClock,
  mdiOpenInNew,
} from '@mdi/js'
import { adminBase, adminPath } from '../adminRoute'
export const adminMenuItems = [
  { path: adminBase, title: '仪表盘', icon: mdiViewDashboardOutline, affix: true },
  { path: adminPath('groups'), title: '群配置', icon: mdiAccountGroupOutline },
  { path: adminPath('rules'), title: '入群规则', icon: mdiShieldCheckOutline },
  { path: adminPath('join-blacklist'), title: '加群黑名单', icon: mdiAccountCancelOutline },
  { path: adminPath('message-moderation'), title: '消息审查', icon: mdiMessageAlertOutline },
  { path: adminPath('notices'), title: '公告管理', icon: mdiBullhornOutline },
  { path: adminPath('files'), title: '群文件', icon: mdiFolderOutline },
  { path: adminPath('essence'), title: '精华管理', icon: mdiStarOutline },
  { path: adminPath('dedupe'), title: '一键去重', icon: mdiAccountMultipleRemoveOutline },
  { path: adminPath('events'), title: '事件日志', icon: mdiTextBoxOutline },
  { path: adminPath('jobs'), title: '后台任务', icon: mdiProgressClock },
  { path: '/join', title: '公开入口', icon: mdiOpenInNew },
]
export function titleByPath(path: string) {
  return adminMenuItems.find((item) => item.path === path)?.title || 'Auto Group'
}
