/**
 * SentYacht — Boat Inventory Data
 * Single source of truth for all boat listings.
 * Update this file when inventory changes.
 */
const boats = [
  {
    slug: "astondoa-82-glx-2008",
    name: "Astondoa 82 GLX",
    brand: "Astondoa",
    type: "motor",
    year: 2008,
    price: 1300000,
    length: 24.99,
    beam: 5.90,
    draft: 1.80,
    location: "Barcelona",
    condition: "used",
    badges: [],
    engines: "2× MAN 1360 CV",
    fuel: "Diésel",
    cabins: 4,
    berths: 8,
    heads: 4,
    description: {
      es: "Yate flybridge de gran eslora en excelente estado. Cuatro cabinas, cuatro baños, amplio salón y flybridge con bimini. Mantenimiento al día con revisiones anuales. Ideal para cruceros largos por el Mediterráneo.",
      en: "Large flybridge yacht in excellent condition. Four cabins, four heads, spacious saloon and flybridge with bimini. Fully maintained with annual surveys. Ideal for extended Mediterranean cruising."
    },
    specs: {
      es: { "Eslora": "24,99 m", "Manga": "5,90 m", "Calado": "1,80 m", "Motor": "2× MAN 1360 CV", "Combustible": "Diésel", "Cabinas": "4", "Literas": "8", "Baños": "4", "Año": "2008", "Puerto": "Barcelona" },
      en: { "Length": "24.99 m", "Beam": "5.90 m", "Draft": "1.80 m", "Engine": "2× MAN 1360 HP", "Fuel": "Diesel", "Cabins": "4", "Berths": "8", "Heads": "4", "Year": "2008", "Port": "Barcelona" }
    },
    images: ["astondoa-82-glx-1.jpg"]
  },
  {
    slug: "astondoa-72-glx-2003",
    name: "Astondoa 72 GLX",
    brand: "Astondoa",
    type: "motor",
    year: 2003,
    price: 850000,
    length: 22.00,
    beam: 5.50,
    draft: 1.70,
    location: "Alicante",
    condition: "used",
    badges: ["new"],
    engines: "2× MAN 1100 CV",
    fuel: "Diésel",
    cabins: 4,
    berths: 8,
    heads: 3,
    description: {
      es: "Astondoa 72 GLX con amplio flybridge y cuatro cabinas. Construcción sólida del astillero español de referencia. Mecánica revisada y lista para navegar. Amarre en Alicante.",
      en: "Astondoa 72 GLX with spacious flybridge and four cabins. Solid build from Spain's premier shipyard. Mechanically surveyed and ready to cruise. Berth in Alicante."
    },
    specs: {
      es: { "Eslora": "22,00 m", "Manga": "5,50 m", "Calado": "1,70 m", "Motor": "2× MAN 1100 CV", "Combustible": "Diésel", "Cabinas": "4", "Literas": "8", "Baños": "3", "Año": "2003", "Puerto": "Alicante" },
      en: { "Length": "22.00 m", "Beam": "5.50 m", "Draft": "1.70 m", "Engine": "2× MAN 1100 HP", "Fuel": "Diesel", "Cabins": "4", "Berths": "8", "Heads": "3", "Year": "2003", "Port": "Alicante" }
    },
    images: ["astondoa-72-glx-1.jpg"]
  },
  {
    slug: "astondoa-53-glx-1993",
    name: "Astondoa 53 GLX",
    brand: "Astondoa",
    type: "motor",
    year: 1993,
    price: 195000,
    length: 15.85,
    beam: 4.60,
    draft: 1.30,
    location: "Barcelona",
    condition: "used",
    badges: [],
    engines: "2× MAN 570 CV",
    fuel: "Diésel",
    cabins: 3,
    berths: 6,
    heads: 2,
    description: {
      es: "Clásico Astondoa 53 GLX con líneas atemporales. Tres cabinas, dos baños, salón luminoso. Un referente de la construcción naval española. Mantenimiento impecable para su antigüedad.",
      en: "Classic Astondoa 53 GLX with timeless lines. Three cabins, two heads, bright saloon. A benchmark of Spanish shipbuilding. Impeccably maintained for her age."
    },
    specs: {
      es: { "Eslora": "15,85 m", "Manga": "4,60 m", "Calado": "1,30 m", "Motor": "2× MAN 570 CV", "Combustible": "Diésel", "Cabinas": "3", "Literas": "6", "Baños": "2", "Año": "1993", "Puerto": "Barcelona" },
      en: { "Length": "15.85 m", "Beam": "4.60 m", "Draft": "1.30 m", "Engine": "2× MAN 570 HP", "Fuel": "Diesel", "Cabins": "3", "Berths": "6", "Heads": "2", "Year": "1993", "Port": "Barcelona" }
    },
    images: ["astondoa-53-glx-1.jpg"]
  },
  {
    slug: "astondoa-39-2002",
    name: "Astondoa 39",
    brand: "Astondoa",
    type: "motor",
    year: 2002,
    price: 129000,
    length: 11.95,
    beam: 3.90,
    draft: 1.10,
    location: "El Masnou",
    condition: "used",
    badges: ["stock", "price-drop"],
    engines: "2× Volvo 310 CV",
    fuel: "Diésel",
    cabins: 2,
    berths: 4,
    heads: 1,
    description: {
      es: "Astondoa 39 compacto y manejable, perfecto para escapadas de fin de semana. Dos cabinas, un baño, bañera amplia. Amarre disponible en el Port Esportiu de El Masnou.",
      en: "Compact and manageable Astondoa 39, perfect for weekend getaways. Two cabins, one head, spacious cockpit. Berth available at Port Esportiu de El Masnou."
    },
    specs: {
      es: { "Eslora": "11,95 m", "Manga": "3,90 m", "Calado": "1,10 m", "Motor": "2× Volvo 310 CV", "Combustible": "Diésel", "Cabinas": "2", "Literas": "4", "Baños": "1", "Año": "2002", "Puerto": "El Masnou" },
      en: { "Length": "11.95 m", "Beam": "3.90 m", "Draft": "1.10 m", "Engine": "2× Volvo 310 HP", "Fuel": "Diesel", "Cabins": "2", "Berths": "4", "Heads": "1", "Year": "2002", "Port": "El Masnou" }
    },
    images: ["astondoa-39-1.jpg"]
  },
  {
    slug: "navalia-60-2006",
    name: "Navalia 60",
    brand: "Navalia",
    type: "motor",
    year: 2006,
    price: 360000,
    length: 18.00,
    beam: 5.20,
    draft: 1.50,
    location: "Barcelona",
    condition: "used",
    badges: [],
    engines: "2× Caterpillar 800 CV",
    fuel: "Diésel",
    cabins: 3,
    berths: 6,
    heads: 2,
    description: {
      es: "Navalia 60 de fabricación española con diseño mediterráneo. Tres cabinas, amplio salón con buena visibilidad y plataforma de baño generosa. Mantenimiento profesional desde su botadura.",
      en: "Spanish-built Navalia 60 with Mediterranean design. Three cabins, spacious saloon with good visibility and generous bathing platform. Professionally maintained since launch."
    },
    specs: {
      es: { "Eslora": "18,00 m", "Manga": "5,20 m", "Calado": "1,50 m", "Motor": "2× Caterpillar 800 CV", "Combustible": "Diésel", "Cabinas": "3", "Literas": "6", "Baños": "2", "Año": "2006", "Puerto": "Barcelona" },
      en: { "Length": "18.00 m", "Beam": "5.20 m", "Draft": "1.50 m", "Engine": "2× Caterpillar 800 HP", "Fuel": "Diesel", "Cabins": "3", "Berths": "6", "Heads": "2", "Year": "2006", "Port": "Barcelona" }
    },
    images: ["navalia-60-1.jpg"]
  },
  {
    slug: "sunseeker-manhattan-50-2004",
    name: "Sunseeker Manhattan 50",
    brand: "Sunseeker",
    type: "motor",
    year: 2004,
    price: 359000,
    length: 15.66,
    beam: 4.42,
    draft: 1.17,
    location: "El Masnou",
    condition: "used",
    badges: ["stock"],
    engines: "2× MAN 800 CV",
    fuel: "Diésel",
    cabins: 3,
    berths: 6,
    heads: 2,
    description: {
      es: "Sunseeker Manhattan 50, un icono del diseño británico. Tres cabinas, dos baños, flybridge práctico. Mecánica revisada y en buen estado general. Disponible para visita inmediata en El Masnou.",
      en: "Sunseeker Manhattan 50, an icon of British design. Three cabins, two heads, practical flybridge. Mechanically surveyed and in good overall condition. Available for immediate viewing in El Masnou."
    },
    specs: {
      es: { "Eslora": "15,66 m", "Manga": "4,42 m", "Calado": "1,17 m", "Motor": "2× MAN 800 CV", "Combustible": "Diésel", "Cabinas": "3", "Literas": "6", "Baños": "2", "Año": "2004", "Puerto": "El Masnou" },
      en: { "Length": "15.66 m", "Beam": "4.42 m", "Draft": "1.17 m", "Engine": "2× MAN 800 HP", "Fuel": "Diesel", "Cabins": "3", "Berths": "6", "Heads": "2", "Year": "2004", "Port": "El Masnou" }
    },
    images: ["sunseeker-manhattan-50-1.jpg"]
  },
  {
    slug: "hanse-470-2007",
    name: "Hanse 470",
    brand: "Hanse",
    type: "sail",
    year: 2007,
    price: 210000,
    length: 14.19,
    beam: 4.36,
    draft: 2.10,
    location: "Barcelona",
    condition: "used",
    badges: [],
    engines: "1× Yanmar 55 CV",
    fuel: "Diésel",
    cabins: 3,
    berths: 6,
    heads: 2,
    description: {
      es: "Hanse 470, velero de crucero de alto rendimiento del astillero alemán. Tres cabinas, dos baños, cockpit amplio. Jarcia y velas en buen estado. Ideal para regatas y cruceros largos.",
      en: "Hanse 470, high-performance cruising sailboat from the German shipyard. Three cabins, two heads, spacious cockpit. Rigging and sails in good condition. Ideal for racing and extended cruising."
    },
    specs: {
      es: { "Eslora": "14,19 m", "Manga": "4,36 m", "Calado": "2,10 m", "Motor": "1× Yanmar 55 CV", "Combustible": "Diésel", "Cabinas": "3", "Literas": "6", "Baños": "2", "Año": "2007", "Puerto": "Barcelona" },
      en: { "Length": "14.19 m", "Beam": "4.36 m", "Draft": "2.10 m", "Engine": "1× Yanmar 55 HP", "Fuel": "Diesel", "Cabins": "3", "Berths": "6", "Heads": "2", "Year": "2007", "Port": "Barcelona" }
    },
    images: ["hanse-470-1.jpg"]
  },
  {
    slug: "grand-banks-38-eastbay-ex-2002",
    name: "Grand Banks 38 Eastbay EX",
    brand: "Grand Banks",
    type: "motor",
    year: 2002,
    price: 175000,
    length: 12.45,
    beam: 4.05,
    draft: 1.02,
    location: "El Masnou",
    condition: "used",
    badges: ["new"],
    engines: "2× Caterpillar 420 CV",
    fuel: "Diésel",
    cabins: 2,
    berths: 4,
    heads: 1,
    description: {
      es: "Grand Banks 38 Eastbay EX, referencia en trawlers de calidad. Construcción robusta, dos cabinas, un baño. Navegación eficiente y cómoda. Perfecto para crucero costero y vivir a bordo.",
      en: "Grand Banks 38 Eastbay EX, the benchmark in quality trawlers. Robust construction, two cabins, one head. Efficient and comfortable cruising. Perfect for coastal cruising and liveaboard."
    },
    specs: {
      es: { "Eslora": "12,45 m", "Manga": "4,05 m", "Calado": "1,02 m", "Motor": "2× Caterpillar 420 CV", "Combustible": "Diésel", "Cabinas": "2", "Literas": "4", "Baños": "1", "Año": "2002", "Puerto": "El Masnou" },
      en: { "Length": "12.45 m", "Beam": "4.05 m", "Draft": "1.02 m", "Engine": "2× Caterpillar 420 HP", "Fuel": "Diesel", "Cabins": "2", "Berths": "4", "Heads": "1", "Year": "2002", "Port": "El Masnou" }
    },
    images: ["grand-banks-38-eastbay-ex-1.jpg"]
  },
  {
    slug: "rodman-900-flybridge-1996",
    name: "Rodman 900 FLY",
    brand: "Rodman",
    type: "motor",
    year: 1996,
    price: 39000,
    length: 9.00,
    beam: 3.10,
    draft: 0.90,
    location: "El Masnou",
    condition: "used",
    badges: ["stock", "price-drop"],
    engines: "2× Volvo 150 CV",
    fuel: "Diésel",
    cabins: 1,
    berths: 4,
    heads: 1,
    description: {
      es: "Rodman 900 Flybridge, embarcación española fiable y marinera. Una cabina, un baño, flybridge con buena visibilidad. Opción accesible para iniciarse en la náutica.",
      en: "Rodman 900 Flybridge, a reliable and seaworthy Spanish boat. One cabin, one head, flybridge with good visibility. An accessible option for newcomers to boating."
    },
    specs: {
      es: { "Eslora": "9,00 m", "Manga": "3,10 m", "Calado": "0,90 m", "Motor": "2× Volvo 150 CV", "Combustible": "Diésel", "Cabinas": "1", "Literas": "4", "Baños": "1", "Año": "1996", "Puerto": "El Masnou" },
      en: { "Length": "9.00 m", "Beam": "3.10 m", "Draft": "0.90 m", "Engine": "2× Volvo 150 HP", "Fuel": "Diesel", "Cabins": "1", "Berths": "4", "Heads": "1", "Year": "1996", "Port": "El Masnou" }
    },
    images: ["rodman-900-1.jpg"]
  },
  {
    slug: "fjord-900-1990",
    name: "Fjord 900",
    brand: "Fjord",
    type: "motor",
    year: 1990,
    price: 29500,
    length: 9.00,
    beam: 3.00,
    draft: 0.85,
    location: "El Masnou",
    condition: "used",
    badges: ["stock"],
    engines: "1× Volvo 130 CV",
    fuel: "Diésel",
    cabins: 1,
    berths: 2,
    heads: 1,
    description: {
      es: "Fjord 900 noruego, diseño nórdico funcional y robusto. Una cabina, un baño, cockpit espacioso. Construcción sólida ideal para la navegación costera. La embarcación más accesible de nuestra cartera.",
      en: "Norwegian Fjord 900, functional and robust Nordic design. One cabin, one head, spacious cockpit. Solid construction ideal for coastal navigation. The most accessible vessel in our portfolio."
    },
    specs: {
      es: { "Eslora": "9,00 m", "Manga": "3,00 m", "Calado": "0,85 m", "Motor": "1× Volvo 130 CV", "Combustible": "Diésel", "Cabinas": "1", "Literas": "2", "Baños": "1", "Año": "1990", "Puerto": "El Masnou" },
      en: { "Length": "9.00 m", "Beam": "3.00 m", "Draft": "0.85 m", "Engine": "1× Volvo 130 HP", "Fuel": "Diesel", "Cabins": "1", "Berths": "2", "Heads": "1", "Year": "1990", "Port": "El Masnou" }
    },
    images: ["fjord-900-1.jpg"]
  },
  {
    slug: "finnyacht-35-1972",
    name: "Finnyacht FINM Cleaper 35",
    brand: "Finnyacht",
    type: "sail",
    year: 1972,
    price: 28000,
    length: 10.44,
    beam: 3.20,
    draft: 1.80,
    location: "El Masnou",
    condition: "used",
    badges: ["stock", "price-drop"],
    engines: "1× Volvo 28 CV",
    fuel: "Diésel",
    cabins: 2,
    berths: 5,
    heads: 1,
    description: {
      es: "Velero clásico finlandés Finnyacht 35 con carácter y encanto. Dos cabinas, un baño, bañera protegida. Construcción nórdica robusta pensada para navegación oceánica. Un velero con historia.",
      en: "Classic Finnish sailboat Finnyacht 35 with character and charm. Two cabins, one head, protected cockpit. Robust Nordic construction designed for ocean sailing. A sailboat with history."
    },
    specs: {
      es: { "Eslora": "10,44 m", "Manga": "3,20 m", "Calado": "1,80 m", "Motor": "1× Volvo 28 CV", "Combustible": "Diésel", "Cabinas": "2", "Literas": "5", "Baños": "1", "Año": "1972", "Puerto": "El Masnou" },
      en: { "Length": "10.44 m", "Beam": "3.20 m", "Draft": "1.80 m", "Engine": "1× Volvo 28 HP", "Fuel": "Diesel", "Cabins": "2", "Berths": "5", "Heads": "1", "Year": "1972", "Port": "El Masnou" }
    },
    images: ["finnyacht-35-1.jpg"]
  },
  {
    slug: "ketch-nordic-36-classic-1981",
    name: "Ketch Nordic 36 Classic",
    brand: "Ketch",
    type: "sail",
    year: 1981,
    price: 39500,
    length: 10.97,
    beam: 3.20,
    draft: 1.65,
    location: "El Masnou",
    condition: "used",
    badges: ["new"],
    engines: "1× Volvo 28 CV",
    fuel: "Diésel",
    cabins: 2,
    berths: 5,
    heads: 1,
    description: {
      es: "Ketch Nordic 36 Classic, velero clásico con aparejo de ketch ideal para navegación oceánica. Dos cabinas, un baño. Construcción nórdica robusta. Disponible en El Masnou.",
      en: "Ketch Nordic 36 Classic, a classic ketch-rigged sailboat ideal for ocean sailing. Two cabins, one head. Robust Nordic construction. Available in El Masnou."
    },
    specs: {
      es: { "Eslora": "10,97 m", "Manga": "3,20 m", "Calado": "1,65 m", "Motor": "1× Volvo 28 CV", "Combustible": "Diésel", "Cabinas": "2", "Literas": "5", "Baños": "1", "Año": "1981", "Puerto": "El Masnou" },
      en: { "Length": "10.97 m", "Beam": "3.20 m", "Draft": "1.65 m", "Engine": "1× Volvo 28 HP", "Fuel": "Diesel", "Cabins": "2", "Berths": "5", "Heads": "1", "Year": "1981", "Port": "El Masnou" }
    },
    images: ["ketch-nordic-36-1.jpg"]
  }
];

/* ─── Helper Functions ─── */

/** Format price with European locale: 1.300.000 € */
function formatPrice(price) {
  return price.toLocaleString('es-ES') + ' €';
}

/** Get boats filtered by criteria */
function filterBoats(filters = {}) {
  return boats.filter(boat => {
    if (filters.type && boat.type !== filters.type) return false;
    if (filters.brand && boat.brand !== filters.brand) return false;
    if (filters.location && boat.location !== filters.location) return false;
    if (filters.minPrice && boat.price < filters.minPrice) return false;
    if (filters.maxPrice && boat.price > filters.maxPrice) return false;
    if (filters.minLength && boat.length < filters.minLength) return false;
    if (filters.maxLength && boat.length > filters.maxLength) return false;
    if (filters.minYear && boat.year < filters.minYear) return false;
    if (filters.maxYear && boat.year > filters.maxYear) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const searchable = `${boat.name} ${boat.brand} ${boat.location}`.toLowerCase();
      if (!searchable.includes(q)) return false;
    }
    return true;
  });
}

/** Get unique values for filter options */
function getFilterOptions() {
  return {
    brands: [...new Set(boats.map(b => b.brand))].sort(),
    locations: [...new Set(boats.map(b => b.location))].sort(),
    types: [...new Set(boats.map(b => b.type))],
    priceRange: { min: Math.min(...boats.map(b => b.price)), max: Math.max(...boats.map(b => b.price)) },
    lengthRange: { min: Math.min(...boats.map(b => b.length)), max: Math.max(...boats.map(b => b.length)) },
    yearRange: { min: Math.min(...boats.map(b => b.year)), max: Math.max(...boats.map(b => b.year)) }
  };
}

/** Get a boat by slug */
function getBoatBySlug(slug) {
  return boats.find(b => b.slug === slug) || null;
}

/** Get similar boats (same type or similar price, excluding current) */
function getSimilarBoats(slug, count = 3) {
  const current = getBoatBySlug(slug);
  if (!current) return [];
  return boats
    .filter(b => b.slug !== slug)
    .sort((a, b) => {
      const aScore = (a.type === current.type ? 2 : 0) + (1 / (1 + Math.abs(a.price - current.price) / 100000));
      const bScore = (b.type === current.type ? 2 : 0) + (1 / (1 + Math.abs(b.price - current.price) / 100000));
      return bScore - aScore;
    })
    .slice(0, count);
}

/** Sort boats by field */
function sortBoats(boatList, field, direction = 'desc') {
  return [...boatList].sort((a, b) => {
    const va = a[field], vb = b[field];
    return direction === 'asc' ? va - vb : vb - va;
  });
}
