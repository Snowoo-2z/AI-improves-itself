// node play.js ../dist/ArenaClash.sb3 script.json  — rejoue un scénario dans la VM Scratch et capture des écrans dans out/
const VM=require('scratch-vm');const fs=require('fs');const FakeRenderer=require('./fakerender');
const vm=new VM();const R=new FakeRenderer();vm.attachRenderer(R);vm.attachStorage(new (require('scratch-storage').ScratchStorage)());
fs.mkdirSync('out',{recursive:true});
const script=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
vm.runtime.on('QUESTION',q=>{if(q!==null&&script.answer!==undefined)setTimeout(()=>vm.runtime.emit('ANSWER',script.answer),1)});
vm.loadProject(fs.readFileSync(process.argv[2])).then(async()=>{
  vm.start();vm.greenFlag();
  const s=v=>vm.runtime.getTargetForStage().lookupVariableByNameAndType(v,'').value;
  const tick=n=>new Promise(r=>{let i=0;const h=setInterval(()=>{vm.runtime._step();if(++i>=n){clearInterval(h);r()}},1)});
  const list=(n)=>vm.runtime.getTargetForStage().lookupVariableByNameAndType(n,'list').value;
  const evalCond=(expr)=>{const m=/^([A-Za-z0-9_]+)\s*([<>])\s*(-?[\d.]+)$/.exec(expr);
    if(!m)return false;const v=+s(m[1]);return m[2]==='<'?v<+m[3]:v>+m[3];};
  for(const a of (script.steps||script)){
    if(a.mouse)vm.postIOData('mouse',{x:a.mouse[0]+240,y:180-a.mouse[1],isDown:!!a.down,canvasWidth:480,canvasHeight:360});
    if(a.key)vm.postIOData('keyboard',{key:a.key,isDown:!!a.down});
    if(a.set){const t=vm.runtime.getTargetForStage();for(const k in a.set)t.lookupVariableByNameAndType(k,'').value=a.set[k];}
    if(a.list){for(const k in a.list)list(k).splice(0,list(k).length,...a.list[k]);}
    if(a.answer!==undefined)script.answer=a.answer;
    if(a.hold){vm.postIOData('keyboard',{key:a.hold,isDown:true});await tick(a.frames||5);
      vm.postIOData('keyboard',{key:a.hold,isDown:false});}
    if(a.loop){for(let i=0;i<(a.loop.frames||60);i++){const e=a.loop.each||{};
      for(const k in e.set)s(k)===undefined?null:(vm.runtime.getTargetForStage().lookupVariableByNameAndType(k,'').value=e.set[k]);
      vm.runtime._step();if(a.loop.stop&&evalCond(a.loop.stop))break;}}
    await tick(a.wait||3);
    if(a.name)R.toPNG('out/'+a.name+'.png');
    if(a.shot)R.toPNG('out/'+a.shot+'.png');
    if(a.dump)console.log((a.name||'').padEnd(14), a.dump.map(k=>k+'='+s(k)).join('  '));
  }
  process.exit(0)}).catch(e=>{console.error(e);process.exit(1)});
