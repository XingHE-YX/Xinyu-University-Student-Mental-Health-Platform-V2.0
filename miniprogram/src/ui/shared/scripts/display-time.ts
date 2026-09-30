export const displayTime = (raw: string, now = new Date()): string => {
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return ''
  const minutes = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`
  return `${date.getFullYear() === now.getFullYear() ? '' : `${date.getFullYear()}年`}${date.getMonth() + 1}月${date.getDate()}日`
}
