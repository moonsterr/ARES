/**
 * Region bounds configuration for ARES dashboard.
 * Each region defines a camera view:
 *   longitude, latitude — centre point
 *   zoom               — Deck.gl/MapLibre zoom level
 *   pitch, bearing     — optional 3-D tilt
 *
 * Used by map region-jump controls and initial view state.
 */

export const REGIONS = {
  /** Default home view — covers full Middle East + Eastern Mediterranean */
  middle_east: {
    label:     'Middle East',
    longitude: 44.0,
    latitude:  29.0,
    zoom:      4.5,
    pitch:     0,
    bearing:   0,
  },

  /** Levant: Israel, Gaza, West Bank, Lebanon, Syria */
  levant: {
    label:     'Levant',
    longitude: 35.5,
    latitude:  33.0,
    zoom:      6.5,
    pitch:     0,
    bearing:   0,
  },

  /** Gaza Strip close-up */
  gaza: {
    label:     'Gaza Strip',
    longitude: 34.4,
    latitude:  31.4,
    zoom:      9.0,
    pitch:     0,
    bearing:   0,
  },

  /** Persian Gulf — Iran, Saudi Arabia, UAE, Kuwait, Qatar, Bahrain */
  persian_gulf: {
    label:     'Persian Gulf',
    longitude: 50.5,
    latitude:  26.5,
    zoom:      5.5,
    pitch:     0,
    bearing:   0,
  },

  /** Red Sea corridor — Yemen, Houthi maritime threat zone */
  red_sea: {
    label:     'Red Sea',
    longitude: 39.0,
    latitude:  18.0,
    zoom:      5.0,
    pitch:     0,
    bearing:   0,
  },

  /** Yemen — full country view */
  yemen: {
    label:     'Yemen',
    longitude: 47.5,
    latitude:  15.5,
    zoom:      6.0,
    pitch:     0,
    bearing:   0,
  },

  /** Iran — full country view */
  iran: {
    label:     'Iran',
    longitude: 53.5,
    latitude:  32.5,
    zoom:      5.0,
    pitch:     0,
    bearing:   0,
  },

  /** Eastern Mediterranean — Cyprus, Turkey, Greece, Egypt */
  eastern_med: {
    label:     'Eastern Mediterranean',
    longitude: 30.0,
    latitude:  34.5,
    zoom:      5.5,
    pitch:     0,
    bearing:   0,
  },

  /** North Africa — Libya, Egypt, Sudan, Tunisia */
  north_africa: {
    label:     'North Africa',
    longitude: 20.0,
    latitude:  24.0,
    zoom:      4.0,
    pitch:     0,
    bearing:   0,
  },

  /** Horn of Africa — Somalia, Ethiopia, Djibouti, Eritrea */
  horn_of_africa: {
    label:     'Horn of Africa',
    longitude: 44.0,
    latitude:  8.0,
    zoom:      5.0,
    pitch:     0,
    bearing:   0,
  },

  /** Ukraine conflict zone */
  ukraine: {
    label:     'Ukraine',
    longitude: 32.0,
    latitude:  49.0,
    zoom:      5.5,
    pitch:     0,
    bearing:   0,
  },

  /** Caucasus — Armenia, Azerbaijan, Georgia */
  caucasus: {
    label:     'Caucasus',
    longitude: 44.5,
    latitude:  41.5,
    zoom:      6.0,
    pitch:     0,
    bearing:   0,
  },
}

/** Ordered list for UI menus — most relevant regions first */
export const REGION_LIST = [
  'middle_east',
  'levant',
  'gaza',
  'persian_gulf',
  'red_sea',
  'yemen',
  'iran',
  'eastern_med',
  'north_africa',
  'horn_of_africa',
  'ukraine',
  'caucasus',
]

/** Default region on initial load */
export const DEFAULT_REGION = 'middle_east'
