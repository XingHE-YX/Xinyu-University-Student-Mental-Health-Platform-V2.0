Component({ properties: { title: String, description: String }, methods: { tap() { this.triggerEvent('action') } } })
