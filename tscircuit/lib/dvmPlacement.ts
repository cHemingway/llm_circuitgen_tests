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
  U11: { x: 10, y: -26, rotation: 270 },
  U12: { x: 24, y: -26, rotation: 270 },
  U13: { x: -4, y: -26, rotation: 270 },
  U14: { x: -18, y: -26, rotation: 270 },
  RN2: { x: -18, y: -32.6, rotation: 0 },
  RN3: { x: -10, y: -32.6, rotation: 180 },
  RN4: { x: -2, y: -32.6, rotation: 180 },
  R20: { x: 17, y: -32.6, rotation: 0 },
  R21: { x: 6.4, y: -19.7, rotation: 180 },
}
