Component({ properties: { title: String, summary: String, recordedAt: String, category: String }, methods: { tap() { this.triggerEvent('open') } } })
