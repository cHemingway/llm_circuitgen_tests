/**
 * Command-side placement: the 74LV595A registers, 74LVC07A buffers, pull-up
 * arrays and the two discrete resistors. Chosen together with the pin
 * assignment in dvmPinMap.ts by minimising ratsnest crossings. Each chip's
 * decoupling capacitor follows it (see DvmInterface.tsx).
 */
export interface Placement {
  x: number
  y: number
  rotation: 0 | 90 | 180 | 270
}

export const COMMAND_PLACEMENT: Record<string, Placement> = {
  U11: { x: 13.0, y: -27.0, rotation: 0 },
  U12: { x: 26.8, y: -27.0, rotation: 0 },
  U13: { x: 0.2, y: -23.6, rotation: 90 },
  U14: { x: -15.1, y: -23.3, rotation: 90 },
  RN2: { x: -16.2, y: -30.7, rotation: 270 },
  RN3: { x: -7.6, y: -28.2, rotation: 180 },
  RN4: { x: 6.0, y: -26.5, rotation: 270 },
  R20: { x: 34.9, y: -21.0, rotation: 180 },
  R21: { x: 9.4, y: -21.5, rotation: 0 },
}
