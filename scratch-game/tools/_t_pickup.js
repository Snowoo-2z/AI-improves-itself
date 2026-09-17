const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
const getL=(n,i)=>S().lookupVariableByNameAndType(n,'list').value[i-1];
const setL=(n,i,v)=>{S().lookupVariableByNameAndType(n,'list').value[i-1]=v;};
const joueur=()=>vm.runtime.targets.find(t=>t.getName()==='Joueur');
const step=n=>{for(let i=0;i<n;i++)vm.runtime._step();};
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async ()=>{
  vm.start(); vm.greenFlag(); step(5);
  set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',600);
  set('P1HP',200); set('BotHP',200); set('P1Arme',1); set('P1ArmeOrig',1);
  set('P1ArmeOrig',1); set('BotArme',1);
  step(6); set('phase','fight'); set('P1X',-120); set('BotX',120); set('P1Y',-92);
  setL('solArme',1,4); setL('solX',1,-120); setL('solY',1,-92); setL('solTimer',1,0);
  setL('solArme',2,0); setL('solTimer',2,0);
  for(let i=0;i<8;i++){
    vm.runtime._step();
    console.log(i,'P1Arme=',S().lookupVariableByNameAndType('P1Arme','').value,
      'solArme=',getL('solArme',1),getL('solArme',2),'timer=',getL('solTimer',1),
      'X=',Math.round(S().lookupVariableByNameAndType('P1X','').value),
      'phase=',S().lookupVariableByNameAndType('phase','').value);
  }
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
