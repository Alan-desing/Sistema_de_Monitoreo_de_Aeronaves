// Forma del ícono según la categoría ADS-B del emisor (campo `category` de adsb.fi).
// Todos los dibujos miran al norte; el mapa los rota según el rumbo.
import planeSvg from 'bootstrap-icons/icons/airplane-fill.svg?raw'
import balloonSvg from 'bootstrap-icons/icons/balloon-fill.svg?raw'

const svg = (body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor">${body}</svg>`

export const SHAPES = {
  jet: { label: 'Avión', svg: planeSvg },
  light: {
    label: 'Avioneta / ultraliviano',
    // Alas cortas y anchas (el planeador las tiene largas y finas).
    svg: svg('<path d="M7.2 1.2h1.6l.1 3.8 5.1.2v2.2l-5.1.2-.1 4.5 2.6.3v1.5l-2.7.2-.7 1-.7-1-2.7-.2v-1.5l2.6-.3-.1-4.5-5.1-.2V5.2l5.1-.2z"/>'),
  },
  heli: {
    label: 'Helicóptero',
    // Palas del rotor cruzadas en X, cabina, botalón de cola y rotor de cola.
    svg: svg(
      '<path d="M3.85 1.15 12.85 10.15 12.15 10.85 3.15 1.85zM12.15 1.15 12.85 1.85 3.85 10.85 3.15 10.15z' +
        'M6.1 6.3a1.9 2.8 0 1 0 3.8 0a1.9 2.8 0 1 0-3.8 0zM7.45 8.5h1.1v5h-1.1zM5.8 13.1h4.4v1.1H5.8z"/>',
    ),
  },
  drone: {
    label: 'Dron',
    // Cuadricóptero visto desde arriba: brazos en X, cuerpo y cuatro hélices.
    svg: svg(
      '<path d="M2.6 1.8 8 7.2l5.4-5.4.8.8L8.8 8l5.4 5.4-.8.8L8 8.8l-5.4 5.4-.8-.8L7.2 8 1.8 2.6z"/>' +
        '<rect x="5.8" y="5.8" width="4.4" height="4.4" rx="1"/>' +
        '<circle cx="3" cy="3" r="2.4" fill-opacity=".55"/><circle cx="13" cy="3" r="2.4" fill-opacity=".55"/>' +
        '<circle cx="3" cy="13" r="2.4" fill-opacity=".55"/><circle cx="13" cy="13" r="2.4" fill-opacity=".55"/>',
    ),
  },
  glider: {
    label: 'Planeador',
    // Alas muy largas y finas, fuselaje delgado, cola en T.
    svg: svg('<path d="M7.5 2.2h1l.1 3.3 7.2.3v1.1l-7.2.3-.1 5.6 2.3.2v1.1H5.2V13l2.3-.2-.1-5.6-7.2-.3V5.8l7.2-.3z"/>'),
  },
  balloon: { label: 'Globo / dirigible', svg: balloonSvg, fixed: true },
}

const BY_CATEGORY = { A1: 'light', A2: 'light', B4: 'light', A7: 'heli', B6: 'drone', B1: 'glider', B2: 'balloon' }

// Sin categoría (o una no listada) se dibuja como avión.
export function shapeOf(ac) {
  return BY_CATEGORY[ac.category] || 'jet'
}
