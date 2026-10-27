from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api_routes import router

app = FastAPI(title="YottaFlex Liquidity Forecasting", version="0.1.0")
app.include_router(router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>YottaFlex Liquidity</title>
<style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem}
table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.4rem}
.card{border:1px solid #ddd;padding:1rem;margin:1rem 0;border-radius:8px}</style></head>
<body><h1>YottaFlex Liquidity Forecasting</h1>
<div id="summary" class="card">Loading summary...</div>
<div id="runs" class="card"><h2>Forecast runs</h2>Loading...</div>
<script>
async function load(){
 const summary=await fetch('/api/summary').then(r=>r.json());
 document.getElementById('summary').innerHTML='<h2>Dataset summary</h2><pre>'+
 JSON.stringify(summary,null,2)+'</pre>';
 const runs=await fetch('/api/forecast-runs').then(r=>r.json());
 document.getElementById('runs').innerHTML='<h2>Forecast runs</h2><table><tr><th>Run</th><th>Scenario</th><th>Version</th><th>Status</th></tr>'+
 runs.map(r=>'<tr><td>'+r.run_code+'</td><td>'+r.scenario_code+'</td><td>'+r.version+'</td><td>'+r.status+'</td></tr>').join('')+'</table>';
} load();
</script></body></html>"""
