Component({
  properties: {
    current: { type: Number, value: 0, observer: 'syncSegments' },
    total: { type: Number, value: 0, observer: 'syncSegments' },
  },
  data: { segments: [] as number[] },
  lifetimes: { attached() { this.syncSegments() } },
  methods: {
    syncSegments() {
      const total = Math.max(0, Number(this.data.total) || 0)
      this.setData({ segments: Array.from({ length: total }, (_, index) => index) })
    },
  },
})
