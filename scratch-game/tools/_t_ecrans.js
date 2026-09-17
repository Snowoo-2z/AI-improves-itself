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
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
