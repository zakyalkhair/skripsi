# Panduan Modul 4 (GraphRAG: laporan situasi + tanya-jawab)

Prasyarat: Modul 3 sudah menghasilkan CSV (`python -m modul3 proses`) dan/atau graf di Neo4j (`python -m modul3 muat`).
`.env` berisi `NEO4J_*`, `CEREBRAS_API_KEY`, `GROQ_API_KEY` (lihat `.env.example`).

1. Cek nama model yang benar-benar tersedia di akunmu:  `python -m modul4 modelku`
2. Uji tanpa Neo4j dan tanpa LLM:  `python -m modul4 korpus --backend csv` lalu `python -m modul4 laporan --semua --tanpa-llm --backend csv`
3. Penuh (Neo4j + LLM). Penjawab dan hakim HARUS model berbeda:

       python -m modul4 korpus
       python -m modul4 laporan --semua --gen groq:openai/gpt-oss-120b
       python -m modul4 tanya "Berapa korban banjir di Aceh Tamiang?" --gen groq:openai/gpt-oss-120b
       python -m modul4 evaluasi --soal dev_2025/data/modul4/soal_draf.jsonl --gen groq:openai/gpt-oss-120b --judge groq:qwen/qwen3.8-27b
       python -m modul4 semua

   Kena batas laju? tambahkan `--cadangan groq:openai/gpt-oss-20b (sudah bawaan)`. Konteks per jawaban dibatasi `--maks-konteks` (karakter).
4. Keluaran di `dev_2025/data/modul4/`: `korpus_manifest.json`, `laporan/*.md`, `evaluasi_qa.csv`, `evaluasi_ringkasan.json`, `log_llm.jsonl` (model, provider, waktu, token tiap panggilan).

Soal gold: tulis sendiri `soal.jsonl`, satu baris per soal: `{"id":"Q1-001","kelompok":"Q1","pertanyaan":"...","nugget":["2025-12-02"],"event_id":null,"sumber":"manual"}`; Q5 memakai `"nugget":["ABSTAIN"]`.
