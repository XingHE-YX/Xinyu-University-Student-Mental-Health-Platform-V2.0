import { getUserMessage } from '../../../infra/error'
import { logErrorOnce } from '../../../infra/logger'

export const reportPageError = (error: unknown): void => logErrorOnce('ui', 'page.failed', error)

export const handlePageError = (error: unknown, fallback?: string): string => {
  reportPageError(error)
  return getUserMessage(error, fallback)
}
