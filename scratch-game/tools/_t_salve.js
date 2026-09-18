const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
const get=k=>S().lookupVariableByNameAndType(k,'').value;
const botT=()=>vm.runtime.targets.find(t=>t.getName()==='Bot');
const cleanBot=()=>{['aiTimer','iBlock','iPunch','iKick','iSpecial','iJump','iMove'].forEach(v=>{const o=botT().lookupVariableByNameAndType(v,'');if(o)o.value=0;});};
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async ()=>{
  vm.start(); vm.greenFlag(); for(let i=0;i<5;i++)vm.runtime._step();
  const essai=(dist)=>{
    set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',600);
    set('P1HP',200); set('BotHP',200); set('P1Max',200); set('BotMax',200);
    set('P1Arme',5); set('BotArme',1); set('P1Special',100);
    cleanBot(); for(let i=0;i<7;i++)vm.runtime._step();
    set('phase','fight'); set('BotReaction',600); set('BotAggro',0); set('BotVitesse',0); set('hitStop',0);
    set('P1State','idle'); set('BotState','idle'); set('P1X',-200); set('BotX',-200+dist); set('P1Y',-92); set('BotY',-92);
    const BX=-200+dist;
    for(let i=0;i<2;i++){set('BotX',BX);vm.runtime._step();}
    console.log('--- salve à', dist, 'px ---');
    vm.postIOData('keyboard',{key:'l',isDown:true});
    for(let i=0;i<5;i++){set('BotX',BX);set('P1X',-200);vm.runtime._step();}
    vm.postIOData('keyboard',{key:'l',isDown:false});
    let lances=0;
    for(let i=0;i<130;i++){
      set('BotX',BX); set('P1X',-200); set('BotVitesse',0);
      const avant=vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='Fleche').length;
      vm.runtime._step();
      const apres=vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='Fleche');
      if(apres.length>avant) lances++;
      const xs=apres.map(t=>Math.round(t.lookupVariableByNameAndType('x','').value));
      if(apres.length>0&&i%2===0) console.log(String(i).padStart(2),'flèches',apres.length,xs.join(','),'HP',get('BotHP'));
    }
    console.log('flèches lancées:',lances,'| dégâts totaux:',200-get('BotHP'));
  };
  essai(70); essai(200);
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
