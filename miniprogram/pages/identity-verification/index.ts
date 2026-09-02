import { verifyIdentity } from '../../services/auth'

Page({
  data: { name: '', studentNumber: '', loading: false, error: '', from: '' },
  onLoad(query: Record<string, string>) { this.setData({ from: query.from ?? '' }) },
  onNameInput(event: WechatMiniprogram.Input) { this.setData({ name: event.detail.value, error: '' }) },
  onStudentInput(event: WechatMiniprogram.Input) { this.setData({ studentNumber: event.detail.value, error: '' }) },
  async submit() {
    if (!this.data.name.trim() || !this.data.studentNumber.trim()) { this.setData({ error: '请填写姓名和学号' }); return }
    this.setData({ loading: true, error: '' })
    try { await verifyIdentity(this.data.name.trim(), this.data.studentNumber.trim()); wx.switchTab({ url: '/pages/today/index' }) }
    catch (error) { this.setData({ error: error instanceof Error ? error.message : '身份核验服务暂时不可用' }) }
    finally { this.setData({ loading: false }) }
  },
  cancel() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/today/index' }) }) },
})
