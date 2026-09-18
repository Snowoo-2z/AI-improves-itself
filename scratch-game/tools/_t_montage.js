// Planche 2x2 : on réutilise les PNG produits par le rendu factice (placement exact).
const fs=require('fs'), path=require('path'); const {Resvg}=require('@resvg/resvg-js');
const tuiles=[
  ['v_shop_armes.png','Boutique, page ARMES : 6 armes, prix, description'],
  ['v_shop_marteau.png','Survol du marteau : icone, description, prix'],
  ['v_marteau.png','Marteau : le special perce la garde (34 degats)'],
  ['v_fleche.png','Arc : le K tire une fleche ; bouclier chez le bot'],
];
const W=480,H=360,L=26,M=12;
let corps='';
tuiles.forEach(([f,titre],i)=>{
  const x=M+(i%2)*(W+M), y=L+Math.floor(i/2)*(H+L+M);
  corps+=`<text x="${x+6}" y="${y-7}" font-family="DejaVu Sans, sans-serif" font-size="16" fill="#ffffff">${titre}</text>`
       +`<rect x="${x-2}" y="${y-2}" width="${W+4}" height="${H+4}" fill="#233046" rx="3"/>`
       +`<image x="${x}" y="${y}" width="${W}" height="${H}" href="${path.resolve('out',f)}"/>`;
});
const svg=`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${2*W+3*M}" height="${2*H+2*L+3*M}">`
  +`<rect width="100%" height="100%" fill="#0b1020"/>${corps}</svg>`;
fs.writeFileSync('out/planche_armes.svg',svg);
fs.writeFileSync('out/planche_armes.png',new Resvg(svg,{fitTo:{mode:'width',value:1400}}).render().asPng());
console.log('ok');
