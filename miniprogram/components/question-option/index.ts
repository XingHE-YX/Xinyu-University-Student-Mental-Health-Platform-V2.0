Component({ properties: { label: String, selected: Boolean, value: Number }, methods: { choose() { this.triggerEvent('choose', { value: this.data.value }) } } })
