interface IAppOption {
  globalData: {
    apiBaseUrl: string;
    environmentKind: 'demo' | 'authorized' | 'unconfigured';
  };
}

App<IAppOption>({
  globalData: {
    apiBaseUrl: '',
    environmentKind: 'unconfigured',
  },
  onLaunch() {
    // 初始化阶段不发起网络请求；环境状态由后续服务端配置确认。
  },
});
