// i18n : au drapeau vert on choisit français ou anglais ; le menu, la sélection,
// les noms de bots, le combat et la boîte de dialogue de sauvegarde suivent la langue.
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
let VT=1e12; Date.now=()=>VT;
let question=null;
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{const o=S().lookupVariableByNameAndType(k,'');o.value=v;};
const get=k=>{const o=S().lookupVariableByNameAndType(k,'');return o&&o.value;};
const step=n=>{for(let i=0;i<n;i++){VT+=33;vm.runtime._step();}};
const clic=(x,y)=>{vm.postIOData('mouse',{x:x+240,y:180-y,isDown:true,canvasWidth:480,canvasHeight:360});step(2);
  vm.postIOData('mouse',{x:x+240,y:180-y,isDown:false,canvasWidth:480,canvasHeight:360});step(4);};
const attendreQuestion=(max)=>{let i=0; while(!question && i++<(max||60)){ vm.runtime._step(); VT+=33; } };
// « demander et attendre » rend une promesse : il faut faire tourner la boucle de
// micro-tâches entre deux images pour que le thread reparte après la réponse.
const repondre=async(code)=>{
  vm.runtime.emit('ANSWER',code); question=null;
  for(let i=0;i<30;i++){ vm.runtime._step(); VT+=33; await Promise.resolve(); }
  step(3);
};
let ko=0;
const ok=(nom,cond,detail)=>{ if(!cond)ko++; console.log((cond?'  ok   ':'  ECHEC'),nom,'->',detail); };
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async()=>{
  vm.runtime.currentStepTime=33;
  vm.runtime.on('QUESTION',q=>{ if(q!==null) question=q; });
  vm.greenFlag(); step(8); fs.mkdirSync('out',{recursive:true});

  // 1) après le drapeau vert : l'écran de choix de langue
  ok('écran initial = LANGUE', get('scene')==='langue', 'scene = '+get('scene'));
  step(2); vm.runtime.renderer.toPNG('out/l_langue.png');

  // 2) clic ENGLISH -> menu en anglais
  clic(0,-68);
  ok('EN choisi', get('langue')==='en', 'langue = '+get('langue'));
  ok('retour au menu', get('scene')==='menu', 'scene = '+get('scene'));
  step(4);
  ok('menu en anglais', get('trR')==='Max level: ', 'trR = '+get('trR'));
  vm.runtime.renderer.toPNG('out/l_menu_en.png');

  // 3) sélection + nom du bot traduit
  clic(80,20);
  ok('PLAY -> sélection', get('scene')==='select', 'scene = '+get('scene'));
  step(3);
  set('niveauMax',8); set('niveau',8); step(3);
  vm.runtime.renderer.toPNG('out/l_select_en.png');
  clic(10,-81);
  ok('bot 8 en anglais', get('BotNom')==='The Champion', 'BotNom = '+get('BotNom'));
  step(12);
  vm.runtime.renderer.toPNG('out/l_fight_en.png');

  // 4) relancer le drapeau : le choix reparaît, cette fois français
  vm.greenFlag(); step(8);
  ok('re-choix au re-lancement', get('scene')==='langue', 'scene = '+get('scene'));
  clic(0,8);
  ok('FR choisi', get('langue')==='fr' && get('scene')==='menu', 'langue = '+get('langue'));
  step(4);
  ok('menu en français', get('trR')==='Niveau max : ', 'trR = '+get('trR'));
  vm.runtime.renderer.toPNG('out/l_menu_fr.png');

  // 5) la boîte de dialogue de sauvegarde suit la langue (FR ici) + toast de la boutique
  clic(134,-116);
  attendreQuestion();
  ok('invite en français', question==='Colle ton code de sauvegarde puis appuie sur Entrée :', 'question = '+question);
  await repondre('0000000000000000');
  ok('code invalide détecté', get('infoSauvegarde')==='msg_charge_bad', 'info = '+get('infoSauvegarde'));
  set('pieces',0); set('scene','shop'); set('shopPage',1); step(4);
  clic(80,72);  // accessoire non possédé sans pièces -> toast
  ok('toast en français', get('message')==='Pas assez de pièces !', 'message = '+get('message'));
  vm.runtime.renderer.toPNG('out/l_shop_fr.png');

  // 6) idem en anglais
  vm.greenFlag(); step(8);
  clic(0,-68); step(4);
  clic(134,-116);
  attendreQuestion();
  ok('invite en anglais', question==='Paste your save code then press Enter:', 'question = '+question);
  await repondre('0000000000000000');
  ok('code invalide en anglais', get('infoSauvegarde')==='msg_charge_bad', 'info = '+get('infoSauvegarde'));
  set('pieces',0); set('scene','shop'); set('shopPage',1); step(4);
  clic(80,72);
  ok('toast en anglais', get('message')==='Not enough coins!', 'message = '+get('message'));
  vm.runtime.renderer.toPNG('out/l_shop_en.png');

  console.log(ko===0?'RESULTAT : OK':'RESULTAT : '+ko+' echec(s)');
  process.exit(ko===0?0:1);
}).catch(e=>{console.error(e);process.exit(1);});
