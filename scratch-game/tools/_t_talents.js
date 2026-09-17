// Arbre de talents : 1 point par niveau d'arme, deux voies par arme, choix modifiables,
// et effets réellement mesurés en combat (allonge, dégâts, rechargement, défense).
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM(); const R=new (require('./fakerender'))();
vm.attachRenderer(R); vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
let VT=1e12; Date.now=()=>VT;
let graine=246813579;
Math.random=()=>{ graine=(graine*1103515245+12345)%2147483648; return graine/2147483648; };
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{const o=S().lookupVariableByNameAndType(k,'');if(o)o.value=v;};
const get=k=>{const o=S().lookupVariableByNameAndType(k,'');return o&&o.value;};
const L=n=>S().lookupVariableByNameAndType(n,'list').value;
const J=()=>vm.runtime.targets.find(t=>t.getName()==='Joueur');
const V=(t,k)=>{const o=t.lookupVariableByNameAndType(k,'');return o&&o.value;};
const setV=(t,k,v)=>{const o=t.lookupVariableByNameAndType(k,'');if(o)o.value=v;};
const step=n=>{for(let i=0;i<n;i++){ VT+=33; vm.runtime._step(); }};
const clic=(x,y)=>{vm.postIOData('mouse',{x:x+240,y:180-y,isDown:true,canvasWidth:480,canvasHeight:360});step(1);
  vm.postIOData('mouse',{x:x+240,y:180-y,isDown:false,canvasWidth:480,canvasHeight:360});step(4);};
const key=(k,d)=>vm.postIOData('keyboard',{key:k,isDown:d});
const resetRound=()=>{ vm.runtime.startHats('event_whenbroadcastreceived', {BROADCAST_OPTION:'resetRound'}); step(3); };
let ko=0;
const ok=(nom,cond,detail)=>{ if(!cond)ko++; console.log((cond?'  ok   ':'  ECHEC'),nom,'->',detail); };
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async()=>{
  vm.start(); clearInterval(vm.runtime._steppingInterval); vm.runtime._steppingInterval=null;
  vm.runtime.currentStepTime=33; vm.greenFlag(); step(5); fs.mkdirSync('out',{recursive:true});
  const atelier=()=>{ set('scene','shop'); set('shopPage',3); step(4); };
  const pts=(k,voie)=>Number(L('talPts')[(k-1)*2+(voie==='B'?1:0)]);

  // ---- 1) placer des points (épée niveau 3 = 2 points), puis refus au-delà
  set('pieces',900); set('P1Arme',2); set('P1ArmeOrig',2); set('armeApercu',2);
  L('armePossede')[1]=1; L('armeNiveau')[1]=3;
  L('talPts').fill(0); set('message',''); atelier();
  clic(150,-40); clic(150,-40);
  const apres2=pts(2,'A');
  clic(150,-40);
  ok('placer les points', apres2===2 && pts(2,'A')===2 && /Plus de points/.test(String(get('message'))),
     '2 points en voie A, 3e clic refusé ('+get('message')+')');

  // ---- 2) les points sont propres à chaque arme (le marteau n'a rien)
  clic(0,62);                                    // sélection du marteau (3e bouton)
  const marteauVide=pts(4,'A')+pts(4,'B'), epeeIntacte=pts(2,'A');
  ok('points par arme', marteauVide===0 && epeeIntacte===2,
     'marteau : '+marteauVide+' point(s) | épée toujours à '+epeeIntacte);

  // ---- 3) choix modifiable : EFFACER rend les points et on réinvestit en voie B
  clic(150,-120);
  clic(150,-84); clic(150,-84);
  ok('choix modifiable (respec)', pts(2,'A')===0 && pts(2,'B')===2,
     'après EFFACER : voie A = '+pts(2,'A')+' | voie B = '+pts(2,'B')+' (2 points réinvestis)');
  R.toPNG('out/t_talents.png');

  // ---- 4) effet mesuré : voie B de l'épée = +0,4 vitesse, voie A = +12 allonge
  const combat=(arme,niveau,allocation)=>{
    set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',9000);
    set('P1HP',600); set('BotHP',600); set('P1Max',600); set('BotMax',600);
    set('P1Arme',arme); set('P1ArmeOrig',arme); set('niveau',1); set('BotArme',1);
    set('BotAggro',0); set('BotGarde',0); set('BotReaction',600); set('BotVitesse',0);
    L('armePossede')[arme-1]=1; L('armeNiveau')[arme-1]=niveau;
    L('talPts').fill(0);
    for(const [k,voie,n] of allocation) L('talPts')[(k-1)*2+(voie==='B'?1:0)]=n;
    step(8); set('phase','fight'); resetRound();
    set('P1State','idle'); set('BotState','idle'); set('P1X',-60); set('P1Y',-92); set('P1Dir',90);
    set('BotX',60); set('BotY',-92); set('BotDir',-90); set('BotReaction',600); set('BotVitesse',0); step(2);
  };
  // vitesse : 30 images de marche vers la droite
  const marche=()=>{ const x0=Number(get('P1X')); key('ArrowRight',true); step(30); key('ArrowRight',false); step(2);
    return Math.round((Number(get('P1X'))-x0)*10)/10; };
  combat(2,1,[]); const vSans=marche();
  combat(2,3,[[2,'B',2]]); const vAvec=marche();
  ok('voie "Danse" (+vitesse)', vAvec>vSans, 'sans talent : '+vSans+' px en 1 s | 2 points en voie B : '+vAvec+' px');

  // dégâts : marteau + voie "Broyeur" (+3 par point) sur un bot immobile
  const frappe=(niveau,points)=>{
    combat(4,niveau,[[4,'A',points]]);
    set('P1X',5); set('BotX',60); set('P1Y',-92); set('P1Dir',90); set('P1Special',100); step(2);
    const hp0=Number(get('BotHP'));
    key('l',true); step(2); key('l',false);
    for(let i=0;i<70;i++){ vm.runtime._step(); VT+=33; set('BotX',60); set('BotY',-92); set('BotState','idle'); set('P1Dir',90); }
    return Math.round(hp0-Number(get('BotHP')));
  };
  combat(4,2,[[4,'A',0]]); frappe(4,0);            // mise en place
  const dmg0=frappe(4,0), dmg4=frappe(4,4);
  ok('voie "Broyeur" (+dégâts de smash)', dmg4>dmg0, 'smash sans talent : '+dmg0+' | avec 4 points : '+dmg4+' dégâts (66 attendus)');

  // allonge : 4 points en "Estoc" (épée) doivent porter plus loin
  const touche=(points)=>{
    combat(2,1,[[2,'A',points]]);
    set('P1X',-100); set('BotX',60); set('P1Y',-92); set('P1Dir',90); step(2);   // 160 px : hors de portée sans talent
    const hp0=Number(get('BotHP'));
    key('k',true); step(2); key('k',false);
    for(let i=0;i<60;i++){ vm.runtime._step(); VT+=33; set('BotX',60); set('BotY',-92); set('BotState','idle'); set('P1Dir',90); }
    return Math.round(hp0-Number(get('BotHP')));
  };
  const allSans=touche(0), allAvec=touche(4);
  ok('voie "Estoc" (+allonge)', allSans===0 && allAvec>0,
     'coup de pied à 160 px : '+allSans+' dégâts sans talent | '+allAvec+' avec 4 points (+48 px)');

  // defense : bouclier + voie "Rempart" (-4 % par point)
  const encaisse=(points)=>{
    combat(6,2,[[6,'A',points]]);
    const hp0=Number(get('P1HP'));
    set('P1Hit',100); set('P1HitType','coup'); set('P1HitDir',1); step(1);
    return Math.round(hp0-Number(get('P1HP')));
  };
  const def0=encaisse(0), def4=encaisse(4);
  ok('voie "Rempart" (-dégâts subis)', def4<def0, '100 dégâts bruts : '+def0+' subis sans talent | '+def4+' avec 4 points (-16 % attendu)');

  // rechargement : arc + voie "Tir tendu" (-4 images par point)
  const rechargeDe=(points)=>{
    combat(5,3,[[5,'A',points]]);
    key('k',true); step(2); key('k',false); step(8);
    return Math.round(Number(V(J(),'recharge')));
  };
  const r0=rechargeDe(0), r4=rechargeDe(4);
  ok('voie "Tir tendu" (rechargement)', r4>0 && r4<r0-10,
     'rechargement après tir : '+r0+' images sans talent | '+r4+' avec 4 points');

  // ---- 5) le code de sauvegarde emporte les talents (36 chiffres)
  combat(4,4,[[4,'A',3],[4,'B',0]]);
  set('pieces',1234); set('niveauMax',5);
  set('scene','menu'); step(3); clic(28,-112); step(4);   // bouton SAUVER
  const code=String(get('codeSauvegarde')).replace(/[^0-9]/g,'');
  ok('code 36 chiffres', code.length===36, 'code = '+get('codeSauvegarde')+' ('+code.length+' chiffres)');
  // on remet tout à zéro puis on recharge
  L('talPts').fill(0); set('P1Arme',1);
  vm.runtime.on('QUESTION',q=>{ if(q!==null) setTimeout(()=>vm.runtime.emit('ANSWER', String(get('codeSauvegarde'))),1); });
  set('scene','menu'); step(3); clic(134,-112);
  for(let i=0;i<120;i++){ vm.runtime._step(); VT+=33; await new Promise(r=>setTimeout(r,0)); }  // ask-and-wait + chargement
  ok('talents restaurés par le code', pts(4,'A')===3,
     'après chargement : voie A du marteau = '+pts(4,'A')+' | info = '+get('infoSauvegarde'));
  console.log(ko===0?'RESULTAT : OK':'RESULTAT : '+ko+' echec(s)');
  process.exit(ko===0?0:1);
}).catch(e=>{console.error(e);process.exit(1)});
