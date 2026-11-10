#!/bin/bash
# Testes de interface (Node + jsdom) contra o servidor real.
# Requer: banco migrado e `ADMIN_PASSWORD=Admin@12345 python -m app.seed --demo` (dados de demonstração).
# Uso: bash run.sh [cenario ...]   (sem argumentos: todos)
cd "$(dirname "$0")/../../backend" || exit 1
python -m uvicorn app.main:app --port 8000 > /tmp/uvicorn-smoke.log 2>&1 &
UV=$!; for i in $(seq 1 40); do curl -s localhost:8000/api/publico/clinica >/dev/null && break; sleep 0.5; done
cd ../frontend/tests || exit 1; rc=0
SC=${@:-home procedimentos login cadastro portal fluxo meus dashboard dashdent dashrec agenda pacientes procs pros resto}
for s in $SC; do echo "== $s"; node scenarios.mjs "$s" 2>&1 | grep -vE "ExperimentalWarning|node --trace"; [ ${PIPESTATUS[0]} -ne 0 ] && rc=1; done
kill $UV 2>/dev/null; exit $rc
