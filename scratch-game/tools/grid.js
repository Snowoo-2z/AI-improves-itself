const {Resvg}=require('@resvg/resvg-js');const fs=require('fs');const names=process.argv.slice(3);
let s=`<svg xmlns="http://www.w3.org/2000/svg" width="960" height="${360*Math.ceil(names.length/2)}">`;
names.forEach((n,i)=>{const inner=fs.readFileSync('out/'+n+'.svg','utf8').replace(/^<svg[^>]*>/,'').replace(/<\/svg>$/,'');
s+=`<svg x="${(i%2)*480}" y="${Math.floor(i/2)*360}" width="480" height="360">${inner}</svg>`});
fs.writeFileSync(process.argv[2],new Resvg(s+'</svg>',{fitTo:{mode:'width',value:960}}).render().asPng());
