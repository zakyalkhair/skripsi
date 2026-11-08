# Dashboard dengan data nyata (Modul 1-4 -> Modul 5)

Jalankan dari root repo (Windows PowerShell / terminal biasa).

1. Konsolidasi (Modul 3.1-3.2) dan ingest Neo4j (opsional untuk dashboard mode file):
   python -m modul3 proses
   python -m modul3 muat        # hanya bila ingin Neo4j / jalur backend neo4j

2. Ekspor ke format dashboard:
   python -m modul3.ke_dashboard
   (menghasilkan dashboard/data/nyata/graf.json dan gazetteer.json, metadata contoh=false)

3. Isi dashboard/backend/.env:
   GRAPHRAG=1
   GRAPHRAG_GEN=groq:openai/gpt-oss-120b
   GRAPHRAG_CADANGAN=groq:openai/gpt-oss-20b
   M4_BACKEND=csv
   (GROQ_API_KEY ada di .env root repo)

4. Backend (dari dashboard/backend), PowerShell:
   $env:CONTOH_DIR="../data/nyata"; $env:GAZETTEER_FILE="../data/nyata/gazetteer.json"
   uvicorn app.main:app --port 8000

5. Frontend (dari dashboard/frontend):
   npm run dev     # buka http://localhost:5173

6. (Opsional) laporan 4.3 tersimpan: python -m modul4 laporan --semua
