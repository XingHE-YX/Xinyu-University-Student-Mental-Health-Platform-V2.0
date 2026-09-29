Component({ properties: { displayName: String, excerpt: String, status: String, responseCount: Number }, methods: { tap() { this.triggerEvent('open') } } })
