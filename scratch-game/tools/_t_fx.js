// Effets visuels : chaque impact garde SON apparence (étoile pour les coups lourds, éclair quand la
// garde casse) et le logo n'apparaît que dans le menu.
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM(); vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
let VT=1e12; Date.now=()=>VT;
let graine=424242;
Math.random=()=>{ graine=(graine*1103515245+12345)%2147483648; return graine/2147483648; };
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{const o=S().lookupVariableByNameAndType(k,'');o.value=v;};
const get=k=>{const o=S().lookupVariableByNameAndType(k,'');return o&&o.value;};
const step=n=>{for(let i=0;i<n;i++){VT+=33;vm.runtime._step();}};
const fx=()=>vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='FX');
const types=()=>fx().map(t=>t.sprite.costumes[t.currentCostume].name);
const Logo=()=>vm.runtime.targets.find(t=>t.sprite.name==='Logo');
let ko=0;
const ok=(nom,cond,detail)=>{ if(!cond)ko++; console.log((cond?'  ok   ':'  ECHEC'),nom,'->',detail); };
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(()=>{
  vm.runtime.currentStepTime=33; vm.greenFlag(); step(8);
  const combat=(pvBot)=>{ set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',9000);
    set('P1HP',600); set('BotHP',600); set('P1Max',600); set('BotMax',600);
    set('P1Arme',1); set('P1ArmeOrig',1); set('niveau',1); set('BotArme',1);
    set('BotAggro',0); set('BotGarde',pvBot?pvBot:0); set('BotReaction',600); set('BotVitesse',0);
    step(6); set('phase','fight'); set('BotX',60); set('P1X',-150); set('P1Y',-92); set('P1Dir',90);
    set('BotState','idle'); step(2); };

  // 1) coup normal : étincelle + 6 particules
  combat(); set('BotHit',12); set('BotHitType','punch'); set('BotHitDir',1); step(2);
  const t1=types();
  ok('impact normal (étincelle)', t1[0]==='spark' && t1.filter(t=>t==='dot').length===6,
     t1.join(','));

  // 2) coup lourd (smash) : étoile au lieu de l'étincelle
  step(60); set('BotHit',30); set('BotHitType','smash'); set('BotHitDir',1); step(2);
  const t2=types();
  ok('coup lourd (étoile)', t2[0]==='etoile', t2.join(','));

  // 3) garde brisée par le marteau : éclair
  step(60); combat(60); set('BotGarde',60); set('BotState','block');
  set('BotHit',30); set('BotHitType','smash'); set('BotHitDir',1); step(2);
  const t3=types();
  ok('garde brisée (éclair)', t3.indexOf('eclair')>=0, t3.join(','));

  // 4) aucun clone ne fuit : tout est nettoyé
  step(120);
  ok('effets nettoyés', fx().length===0, fx().length+' clone(s) restant(s) après 4 s');

  // 5) le logo ne s'affiche que dans le menu (et il est bien visible)
  set('scene','menu'); step(4); const m=Logo().visible;
  set('scene','shop'); step(4); const s2=Logo().visible;
  set('scene','fight'); step(4); const f2=Logo().visible;
  ok('logo réservé au menu', m===true && s2===false && f2===false,
     'menu='+m+' boutique='+s2+' combat='+f2);
  set('scene','menu'); step(3); vm.runtime.renderer.toPNG('out/fx_menu.png');
  console.log(ko===0?'RESULTAT : OK':'RESULTAT : '+ko+' echec(s)');
  process.exit(ko===0?0:1);
}).catch(e=>{console.error(e);process.exit(1)});
