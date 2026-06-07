export type ColourRamp = [[number, number], [number, number, number, number]];

export const buildCustomColormap = (stops: [number, [number, number, number, number]][]) =>
    encodeURIComponent(JSON.stringify(stops));
  
export const ERP_RAMP: ColourRamp[] = [
[[0,0.5],   [20, 35, 70, 255]],       // rgb(20, 35, 70)
[[0.5,2], [55, 35, 140, 255]],      // rgb(55, 35, 140)
[[2,4],   [150, 30, 160, 255]],     // rgb(150, 30, 160)
[[4,6.5],   [190, 90, 65, 255]],      // rgb(190, 90, 65)
[[6.5,7], [255, 240, 150, 255]],    // rgb(255, 240, 150)
];