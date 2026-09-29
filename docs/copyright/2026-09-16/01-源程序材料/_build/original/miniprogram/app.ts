import { runtimeConfig } from './config/runtime'

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
    // 初始化阶段不发起网络请求；环境状态由后续服务端配置确认。
  },
});
