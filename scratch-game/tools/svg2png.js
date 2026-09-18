// svg2png.js <entree.svg> <sortie.png> [largeur] [hauteur]
const {Resvg}=require('@resvg/resvg-js'); const fs=require('fs');
const [,,src,dst,w,h]=process.argv;
const fit = w ? {fitTo:{mode:'width',value:+w}} : undefined;
const opts = fit || (h ? {fitTo:{mode:'height',value:+h}} : {});
const png = new Resvg(fs.readFileSync(src,'utf8'), opts).render().asPng();
fs.writeFileSync(dst, png);
console.log('->', dst, png.length, 'octets');
