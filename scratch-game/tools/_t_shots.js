const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
const R=new (require('./fakerender'))();
vm.attachRenderer(R);
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
const get=k=>S().lookupVariableByNameAndType(k,'').value;
const step=n=>{for(let i=0;i<n;i++)vm.runtime._step();};
const souris=(x,y,down)=>vm.postIOData('mouse',{x:x+240,y:180-y,isDown:!!down,canvasWidth:480,canvasHeight:360});
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async ()=>{
  vm.start(); vm.greenFlag(); step(5); fs.mkdirSync('out',{recursive:true});
  // 1) boutique ARMES
  set('pieces',1000); set('shopPage',2); set('P1ArmeOrig',1); set('P1Arme',1); set('armeApercu',1);
  S().lookupVariableByNameAndType('armePossede','list').value=[1,0,0,0,1,0];
  set('scene','shop'); souris(-400,-400,false); step(6);
  R.toPNG('out/s_shop_armes.png');
  // 2) survol du marteau (aperçu + combattant)
  souris(-160,12,false); step(6);
  console.log('aperçu après survol =', get('armeApercu'));
  R.toPNG('out/s_shop_marteau.png');
  // 3) combat : marteau en main, smash
  set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',600);
  set('P1HP',200); set('BotHP',200); set('P1Max',200); set('BotMax',200);
  set('P1Arme',4); set('BotArme',2); set('P1Special',100);
  step(7); set('phase','fight'); set('P1State','idle'); set('BotState','idle');
  set('P1X',-150); set('BotX',-60); set('P1Y',-92); set('BotY',-92);
  set('BotReaction',600); set('BotAggro',0); set('BotVitesse',0);
  step(2);
  vm.postIOData('keyboard',{key:'l',isDown:true}); step(5); vm.postIOData('keyboard',{key:'l',isDown:false});
  for(let i=0;i<60;i++){set('BotX',-60);set('P1X',-150);vm.runtime._step(); if(get('BotHP')<200) break;}
  step(4);
  console.log('HP bot après smash =', get('BotHP'), '| arme en main =', get('P1ArmeMain'), get('BotArmeMain'));
  R.toPNG('out/s_marteau.png');
  // 4) arc : flèche en vol
  set('scene','fight'); set('phase','intro'); set('phaseTimer',2);
  set('P1HP',200); set('BotHP',200); set('P1Arme',5); set('BotArme',6); set('P1Special',0);
  step(7); set('phase','fight'); set('P1State','idle'); set('BotState','idle');
  set('P1X',-170); set('BotX',60); set('BotReaction',300); set('BotAggro',0); set('BotVitesse',0);
  step(2); vm.postIOData('keyboard',{key:'k',isDown:true}); step(5); vm.postIOData('keyboard',{key:'k',isDown:false});
  for(let i=0;i<14;i++){set('BotX',60);set('P1X',-170);vm.runtime._step();}
  R.toPNG('out/s_fleche.png');
  // 5) arme au sol + ramassage
  set('scene','fight'); set('phase','intro'); set('phaseTimer',2);
  set('P1Arme',1); set('P1ArmeOrig',1); set('BotArme',1); set('P1HP',200); set('BotHP',200);
  const L=(n)=>S().lookupVariableByNameAndType(n,'list').value;
  L('solArme')[0]=3; L('solX')[0]=-120; L('solY')[0]=-92; L('solTimer')[0]=0;
  L('solArme')[1]=5; L('solX')[1]=120;  L('solY')[1]=-92; L('solTimer')[1]=0;
  step(7); set('phase','fight'); set('P1State','idle'); set('BotState','idle');
  set('P1X',-40); set('BotX',150); set('BotVitesse',0); step(3);
  R.toPNG('out/s_sol.png');
  // 6) écran de sauvegarde (code 18 chiffres)
  set('niveauMax',5); set('pieces',1234); set('P1Arme',5); set('P1ArmeOrig',5);
  L('armePossede')[4]=1;
  set('scene','menu'); souris(-400,-400,false); step(3);
  souris(28,-112,true); step(1); souris(28,-112,false); step(4);
  console.log('scene =', get('scene'), '| code =', get('codeSauvegarde'));
  R.toPNG('out/s_code.png');
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
