// thumb.js <sortie.png> <largeur> <source.svg> ... : assemble des captures dans une image
// (contenu SVG -> les captures gardent leur taille exacte 480x360, taille de la scène Scratch).
const {Resvg}=require('@resvg/resvg-js'); const fs=require('fs');
const dst=process.argv[2], largeur=+process.argv[3], srcs=process.argv.slice(4);
const [cw,chh]=[480,360], cols=Math.max(1,Math.round(largeur/cw)), rows=Math.ceil(srcs.length/cols);
let s=`<svg xmlns="http://www.w3.org/2000/svg" width="${cw*cols}" height="${chh*rows}">`;
srcs.forEach((f,i)=>{
  const inner=fs.readFileSync(f,'utf8').replace(/^<svg[^>]*>/,'').replace(/<\/svg>\s*$/,'');
  s+=`<g transform="translate(${(i%cols)*cw},${Math.floor(i/cols)*chh})">${inner}</g>`;
});
fs.writeFileSync(dst,new Resvg(s+'</svg>',{fitTo:{mode:'width',value:largeur}}).render().asPng());
console.log('->',dst);
