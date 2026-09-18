const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
const R=new (require('./fakerender'))();
vm.attachRenderer(R);
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
const step=n=>{for(let i=0;i<n;i++)vm.runtime._step();};
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async ()=>{
  vm.start(); vm.greenFlag(); step(6);
  fs.mkdirSync('out',{recursive:true});
  ['menu','commandes','select'].forEach(sc=>{ set('scene',sc); step(5); R.toPNG('out/v_'+sc+'.png'); });
  set('scene','shop'); set('shopPage',1); set('pieces',500); step(5); R.toPNG('out/v_shop_look.png');
  set('shopPage',2); set('armeApercu',4); step(5); R.toPNG('out/v_shop_armes.png');
  // écran de sauvegarde avec un vrai code (bouton SAUVER du menu)
  set('scene','menu'); set('niveauMax',5); set('pieces',1234); set('P1Arme',5); set('P1ArmeOrig',5); step(4);
  vm.postIOData('mouse',{x:28+240,y:180+116,isDown:true,canvasWidth:480,canvasHeight:360}); step(1);
  vm.postIOData('mouse',{x:28+240,y:180+116,isDown:false,canvasWidth:480,canvasHeight:360}); step(6);
  R.toPNG('out/v_save.png');
  console.log('code affiché :', S().lookupVariableByNameAndType('codeSauvegarde','').value);
  console.log('captures d\'écrans écrites dans out/v_*.png (menu, commandes, select, boutique LOOK/ARMES, sauvegarde)');
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
