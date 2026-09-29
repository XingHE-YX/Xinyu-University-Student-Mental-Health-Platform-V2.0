Component({ properties: { title: { type: String, value: '这里暂时没有内容' }, actionLabel: { type: String, value: '' } }, methods: { action() { this.triggerEvent('action') } } })
