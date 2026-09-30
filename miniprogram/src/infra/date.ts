export const moodDateKey = (value: Date = new Date()): string => {
  // Recording days follow the API's Asia/Shanghai calendar.
  return new Date(value.getTime() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10)
}
