// Bouclier personnel : touche U, ~3 s de protection à -70 % de dégâts, 5 s de recharge.
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM(); vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
let VT=1e12; Date.now=()=>VT;
let graine=987654321;
Math.random=()=>{ graine=(graine*1103515245+12345)%2147483648; return graine/2147483648; };
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{const o=S().lookupVariableByNameAndType(k,'');if(o)o.value=v;};
const get=k=>{const o=S().lookupVariableByNameAndType(k,'');return o&&o.value;};
const J=()=>vm.runtime.targets.find(t=>t.getName()==='Joueur');
const V=(t,k)=>{const o=t.lookupVariableByNameAndType(k,'');return o&&o.value;};
const setV=(t,k,v)=>{const o=t.lookupVariableByNameAndType(k,'');if(o)o.value=v;};
const step=n=>{for(let i=0;i<n;i++){ VT+=33; vm.runtime._step(); }};
const key=(k,d)=>vm.postIOData('keyboard',{key:k,isDown:d});
const fx=()=>vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='FX').length;
let ko=0;
const ok=(nom,cond,detail)=>{ if(!cond)ko++; console.log((cond?'  ok   ':'  ECHEC'),nom,'->',detail); };
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async()=>{
  // pas de vm.start() : il lance une boucle d'images en temps réel ; ici c'est nous qui avançons
  vm.runtime.currentStepTime=33; vm.greenFlag(); step(5);
  const combat=()=>{ set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',9000);
    set('P1HP',600); set('BotHP',600); set('P1Max',600); set('BotMax',600);
    set('P1Arme',1); set('P1ArmeOrig',1); set('niveau',1); set('BotArme',1);
    set('BotAggro',0); set('BotGarde',0); set('BotReaction',600); set('BotVitesse',0);
    step(6); set('phase','fight'); set('BotX',60); set('P1X',-150); set('P1Y',-92); set('P1Dir',90);
    setV(J(),'bulleT',0); setV(J(),'bulleCd',0); setV(J(),'talBulle',0); set('P1State','idle'); step(2); };

  // 1) activation : la touche U allume le bouclier
  combat();
  key('u',true); step(2); key('u',false);
  const t0=Number(V(J(),'bulleT')), cd0=Number(V(J(),'bulleCd'));
  ok('déclenchement (U)', t0>=80 && cd0>=140, 'bulleT='+t0+' images, recharge='+cd0+' images');

  // 2) durée : encore active à 2,5 s, éteinte après 3 s
  step(70); const actif=Number(V(J(),'bulleT'))>0;
  step(30); const eteint=Number(V(J(),'bulleT'))===0;
  ok('durée ~3 s', actif && eteint, 'active après 70 images : '+actif+' | éteinte après 100 images : '+eteint);

  // 3) dégâts : une flèche de 40 dégâts n'en fait plus que ~12 avec le bouclier
  const encaisse=(avecBulle)=>{
    combat(); setV(J(),'bulleCd',0); setV(J(),'bulleT', avecBulle?90:0);
    const hp=Number(get('P1HP')); set('P1Hit',40); set('P1HitType','fleche'); set('P1HitDir',1); step(1);
    return { perte: Math.round(hp-Number(get('P1HP'))), fx: fx() };
  };
  const sans=encaisse(false), avec=encaisse(true);
  ok('absorption des dégâts', avec.perte>0 && avec.perte<=sans.perte*0.4,
     'sans bouclier : '+sans.perte+' dégâts | avec : '+avec.perte+' dégâts (-70 % attendu)');

  // 4) recharge : impossible de relancer le bouclier pendant le temps de recharge
  combat(); setV(J(),'bulleCd',60);
  key('u',true); step(2); key('u',false); step(2);
  const bloque=Number(V(J(),'bulleT'))===0;
  setV(J(),'bulleCd',0); key('u',true); step(2); key('u',false); step(2);
  const repart=Number(V(J(),'bulleT'))>0;
  ok('recharge du bouclier', bloque && repart,
     'en recharge : '+(bloque?'bloqué':'déclenché !')+' | une fois prêt : '+(repart?'repart':'bloqué !'));

  // 5) visuel : une bulle (clone FX) suit le combattant — et c'est bien le dessin de la bulle.
  //    (le type était lu une image trop tard : les autres effets nés la même image l'écrasaient)
  const bulles=()=>vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='FX'&&
      t.lookupVariableByNameAndType('typeActuel','').value==='bulle');
  combat();
  key('u',true); step(2); key('u',false); step(1);
  const b1=bulles(), costumes=b1.map(t=>t.sprite.costumes[t.currentCostume].name);
  step(3);
  ok('visuel de la bulle', b1.length===1 && costumes[0]==='bulle',
     b1.length+' clone(s) FX, costume = '+(costumes.join(',')||'aucun'));

  // 5 bis) un effet de combat né pendant la protection ne doit pas se transformer en bulle
  combat(); key('u',true); step(2); key('u',false); step(2);
  set('P1Hit',20); set('P1HitType','poing'); set('P1HitDir',1); step(3);
  const b2=bulles();
  ok('bulle et effets de combat séparés', b2.length===1,
     b2.length+' bulle(s) pendant un coup reçu (1 attendue)');

  // 6) HUD : la jauge de bouclier du joueur suit bien l'état réel (miroir P1BulleT / P1BulleCd)
  combat(); key('u',true); step(2); key('u',false); step(2);
  const jauge=Number(get('P1BulleT')), cdHud=Number(get('P1BulleCd'));
  step(200);
  const fini=Number(get('P1BulleT'))===0 && Number(get('P1BulleCd'))===0;
  ok('jauge du bouclier sur le HUD', jauge>0 && cdHud>0 && fini,
     'HUD : '+jauge+' images de protection, recharge '+cdHud+' -> puis tout à 0 : '+fini);
  console.log(ko===0?'RESULTAT : OK':'RESULTAT : '+ko+' echec(s)');
  process.exit(ko===0?0:1);
}).catch(e=>{console.error(e);process.exit(1)});
