const routes = new Set(['social','email','sap','health','shopping','travel']);
export function proposal(text, answer) {
  const fallback = {route:'hermes', advisory:true, execute:false};
  if (typeof text !== 'string' || text.length > 800 || !text.trim() || !routes.has(answer?.choice)) return fallback;
  const values = Object.values(answer.probabilities ?? {});
  if (!values.length || values.some(p => !Number.isFinite(p) || p < 0 || p > 1)) return fallback;
  if (Math.abs(values.reduce((a,b) => a+b, 0)-1) > 0.002) return fallback;
  const best = answer.probabilities[answer.choice];
  const second = Math.max(0, ...Object.entries(answer.probabilities).filter(([k]) => k !== answer.choice).map(([,p]) => p));
  if (!Number.isFinite(best) || best < 0.95 || best-second < 0.25) return fallback;
  return {route:answer.choice, advisory:true, execute:false};
}
