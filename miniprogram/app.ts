interface IAppOption {
  globalData: {
    apiBaseUrl: string;
    environmentKind: 'demo' | 'authorized' | 'unconfigured';
  };
}

App<IAppOption>({
  globalData: {
    // 真实构建通过环境配置注入 API 地址；未配置时页面只展示不可用状态。
    apiBaseUrl: '',
    environmentKind: 'unconfigured',
  },
  onLaunch() {
    // 初始化阶段不发起网络请求；环境状态由后续服务端配置确认。
  },
});
