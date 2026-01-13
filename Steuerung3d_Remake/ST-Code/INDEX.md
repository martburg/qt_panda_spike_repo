# Extracted TwinCAT ST Sources (with index)

- Generated: 2026-01-12 19:34 UTC
- Source archive: `Anton_ST_sources_extracted.zip`

## Contents

| File | Size (bytes) | Notes |
|---|---:|---|
| `plc_st_extract/HauptAnton__MAIN.st` | 29958 | PROGRAM MAIN; mentions lifetick; mentions StatusnachUI |
| `plc_st_extract/HauptAnton__PLC_Fehlerbehandlung.st` | 20038 | PROGRAM PLC_Fehlerbehandlung; contains 'Komm*' (likely comms) |
| `plc_st_extract/HauptAntonSPSPos__MAIN.st` | 30163 | PROGRAM MAIN; mentions lifetick; mentions StatusnachUI |
| `plc_st_extract/HauptAntonSPSPos__PLC_Fehlerbehandlung.st` | 19914 | PROGRAM PLC_Fehlerbehandlung; contains 'Komm*' (likely comms) |
| `plc_st_extract/KommAnton__MAIN.st` | 32179 | PROGRAM MAIN; contains 'Komm*' (likely comms); mentions EOD; mentions lifetick |
| `plc_st_extract/PrüfAnton__PRUEF.st` | 21778 | PROGRAM PRUEF |
| `plc_st_extract/PrüfAntonSPSPos__PRUEF.st` | 22014 | PROGRAM PRUEF |

## How to use

- Open the ST files in an IEC 61131-3 editor (TwinCAT XAE, etc.).
- `Komm*` programs usually contain the field packing/unpacking for UDP semicolon packets.
- Cross-reference the remake protocol contract docs: `docs/PLC_TWINCAT_LEGACY.md`.
