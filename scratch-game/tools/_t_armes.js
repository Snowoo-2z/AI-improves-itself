const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
const R=new (require('./fakerender'))();
vm.attachRenderer(R);
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
const get=k=>S().lookupVariableByNameAndType(k,'').value;
const getL=(n,i)=>S().lookupVariableByNameAndType(n,'list').value[i-1];
const setL=(n,i,v)=>{S().lookupVariableByNameAndType(n,'list').value[i-1]=v;};
const step=n=>{for(let i=0;i<n;i++)vm.runtime._step();};
const key=(k,d)=>vm.postIOData('keyboard',{key:k,isDown:d});
const press=(k,frames)=>{key(k,true);step(frames);key(k,false);};
const cleanBot=()=>{const b=vm.runtime.targets.find(t=>t.getName()==='Bot');
  ['aiTimer','iBlock','iPunch','iKick','iSpecial','iJump','iMove'].forEach(v=>{const o=b.lookupVariableByNameAndType(v,''); if(o)o.value=0;});};
let reponse='', questionEnAttente=null;
vm.runtime.on('QUESTION',q=>{ if(q!==null) questionEnAttente=q; });
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async ()=>{
  vm.start(); vm.greenFlag(); fs.mkdirSync('out',{recursive:true}); step(5);
  const combat=(arme,botArme)=>{
    set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',600);
    set('P1HP',200); set('BotHP',200); set('P1Max',200); set('BotMax',200);
    set('P1Arme',arme); set('P1ArmeOrig',arme); set('BotArme',botArme);
    step(6); set('phase','fight'); set('P1X',-120); set('BotX',-50);
    set('P1State','idle'); set('BotState','idle'); cleanBot(); step(1);
  };
  // 1) boutique ARMES + achat
  set('pieces',1000); set('P1Arme',1); set('P1ArmeOrig',1); set('shopPage',2);
  set('scene','shop'); step(4); R.toPNG('out/a_shop_armes.png');
  const listArmes=()=>S().lookupVariableByNameAndType('armePossede','list').value;
  console.log('1) boutique ARMES : possédées =', JSON.stringify(listArmes()));
  // achat de l'épée (bouton 2 : x=0,y=72) -> clic souris
  const clic=(x,y)=>{vm.postIOData('mouse',{x:x+240,y:180-y,isDown:true,canvasWidth:480,canvasHeight:360});step(1);
                     vm.postIOData('mouse',{x:x+240,y:180-y,isDown:false,canvasWidth:480,canvasHeight:360});step(2);};
  clic(0,74); clic(0,74);
  // clic sur CHARGER + réponse à la question « colle ton code » (l'ANSWER doit être émis entre deux images)
  // le bloc « demander et attendre » rend une promesse : il faut laisser tourner
  // la boucle de micro-tâches entre deux images pour que le thread reparte
  const charger=async (code)=>{ reponse=code; clic(134,-116);
    for(let i=0;i<60;i++){ vm.runtime._step();
      if(questionEnAttente){ vm.runtime.emit('ANSWER',reponse); questionEnAttente=null; }
      await Promise.resolve(); } };
  console.log('   après achat+équipement : pièces =', get('pieces'), '| possédées =', JSON.stringify(listArmes()), '| P1Arme =', get('P1Arme'));
  // 2) combat : épée en main
  combat(2,1); step(3); R.toPNG('out/a_epee.png');
  console.log('2) épée : P1ArmeMain =', get('P1ArmeMain'), '| BotArmeMain =', get('BotArmeMain'), '| costume joueur =', vm.runtime.targets.find(t=>t.getName()==='Joueur').sprite.costumes[vm.runtime.targets.find(t=>t.getName()==='Joueur').currentCostume].name);
  // 3) marteau vs garde
  combat(4,1);
  set('BotReaction',600); set('BotGarde',100); set('BotAggro',0); set('P1Special',100);
  set('BotState','block'); set('BotDir',-90);
  for(let i=0;i<3;i++){vm.runtime._step(); set('BotState','block'); set('BotDir',-90);}
  const hp0=get('BotHP'); press('l',6); step(60);
  console.log('3) marteau vs garde : HP', hp0, '->', get('BotHP'), '(attendu 34*0.6=21) état bot =', get('BotState'));
  // 4) marteau vs garde AU SOL d'un défenseur au bouclier (le marteau perce : 60 %)
  combat(4,6);
  set('BotReaction',600); set('BotGarde',100); set('BotAggro',0); set('P1Special',100);
  const tenir=()=>{set('BotState','block'); set('BotDir',-90); set('BotX',-50); set('BotReaction',600);};
  set('BotState','block'); set('BotDir',-90);
  for(let i=0;i<3;i++){vm.runtime._step(); tenir();}
  const hp1=get('BotHP');
  vm.postIOData('keyboard',{key:'l',isDown:true});
  for(let i=0;i<5;i++){vm.runtime._step(); tenir();}
  vm.postIOData('keyboard',{key:'l',isDown:false});
  for(let i=0;i<60;i++){vm.runtime._step(); tenir();}
  console.log('4) marteau vs garde (bouclier) : HP', hp1, '->', get('BotHP'), '(perce : 21 attendu)');
  // 5) coup de pied bloqué par le bouclier : 5 % au lieu de 12 %
  combat(1,6);
  set('BotReaction',600); set('BotGarde',100); set('BotAggro',0);
  set('BotState','block'); set('BotDir',-90); step(2);
  const hp2=get('BotHP'); press('k',6); step(40);
  console.log('5) pied sans garde : HP', hp2, '->', get('BotHP'), '(11 attendu ; la garde du bouclier annule les dégâts bloqués)');
  // 6) arc : tir + dégâts
  combat(5,1);
  set('BotReaction',200); set('BotAggro',0); set('BotGarde',0);
  set('P1X',-150); set('BotX',60); step(2);
  const hp3=get('BotHP'); press('k',5);
  let vues=0; for(let i=0;i<45;i++){vm.runtime._step(); if(vm.runtime.targets.some(t=>!t.isOriginal&&t.sprite.name==='Fleche')){vues++; if(vues===4)R.toPNG('out/a_fleche.png');}}
  console.log('6) arc : frames avec flèche =', vues, '| HP bot', hp3, '->', get('BotHP'), '(13 attendu)');
  // 7) arc : salve du spécial (3 flèches)
  combat(5,1); set('BotReaction',300); set('BotAggro',0); set('P1X',-150); set('BotX',200);
  set('P1Special',100); step(2); press('l',6); step(30);
  const n=vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='Fleche').length;
  console.log('7) salve arc : flèches simultanées =', n);
  step(60); R.toPNG('out/a_salve.png');
  console.log('   HP bot après salve =', get('BotHP'));
  // 8) plus aucune arme au sol : sprites ArmeSol absents et rien ne doit apparaître en combat
  combat(1,1);
  const solSprites=vm.runtime.targets.filter(t=>/ArmeSol/.test(t.sprite.name)).length;
  let apparues=0;
  for(let i=0;i<300;i++){ vm.runtime._step();
    apparues += vm.runtime.targets.filter(t=>t.isOriginal&&/ArmeSol/.test(t.sprite.name)&&t.visible).length; }
  console.log('8) armes au sol : sprites =', solSprites, '| apparitions visibles en 300 images =', apparues,
              '| variables sol* =', ['solArme','solX','solY','solTimer'].filter(v=>S().lookupVariableByNameAndType(v,'')||S().lookupVariableByNameAndType(v,'list')).length);
  // 9) sauvegarde : clic sur SAUVER au menu
  set('scene','menu'); set('pieces',900); set('niveauMax',5); set('P1Arme',5); set('P1ArmeOrig',5);
  setL('armePossede',2,1); setL('armePossede',5,1);
  step(3); clic(28,-116); step(3);
  const code=get('codeSauvegarde');
  console.log('9) code de sauvegarde =', code, '(', code.replace(/-/g,'').length, 'chiffres, 36 attendus ; niveaux =', S().lookupVariableByNameAndType('armeNiveau','list').value.join(''), ')');
  // 10) rechargement du code : arme retrouvée
  set('pieces',10); set('niveauMax',1); set('P1Arme',1); set('P1ArmeOrig',1);
  setL('armePossede',2,0); setL('armePossede',5,0);
  set('scene','menu'); step(2);
  await charger(code);
  console.log('10) après chargement : niveauMax =', get('niveauMax'), '| pièces =', get('pieces'), '| P1Arme =', get('P1Arme'),
              '| possédées =', JSON.stringify(listArmes()), '|', get('infoSauvegarde'));
  // 11) ancien code 15 chiffres (compatibilité)
  set('niveauMax',1); set('pieces',0);
  await charger('5-01234-001-01-94-11');
  console.log('11) ancien code : niveauMax =', get('niveauMax'), '| pièces =', get('pieces'), '| P1Arme =', get('P1Arme'), '|', get('infoSauvegarde'));
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
