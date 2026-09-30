import { getUserMessage } from '../../../infra/error'
import { recoverAccount } from '../../../services/auth'
Page({ data: { loading: false, error: '' }, async submit() { this.setData({ loading: true, error: '' }); try { await recoverAccount(); wx.switchTab({ url: '/ui/pages/today/index' }) } catch (error) { this.setData({ error: getUserMessage(error, '账户暂时无法恢复') }) } finally { this.setData({ loading: false }) } } })
