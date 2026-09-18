// Équilibrage de l'arc (Rosa) : cadence de tir, fermeture de la distance, garde, esquive, chute de dégâts.
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM(); vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{const o=S().lookupVariableByNameAndType(k,'');if(o)o.value=v;};
const get=k=>{const o=S().lookupVariableByNameAndType(k,'');return o&&o.value;};
const J=()=>vm.runtime.targets.find(t=>t.getName()==='Joueur');
const V=(t,k)=>{const o=t.lookupVariableByNameAndType(k,'');return o&&o.value;};
const setV=(t,k,v)=>{const o=t.lookupVariableByNameAndType(k,'');if(o)o.value=v;};
// Horloge virtuelle : 33 ms par image. Sans elle, les blocs "attendre" du jeu dépendent du
// temps réel et le test devient instable d'une exécution à l'autre. On n'appelle pas vm.start()
// (qui lance une boucle d'images en temps réel) : le test avance image par image.
let VT=1e12;
Date.now=()=>VT;
// Les blocs "nombre aléatoire" de Scratch utilisent Math.random : on le remplace par un
// générateur à graine pour que le test donne exactement le même résultat à chaque exécution.
let graine=123456789;
Math.random=()=>{ graine=(graine*1103515245+12345)%2147483648; return graine/2147483648; };
const step=n=>{for(let i=0;i<n;i++){ VT+=33; vm.runtime._step(); }};
const key=(k,d)=>vm.postIOData('keyboard',{key:k,isDown:d});
const dist=()=>Math.abs(get('BotX')-get('P1X'));
const vers=()=>get('BotX')>get('P1X')?'ArrowRight':'ArrowLeft';
// who : 1 = joueur, 2 = bot (var locale des clones de flèche) ; sans argument = toutes
const fleches=(who)=>vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='Fleche'&&
  (who===undefined||Number(V(t,'who'))===who)).length;
let ko=0;
const ok=(nom,cond,detail)=>{ if(!cond)ko++; console.log((cond?'  ok   ':'  ECHEC'),nom,'->',detail); };
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async()=>{
  // pas de vm.start() : il lance une boucle d'images en temps réel ; ici c'est nous qui avançons
  vm.runtime.currentStepTime = 33;
  vm.greenFlag(); step(5);
  const combat=(d,recharge)=>{ set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',9000);
    set('P1HP',600); set('BotHP',600); set('P1Max',600); set('BotMax',600);
    set('P1Arme',1); set('P1ArmeOrig',1); set('niveau',6); set('BotArme',5);
    set('BotAggro',35); set('BotGarde',55); set('BotReaction',7); set('BotVitesse',5.0); set('BotNom','Rosa');
    step(6); set('phase','fight'); set('BotX',-60); set('P1X',d-60); set('P1Y',-92);
    setV(J(),'recharge',recharge||0); setV(J(),'timer',0); set('P1State','idle'); set('BotState','idle'); step(2); };

  // 1) cadence de tir : le bot ne peut plus arroser en continu
  combat(230);
  let tirees=0, avant=0;
  for(let i=0;i<600;i++){ step(1); const n=fleches(2); if(n>avant)tirees+=n-avant; avant=n; }
  ok('cadence arc (20 s)', tirees<=12, tirees+' flèches (max 12, avant le correctif : >20)');

  // 2) le joueur peut atteindre le corps à corps en marchant
  combat(230); const k=vers(); let min=999;
  key(k,true);
  for(let i=0;i<400;i++){ step(1); min=Math.min(min,dist()); }
  key(k,false);
  ok('distance fermable à pied', min<70, 'distance minimale '+Math.round(min)+' px | dégâts subis '+
     Math.round(600-get('P1HP'))+'/600');

  // 3) garde en avançant : on traverse le terrain sans se faire déchiqueter
  combat(230); const k2=vers(); const hp0=get('P1HP');
  key('ArrowDown',true); key(k2,true);
  for(let i=0;i<400;i++) step(1);
  key('ArrowDown',false); key(k2,false);
  ok('garde + avancée', hp0-get('P1HP')<40, 'dégâts '+Math.round(hp0-get('P1HP'))+'/600 en 13 s de marche en garde');

  // 4) esquive au double-tap : glissade + invulnérabilité
  combat(230); const x0=get('P1X'); const k3=vers();
  key(k3,true); step(1); key(k3,false); step(3); key(k3,true); step(1);
  const vxDash=Math.abs(get('P1X')-x0), inv=V(J(),'invT');
  let glissade=0, invu=0;
  for(let i=0;i<20;i++){ step(1); if(V(J(),'dashT')>0)glissade++; if(V(J(),'invT')>0)invu++; }
  key(k3,false); step(20);
  ok('esquive (double-tap)', glissade>=6 && invu>=6,
     'glissade '+glissade+' images, invulnérabilité '+invu+' images, vitesse '+(vxDash>0?('x'+Math.round(vxDash)):'?'));
  // ... et pendant l'invulnérabilité une flèche ne fait aucun dégât
  combat(230); const hp2=get('P1HP');
  setV(J(),'invT',20); set('P1Hit',21); set('P1HitType','fleche'); set('P1HitDir',1); step(1);
  ok('flèche annulée pendant l\'esquive', Number(get('P1HP'))===Number(hp2) && Number(get('P1Hit'))===0,
     'HP '+hp2+' -> '+Math.round(get('P1HP'))+', Hit = '+get('P1Hit'));

  // 5) rechargement : pas deux flèches coup sur coup avec l'arc
  combat(230,99);                 // arc en main, rechargement en cours
  set('BotReaction',600); set('BotArme',1); set('BotAggro',0);   // bot tranquille
  set('P1Arme',5); set('P1ArmeOrig',5); setV(J(),'recharge',99); step(2);
  key('k',true); step(2); key('k',false); step(8);
  const refus = fleches(1)===0;
  setV(J(),'recharge',0); step(2); key('k',true); step(2); key('k',false); step(10);
  const tire = fleches(1)>0 && V(J(),'recharge')>10;
  ok('rechargement de l\'arc', refus && tire,
     'pendant le rechargement : '+(refus?'aucun tir':'tir !')+' | une fois prêt : '+
     (tire?'flèche + recharge '+Math.round(V(J(),'recharge')):'aucune flèche'));

  // 6) chute de dégâts avec la distance : se coller à l'arc est la bonne réponse
  //    (le joueur tire à l'arc ; le bot reste cloué sur place pour comparer les deux portées)
  const duelArc=(d)=>{
    set('scene','fight'); set('phase','fight'); set('phaseTimer',0); set('chrono',9000);
    set('P1HP',600); set('BotHP',600); set('P1Max',600); set('BotMax',600);
    set('P1Arme',5); set('P1ArmeOrig',5); set('niveau',6); set('BotArme',1);
    set('BotAggro',0); set('BotGarde',0); set('BotReaction',600); set('BotVitesse',0);
    setV(J(),'recharge',0); step(30);          // on laisse retomber les flèches encore en vol
    set('P1HP',600); set('BotHP',600); setV(J(),'recharge',0);
    const bx=60, px=bx-d;
    set('BotX',bx); set('BotY',-92); set('BotState','idle');
    set('P1X',px); set('P1Y',-92); set('P1Dir', px<bx?90:-90); step(2);
    const hpb=Number(get('BotHP'))||600;
    key('k',true); step(2); key('k',false);
    for(let i=0;i<90;i++){ step(1); set('BotX',bx); set('BotY',-92); set('BotState','idle');
                           set('P1Dir', px<bx?90:-90); }
    return Math.round(hpb-(Number(get('BotHP'))||600));
  };
  const dProche=duelArc(110), dLoin=duelArc(250);
  ok('dégâts qui chutent avec la distance', dLoin>0 && dLoin<dProche,
     'flèche à 110 px : '+dProche+' dégâts | à 250 px : '+dLoin+' dégâts');

  console.log(ko===0?'RESULTAT : OK':'RESULTAT : '+ko+' echec(s)');
  process.exit(ko===0?0:1);
}).catch(e=>{console.error(e);process.exit(1)});
