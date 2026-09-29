# Reference materials

A standalone, runnable reproduction of the ORIGINAL CLI project
(`main.py` + a real `core/` package + `config.json`), kept here specifically
for regression testing (spec §45) against the FastAPI backend. Nothing here
is imported by the FastAPI app itself.

`core/` is a copy of `../existing_pipeline/` (same real files, same
byte-for-byte content) so this directory works completely standalone --
just needs its own dependencies installed:

```bash
cd reference
python3 -m venv .venv && source .venv/bin/activate
pip install shapely ezdxf matplotlib pandas
python main.py config.json
```

This runs the same worked example used throughout the backend's tests: a
1000x1000 to 1400x1300 synthetic boundary (`coordinates.csv`), with a
control room (`control_room_coordinates.csv`) and inverter room
(`inverter_room_coordinates.csv`), targeting 7 MW AC at a 1.2 DC:AC ratio,
centralized-inverter architecture. Expect console output ending in:

```
Number of Inverters        : 7
...
Total Tables               : 329
...
Total Land Area                : 29.65 ACRES (APPROX.)
```

and a real DXF at `reference/output/solar_layout.dxf` with the same
26-layer structure (BOUNDARY, PV_TABLES, TITLE_BLOCK, GROUP_BOUNDARY,
LIGHTNING_ARRESTER, ...) as the two sample DXF files provided alongside the
original source.

## Using this for regression testing

Run the same boundary/control-room/inverter-room CSVs and equivalent
config through the API instead (`POST /inputs`, upload the CSVs,
`POST /generate`, poll `GET /jobs/{id}`), and diff `table_count`,
`module_count`, `actual_dc_mwp`, `land_area_acres`, and the DXF's layer/
entity structure against this CLI run's output. They should match exactly
-- both paths call the identical, unmodified `run_pipeline()`.

`streamlit_app.py` (the original Streamlit UI) is also kept here for
reference on how the client-facing app assembles its config dict --
useful context for anyone extending the API's Pydantic schemas later, but
it isn't run as part of this backend.
