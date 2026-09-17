// Les bots ont aussi un niveau d'arme (dernière colonne de la table BOTS) : leurs dégâts
// doivent en tenir compte. Ici Rosa (arc) tire sur un joueur passif : niveau 2 -> 17 par
// flèche (13 + 2 + 1x2), niveau 5 -> 23 (13 + 2 + 4x2).
const VM=require('scratch-vm'), fs=require('fs');
const charger=()=>{const vm=new VM(); vm.attachRenderer(new (require('./fakerender'))());
  vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
  return vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(()=>vm);};
const step=(vm,n)=>{for(let i=0;i<n;i++)vm.runtime._step();};
const tir=(vm,niveauRosa)=>{const S=()=>vm.runtime.getTargetForStage();
  const set=(k,v)=>{S().lookupVariableByNameAndType(k,'').value=v;};
  const get=k=>{const v=S().lookupVariableByNameAndType(k,'')||S().lookupVariableByNameAndType(k,'list');return v&&v.value;};
  S().lookupVariableByNameAndType('botArmeNiv','list').value[5]=niveauRosa;   // Rosa = bot n°6
  set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',20000);
  set('P1HP',4000); set('BotHP',4000); set('P1Max',4000); set('BotMax',4000);
  set('P1Arme',1); set('P1ArmeOrig',1); set('niveau',6); set('BotArme',5);
  set('BotAggro',100); set('BotReaction',10); set('BotGarde',0);
  step(vm,6); set('phase','fight');
  const hp0=get('P1HP'); let fleches=0, avant=0, touches=0;
  for(let i=0;i<1200;i++){ vm.runtime._step();
    set('P1X',190); set('P1Y',-92); set('P1State','idle'); set('BotHP',4000);
    // une flèche qui touche laisse P1Hit > 0 le temps d'une image (le joueur l'applique ensuite)
    if(get('P1Hit')>0) touches++;
    const nb=vm.runtime.targets.filter(t=>!t.isOriginal&&t.sprite.name==='Fleche').length;
    if(nb>avant) fleches+=nb-avant; avant=nb; }
  return {niveau:niveauRosa, fleches, touches, degats:hp0-get('P1HP')};};
(async()=>{
  fs.mkdirSync('out',{recursive:true});
  const v0=await charger(); v0.start(); v0.greenFlag(); step(v0,5);
  const S0=()=>v0.runtime.getTargetForStage();
  const L=n=>S0().lookupVariableByNameAndType(n,'list').value;
  console.log('1) niveau d\'arme des bots :');
  L('botNom').forEach((n,i)=>console.log(`   ${n} — ${L('armeNom')[L('botArme')[i]-1]} niveau ${L('botArmeNiv')[i]}`));
  for(const niveau of [2,5]){
    const vm=await charger(); vm.start(); vm.greenFlag(); step(vm,5);
    const r=tir(vm,niveau);
    const attendu=13+2+(niveau-1)*2;
    console.log(`${niveau===2?'2)':'3)'} Rosa arc niveau ${niveau} : ${r.fleches} flèches, ${r.touches} touches, ${r.degats} dégâts → ${(r.degats/Math.max(1,r.touches)).toFixed(2)} par touche (attendu ${attendu})`);
  }
  process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
