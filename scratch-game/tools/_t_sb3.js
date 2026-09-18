const parser=require('scratch-parser'), fs=require('fs');
parser(fs.readFileSync('../dist/ArenaClash.sb3'), false, (err, proj)=>{ if(err){console.log('ERREURS SB3:',JSON.stringify(err).slice(0,1500));process.exit(1);} console.log('sb3 valide (scratch-parser) — cibles:',proj[0].targets.length,'| blocs:',proj[0].targets.reduce((a,t)=>a+Object.keys(t.blocks).length,0)); process.exit(0);});
