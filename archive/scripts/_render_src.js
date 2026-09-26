const { Resvg } = require('@resvg/resvg-js');
const fs = require('fs');
const src = 'D:/Lin_Agent/WB-WorkSpace/BoothKeeper/assets/art/scene-reimu-egg-icon.svg';
const svg = fs.readFileSync(src, 'utf8');
const r = new Resvg(svg, { fitTo: { mode: 'width', value: 720 } });
fs.writeFileSync('D:/Lin_Agent/WB-WorkSpace/BoothKeeper/assets/art/scene-reimu-egg-icon_src720.png', r.render().asPng());
console.log('done');
