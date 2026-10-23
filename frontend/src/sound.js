// Aviso sonoro con Web Audio (sin archivos). El navegador solo permite
// sonido después de que el usuario interactuó con la página.

let context = null

// Tres ráfagas rápidas de dos tonos (agudo-grave): suena a alarma sin llegar a
// sirena. Onda cuadrada para que se destaque, con un filtro que le saca lo
// chillón.
const TONES = [1568, 1175] // sol y re
const TONE_GAP = 0.1 // s entre los dos tonos de una ráfaga
const BURST_GAP = 0.32 // s entre ráfagas
const BURSTS = 3
const LENGTH = 0.09 // s que suena cada tono
const VOLUME = 0.12
const BRIGHTNESS = 3200 // Hz: corte del filtro

function tone(ctx, freq, start) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  const filter = ctx.createBiquadFilter()
  osc.type = 'square'
  osc.frequency.value = freq
  filter.type = 'lowpass'
  filter.frequency.value = BRIGHTNESS
  gain.gain.setValueAtTime(0.0001, start)
  gain.gain.exponentialRampToValueAtTime(VOLUME, start + 0.008)
  gain.gain.setValueAtTime(VOLUME, start + LENGTH - 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + LENGTH)
  osc.connect(filter).connect(gain).connect(ctx.destination)
  osc.start(start)
  osc.stop(start + LENGTH + 0.01)
}

// Programa el aviso completo en un contexto de audio (también sirve uno
// offline, para grabarlo a un archivo). Devuelve la duración en segundos.
export function scheduleAlert(ctx, start = ctx.currentTime) {
  for (let b = 0; b < BURSTS; b++) {
    TONES.forEach((freq, i) => tone(ctx, freq, start + b * BURST_GAP + i * TONE_GAP))
  }
  return (BURSTS - 1) * BURST_GAP + (TONES.length - 1) * TONE_GAP + LENGTH
}

export function beep() {
  try {
    context ||= new AudioContext()
    if (context.state === 'suspended') context.resume()
    scheduleAlert(context)
  } catch {
    /* sin audio disponible */
  }
}
