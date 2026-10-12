(function(root){
function summarize(samples){if(!samples.length)return {average:0,density:'No traffic',green:0};const end=samples[samples.length-1].time;const window=samples.filter(s=>s.time>=end-10);const average=window.reduce((sum,s)=>sum+s.count,0)/window.length;return {average,density:average===0?'No traffic':average<=5?'Low':average<=15?'Moderate':'High',green:average===0?0:Math.min(60,Math.max(10,Math.ceil(average*3)))};}
root.TrafficInsights={summarize};if(typeof module!=='undefined')module.exports=root.TrafficInsights;
})(globalThis);
