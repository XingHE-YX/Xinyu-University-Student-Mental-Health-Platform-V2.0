import { runtimeConfig } from './infra/config/runtime'
import { configureLogger, createLogger, logErrorOnce } from './infra/logger'

try {
  const development = wx.getDeviceInfo().platform === 'devtools'
    || wx.getAccountInfoSync().miniProgram.envVersion === 'develop'
  configureLogger({ level: development ? 'debug' : 'warn' })
} catch { configureLogger({ level: 'warn' }) }

const log = createLogger('app')

interface IAppOption {
  globalData: {
    apiBaseUrl: string;
    cloudbaseEnvId: string;
    environmentKind: 'demo' | 'authorized' | 'unconfigured';
  };
}

App<IAppOption>({
  globalData: {
    // WeChat external config carries only non-secret build values.
    apiBaseUrl: runtimeConfig.apiBaseUrl,
    cloudbaseEnvId: runtimeConfig.cloudbaseEnvId,
    environmentKind: runtimeConfig.environmentKind,
  },
  onLaunch() {
    log.info('app.launch', { environment: runtimeConfig.environmentKind })
  },
  onError(error) {
    logErrorOnce('app', 'app.error', error)
  },
  onUnhandledRejection(event) {
    logErrorOnce('app', 'app.unhandled_rejection', event.reason)
  },
});
