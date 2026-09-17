// Boutique ARMES : achat -> équipement -> amélioration jusqu'au niveau 5.
// Vérifie aussi l'effet réel des niveaux sur les dégâts, le plafond du niveau 5,
// le manque de pièces, et l'aller-retour dans le code de sauvegarde.
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM(); const R=new (require('./fakerender'))();
vm.attachRenderer(R); vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
const get=k=>{const v=S().lookupVariableByNameAndType(k,'')||S().lookupVariableByNameAndType(k,'list');return v&&v.value;};
const L=n=>S().lookupVariableByNameAndType(n,'list').value;
const LV=i=>L('armeNiveau')[i-1];
const step=n=>{for(let i=0;i<n;i++)vm.runtime._step();};
const clic=(x,y)=>{vm.postIOData('mouse',{x:x+240,y:180-y,isDown:true,canvasWidth:480,canvasHeight:360});step(1);
  vm.postIOData('mouse',{x:x+240,y:180-y,isDown:false,canvasWidth:480,canvasHeight:360});step(3);};
let question=null;
vm.runtime.on('QUESTION',q=>{if(q!==null)question=q;});
const charger=async(code)=>{clic(134,-112);
  for(let i=0;i<80;i++){vm.runtime._step(); if(question){vm.runtime.emit('ANSWER',code);question=null;} await Promise.resolve();}};
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async()=>{
  vm.start(); vm.greenFlag(); step(5); fs.mkdirSync('out',{recursive:true});
  const boutique=()=>{set('scene','shop'); set('shopPage',2); step(4);};
  // ---- 1) achat puis équipement (la grille : 3 armes en haut y=74, 3 en bas y=38)
  set('pieces',1000); set('P1Arme',1); set('P1ArmeOrig',1); boutique(); R.toPNG('out/u_armes1.png');
  clic(0,74); clic(0,74);
  console.log('1) achat épée : possédée =', L('armePossede')[1], '| niveau =', LV(2), '| pièces =', get('pieces'),
              '| équipée =', get('P1Arme'));
  // ---- 2) amélioration : 200 -> 40+80+120+160 = 400 pièces pour atteindre le niveau 5
  set('armeApercu',2);
  const avant=get('pieces');
  clic(60,-100);
  console.log('2) 1re amélioration : niveau =', LV(2), '| pièces =', avant, '->', get('pieces'), '(coût 40)');
  R.toPNG('out/u_armes2.png');
  let n=1; while(LV(2)<5 && n<8){ clic(60,-100); n++; }
  console.log('3) montée au niveau max : niveau =', LV(2), '| pièces =', get('pieces'), '|', avant-get('pieces'), 'dépensées (400 attendues)');
  // ---- 4) plafond : le bouton d'amélioration disparaît, cliquer ne dépense rien
  const p4=get('pieces');
  clic(60,-100); clic(60,-100);
  console.log('4) au-delà du niveau 5 : niveau =', LV(2), '| pièces =', p4, '->', get('pieces'), '(inchangé)');
  R.toPNG('out/u_armes3.png');
  // ---- 5) pas assez de pièces
  set('pieces',10); L('armePossede')[3]=1; set('armeApercu',4); set('message',''); step(3);
  clic(60,-100);
  console.log('5) amélioration sans pièces (coût 50) : niveau marteau =', LV(4), '| message =', JSON.stringify(get('message')));
  // ---- 6) les niveaux changent vraiment les dégâts
  const combat=(arme)=>{ set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',900);
    set('P1HP',400); set('BotHP',400); set('P1Max',400); set('BotMax',400);
    set('P1Arme',arme); set('P1ArmeOrig',arme); step(6); set('phase','fight');
    set('P1X',-140); set('BotX',-80); set('P1Y',-92); set('BotY',-92); set('P1Dir',90);
    const b=vm.runtime.targets.find(t=>t.getName()==='Bot');
    ['iBlock','iPunch','iKick','iSpecial','iJump','iMove'].forEach(v=>{const o=b.lookupVariableByNameAndType(v,'');if(o)o.value=0;});
    set('BotReaction',9999); set('BotAggro',0); set('BotGarde',0);
    // le bot reste à sa place (sinon il recule entre deux images)
    for(let i=0;i<3;i++)vm.runtime._step(); };
  const frappe=(t)=>{ const hp=get('BotHP');
    const tenir=()=>{set('BotState','idle'); set('BotDir',-90); set('BotX',-80); set('BotY',-92); set('BotReaction',9999);};
    vm.postIOData('keyboard',{key:t,isDown:true});
    for(let i=0;i<6;i++){vm.runtime._step();tenir();}
    vm.postIOData('keyboard',{key:t,isDown:false});
    for(let i=0;i<60;i++){vm.runtime._step();tenir();}
    return Math.round(hp-get('BotHP')); };
  const mesure=(arme,lbl)=>{ combat(arme); const p=frappe('j'); combat(arme); const k=frappe('k');
    combat(arme); set('P1Special',100); const s=frappe('l');
    return `${lbl} : poing ${p}, pied ${k}, spécial ${s}`; };
  LV(1); console.log('6) dégâts à mains nues (niveau 1) —', mesure(1,'poings'));
  LV(2); console.log('   épée niveau 5 —', mesure(2,'épée'), '(9 / 13 / 26 au niveau 1)');
  // ---- 7) sauvegarde : les niveaux partent dans le code et reviennent
  set('scene','menu'); set('pieces',1500); set('niveauMax',6); step(3); clic(28,-112); step(3);
  const code=get('codeSauvegarde');
  console.log('7) code =', code, '|', code.replace(/-/g,'').length, 'chiffres (36 attendus)');
  LV(2); L('armeNiveau')[1]=1; set('pieces',0); set('scene','menu'); step(2);
  await charger(code);
  console.log('8) après chargement : épée niveau =', LV(2), '| pièces =', get('pieces'), '|', get('infoSauvegarde'));
  // ---- 8) anciens codes toujours acceptés (18 et 15 chiffres)
  await charger('5-00900-001-01-1-1-19-4-02');
  console.log('9) code 18 chiffres : niveauMax =', get('niveauMax'), '| pièces =', get('pieces'),
              '| niveaux =', get('armeNiveau').join(''), '|', get('infoSauvegarde'));
  await charger('5-01234-001-01-94-11');
  console.log('10) code 15 chiffres : niveauMax =', get('niveauMax'), '| pièces =', get('pieces'), '|', get('infoSauvegarde'));
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
