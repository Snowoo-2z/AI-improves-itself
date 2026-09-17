// Renderer factice pour scratch-vm : enregistre drawables + stylo et compose un SVG/PNG.
const {Resvg}=require('@resvg/resvg-js');const fs=require('fs');
class FakeRenderer{
  constructor(){this.skins={};this.drawables={};this.pen=[];this.nextId=1;this.order=[];}
  getNativeSize(){return [480,360]} setLayerGroupOrdering(){}
  createDrawable(group){const id=this.nextId++;this.drawables[id]={id,group,skin:null,x:0,y:0,dir:90,scale:[100,100],visible:true,effects:{}};this.order.push(id);return id}
  destroyDrawable(id){delete this.drawables[id];this.order=this.order.filter(o=>o!==id)}
  updateDrawableSkinId(id,s){if(this.drawables[id])this.drawables[id].skin=s}
  updateDrawablePosition(id,p){const d=this.drawables[id];if(d){d.x=p[0];d.y=p[1]}}
  updateDrawableDirectionScale(id,dir,sc){const d=this.drawables[id];if(d){d.dir=dir;d.scale=sc}}
  updateDrawableVisible(id,v){if(this.drawables[id])this.drawables[id].visible=v}
  updateDrawableEffect(id,e,v){if(this.drawables[id])this.drawables[id].effects[e]=v}
  setDrawableOrder(id,order,group,opt){const i=this.order.indexOf(id);if(i<0)return;this.order.splice(i,1);
    if(opt){const same=this.order.filter(o=>this.drawables[o]&&this.drawables[o].group===group);const cur=same.indexOf(id);order=same.length?this.order.indexOf(same[Math.max(0,Math.min(same.length-1,cur+order))]):0;}
    if(order>=1e9||order===Infinity)this.order.push(id);else if(order<=0)this.order.unshift(id);else this.order.splice(Math.min(order,this.order.length),0,id);return order}
  getDrawableOrder(id){return this.order.indexOf(id)}
  _skin(svg,rc){const m=svg.match(/width="([\d.]+)"\s+height="([\d.]+)"/);return{type:'svg',svg,w:+m[1],h:+m[2],rc:rc||[+m[1]/2,+m[2]/2]}}
  createSVGSkin(svg,rc){const id=this.nextId++;this.skins[id]=this._skin(svg,rc);return id}
  updateSVGSkin(id,svg,rc){this.skins[id]=this._skin(svg,rc)}
  createBitmapSkin(){return this.nextId++} updateBitmapSkin(){} createTextSkin(){return this.nextId++} updateTextSkin(){}
  destroySkin(id){delete this.skins[id]}
  getSkinSize(id){const s=this.skins[id];return s?[s.w,s.h]:[0,0]}
  getCurrentSkinSize(id){const d=this.drawables[id];return d&&d.skin?this.getSkinSize(d.skin):[0,0]}
  getSkinRotationCenter(id){const s=this.skins[id];return s?s.rc:[0,0]}
  createPenSkin(){const id=this.nextId++;this.skins[id]={type:'pen'};return id}
  penClear(){this.pen=[]}
  penLine(skin,attr,x0,y0,x1,y1){this.pen.push({t:'line',attr:{diameter:attr.diameter,color4f:[...attr.color4f]},x0,y0,x1,y1})}
  penPoint(skin,attr,x,y){this.penLine(skin,attr,x,y,x,y)}
  penStamp(skin,did){const d=this.drawables[did];if(d)this.pen.push({t:'stamp',d:JSON.parse(JSON.stringify(d))})}
  getFencedPositionOfDrawable(id,p){return p}
  getBounds(id){const d=this.drawables[id];const s=d&&this.skins[d.skin];if(!s||!s.w)return{left:0,right:0,top:0,bottom:0};const w=s.w*d.scale[0]/100,h=s.h*d.scale[1]/100;return{left:d.x-w/2,right:d.x+w/2,top:d.y+h/2,bottom:d.y-h/2}}
  getBoundsForBubble(id){return this.getBounds(id)}
  isTouchingDrawables(){return false}isTouchingColor(){return false}drawableTouching(){return false}pick(){return -1}draw(){}
  _draw(d,force){const s=this.skins[d.skin];if(!s||s.type!=='svg'||(!d.visible&&!force))return'';
    const sx=d.scale[0]/100,sy=d.scale[1]/100;const flip=d.dir<0?-1:1;const rot=(d.dir===90||d.dir===-90)?0:d.dir-90;
    const ghost=d.effects.ghost||0,color=d.effects.color||0,bright=d.effects.brightness||0;let filt='';
    if(color||bright){const k=`f${Math.round(color)}_${Math.round(bright)}`;filt=`filter="url(#${k})"`;this._filters[k]={color,bright};}
    const inner=s.svg.replace(/^<svg[^>]*>/,'').replace(/<\/svg>\s*$/,'');
    return `<g transform="translate(${240+d.x},${180-d.y}) rotate(${rot}) scale(${sx*flip},${sy}) translate(${-s.rc[0]},${-s.rc[1]})" opacity="${1-ghost/100}" ${filt}>${inner}</g>`}
  toSVG(){this._filters={};let body='';
    for(const d of this.order.map(i=>this.drawables[i]).filter(d=>d&&d.group==='background'))body+=this._draw(d);
    for(const p of this.pen){if(p.t==='line'){const c=p.attr.color4f;body+=`<line x1="${240+p.x0}" y1="${180-p.y0}" x2="${240+p.x1}" y2="${180-p.y1}" stroke="rgb(${Math.round(c[0]*255)},${Math.round(c[1]*255)},${Math.round(c[2]*255)})" stroke-opacity="${c[3]}" stroke-width="${p.attr.diameter}" stroke-linecap="round"/>`}else body+=this._draw(p.d,true)}
    for(const d of this.order.map(i=>this.drawables[i]).filter(d=>d&&d.group==='sprite'))body+=this._draw(d);
    let defs='<defs>';for(const k in this._filters){const {color,bright}=this._filters[k];const b=bright/100;
      defs+=`<filter id="${k}" color-interpolation-filters="sRGB"><feColorMatrix type="hueRotate" values="${color*1.8}"/><feComponentTransfer>`+
        ['R','G','B'].map(c=>b>0?`<feFunc${c} type="linear" slope="${1-b}" intercept="${b}"/>`:`<feFunc${c} type="linear" slope="${1+b}"/>`).join('')+`</feComponentTransfer></filter>`}
    return `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">${defs}</defs><rect width="480" height="360" fill="#fff"/>${body}</svg>`}
  toPNG(path){const svg=this.toSVG();fs.writeFileSync(path.replace(/\.png$/,'.svg'),svg);fs.writeFileSync(path,new Resvg(svg,{fitTo:{mode:'zoom',value:2}}).render().asPng());}
}
module.exports=FakeRenderer;
