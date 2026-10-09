import { sessionStore } from '../../src/infra/store/session.ts'
import { assessmentStore } from '../../src/infra/store/assessment.ts'
import { configureLogger } from '../../src/infra/logger.ts'

export const installWxMock = () => {
  const responses = {}
  const requests = []
  const navigations = []
  let tabBarVisible = true
  const baseUrl = 'https://example.test/api/v2'
  sessionStore.clear()
  assessmentStore.clear()
  configureLogger({ level: 'warn', sink: () => {} })
  globalThis.getApp = () => ({ globalData: { apiBaseUrl: baseUrl, environmentKind: 'authorized' } })
  globalThis.wx = {
    hideTabBar() { tabBarVisible = false },
    showTabBar() { tabBarVisible = true },
    login(options) { options.success({ code: 'fixture-login-code' }) },
    request(options) {
      const path = options.url.replace(baseUrl, '')
      requests.push({ path, method: options.method, data: options.data, header: options.header })
      const response = responses[path]
      if (response === undefined) { options.fail({ errMsg: 'request:fail' }); return }
      options.success({ statusCode: 200, data: { request_id: 'fixture', data: response, error: null } })
    },
  }
  for (const method of ['navigateTo', 'redirectTo', 'reLaunch', 'switchTab', 'navigateBack']) {
    globalThis.wx[method] = (options = {}) => navigations.push({ method, ...options })
  }
  return { responses, requests, navigations, get tabBarVisible() { return tabBarVisible } }
}
