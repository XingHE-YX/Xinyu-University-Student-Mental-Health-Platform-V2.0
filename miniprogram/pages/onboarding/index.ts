import { loginWithWechat, recordBasicConsent } from '../../services/auth'

Page({
  data: { loading: false, error: '', agreed: false },
  toggleAgree() { this.setData({ agreed: !this.data.agreed, error: '' }) },
  async begin() {
    if (!this.data.agreed) { this.setData({ error: '请先阅读并同意基础服务说明' }); return }
    this.setData({ loading: true, error: '' })
    try { await loginWithWechat(); await recordBasicConsent(); wx.redirectTo({ url: '/pages/identity-verification/index?from=onboarding' }) }
    catch (error) { this.setData({ error: error instanceof Error ? error.message : '暂时无法进入，请稍后重试' }) }
    finally { this.setData({ loading: false }) }
  },
  leave() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/today/index' }) }) },
})
