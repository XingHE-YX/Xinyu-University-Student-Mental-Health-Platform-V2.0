interface IAppOption {
  globalData: {
    apiBaseUrl: string
  }
}

App<IAppOption>({
  globalData: {
    apiBaseUrl: '',
  },
})
