// Smoke test : un round complet joué par les IA, jusqu'au résultat (armes au sol comprises).
const VM=require('scratch-vm'), fs=require('fs');
const vm=new VM();
vm.attachRenderer(new (require('./fakerender'))());
vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
const S=()=>vm.runtime.getTargetForStage();
const get=k=>{const o=S().lookupVariableByNameAndType(k,'');return o?o.value:undefined;};
const set=(k,v)=>{const o=S().lookupVariableByNameAndType(k,''); if(o)o.value=v;};
const L=n=>S().lookupVariableByNameAndType(n,'list').value;
const step=n=>{for(let i=0;i<n;i++)vm.runtime._step();};
vm.loadProject(fs.readFileSync('../dist/ArenaClash.sb3')).then(async ()=>{
  vm.start(); vm.greenFlag(); step(30);
  set('niveauMax',8); set('niveau',3); set('scene','select'); step(5);
  // lance le combat contre le bot 3 (Arc) et laisse les deux IA se battre
  set('P1Arme',3); set('P1ArmeOrig',3);
  set('scene','fight'); set('phase','intro'); set('phaseTimer',2); set('chrono',600);
  set('BotHP',200); set('BotMax',200); set('P1HP',200); set('P1Max',200);
  // le joueur reste immobile : un bot agressif doit lui prendre les rounds
  set('BotAggro',80); set('BotGarde',40); set('BotReaction',12);
  step(10);
  let ramassages=0, avant=L('solArme').slice();
  let fini=null;
  for(let i=0;i<9000 && !fini;i++){
    vm.runtime._step();
    if(i%900===0) console.log('   t='+i, 'phase', get('phase'), 'chrono', get('chrono'), 'hitStop', get('hitStop'), 'msg', JSON.stringify(get('message')));
    const apres=L('solArme');
    if(avant[0]!==apres[0]||avant[1]!==apres[1]){ ramassages++; avant=apres.slice(); }
    if(get('scene')==='result') fini=i;
  }
  console.log('combat terminé en', fini, 'images (', fini?Math.round(fini/30)+'s':'DÉPASSEMENT', ') | résultat =', get('resultat'), '| scène =', get('scene'),
              '| HP joueur', get('P1HP'), '/ bot', get('BotHP'));
  console.log('changements d\'arme au sol :', ramassages, '| armes restantes :', JSON.stringify(L('solArme')),
              '| arme bot =', get('BotArmeMain'), '| arme joueur =', get('P1ArmeMain'));
  console.log('victoires joueur', get('victoiresP1'), '/ bot', get('victoiresBot'), '| pièces gagnées =', get('pieces'));
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1)});
