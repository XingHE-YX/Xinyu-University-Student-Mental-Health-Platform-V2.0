Page({
  data: { status: '', id: '', message: '' },
  onLoad(query: Record<string, string>) { const status = query.status ?? ''; const messages: Record<string, string> = { checking: '内容正在检查，检查完成前不会出现在公开列表。', published: '内容已公开展示。', protected: '内容已保护展示，互动范围可能受限。', pending_confirmation: '这条内容等待你的确认。', unpublished: '这条内容暂未公开，内部理由不会在这里展示。', safety_priority: '这条内容优先进入支持处理，完整正文暂不展示。', deleted: '这条内容已删除，正文不会恢复。' }; this.setData({ status, id: query.id ?? '', message: messages[status] ?? '当前状态暂时不可用' }) },
  back() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/treehole/index' }) }) },
})
