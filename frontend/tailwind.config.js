/** Jetons des maquettes « HBN Paie » (S4 / US-40). */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        encre: '#16202E',
        fond: '#F5F6F8',
        surface: '#FFFFFF',
        bordure: '#E3E6EB',
        ligne: '#EEF0F3',
        champ: '#D5D9E0',
        attenue: '#5B6472',
        primaire: '#1F3864',
        menu: '#14213D',
        'menu-survol': '#1F2E52',
        'menu-texte': '#C9D2E3',
        accent: '#F2B544',
        selection: '#F0F4FB',
        info: { fond: '#E6EEFF', texte: '#1E3A8A' },
        alerte: { fond: '#FFF8E6', bord: '#F2D28B', texte: '#5C3D00' },
        danger: '#B42318',
        succes: '#166534',
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      minHeight: { cible: '44px' },
      height: { cible: '44px' },
    },
  },
  plugins: [],
}
