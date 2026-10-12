// Aviso sonoro corto con Web Audio (sin archivos). El navegador solo permite
// sonido después de que el usuario interactuó con la página.

let context = null

export function beep() {
  try {
    context ||= new AudioContext()
    if (context.state === 'suspended') context.resume()
    const now = context.currentTime
    for (const [offset, freq] of [[0, 880], [0.18, 1175]]) {
      const osc = context.createOscillator()
      const gain = context.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, now + offset)
      gain.gain.exponentialRampToValueAtTime(0.25, now + offset + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.16)
      osc.connect(gain).connect(context.destination)
      osc.start(now + offset)
      osc.stop(now + offset + 0.17)
    }
  } catch {
    /* sin audio disponible */
  }
}
