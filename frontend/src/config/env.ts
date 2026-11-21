/** Configuration du frontend : API servie par la même origine (racine « / »). */
export const env = {
  apiBase: import.meta.env.VITE_API_BASE ?? '',
}
