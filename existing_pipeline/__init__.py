"""
existing_pipeline
==================

This package holds the ORIGINAL solar-layout engineering pipeline,
unmodified, exactly as it was handed to the API team. Nothing in here is
allowed to be rewritten by the FastAPI layer -- see app/pipeline/adapter.py
for the only sanctioned entry point into this code.

Provenance note
----------------
The original project's internal module comments (e.g. "# End of
core/capacity.py") show the pipeline's real package name is `core`, and its
modules import each other absolutely as `core.capacity`, `core.geometry`,
`core.calculation_engine`, etc. (confirmed directly in the real
core/pipeline.py's own imports). Renaming the directory to
`existing_pipeline` (to match the requested backend layout) would break
those internal imports.

Rather than edit the pipeline's own import statements (forbidden by the
brief), app/pipeline/adapter.py registers this package -- and every one of
its submodules -- into sys.modules under their original `core.*` names
before importing from it, so `from core.pipeline import run_pipeline` and
`from core.geometry import GeometryEngine` keep working completely
unmodified inside these files, while the directory on disk still lives at
backend/existing_pipeline/ as requested.

All files here now hold REAL, unmodified logic, copied verbatim from the
uploaded source (byte-for-byte identical -- verified with `diff`):
    capacity.py             DC/AC sizing dataclasses + formulas
    csv_loader.py           survey coordinate CSV loading
    grouping.py             SCB/inverter table-grouping (2x6 detection etc.)
    offset.py               boundary setback / exclusion-difference engine
    dwg_export.py           ODA File Converter DXF->DWG bridge
    geometry.py             GeometryEngine (boundary polygon construction)
    packing.py              PackingEngine (row generation, table placement,
                             gap-filling)
    calculation_engine.py   calculatePlant() / calculate_* formula family,
                             generateTableGrouping(), actual_layout_report()
    dxf_writer.py           DXFWriter (layers, blocks, title block drawing)
    pipeline.py             run_pipeline() -- the full orchestration,
                             including the right-of-boundary AutoCAD-style
                             title block (coordinate tables, key plan,
                             notes, plant details, legend, section details)

`exceptions.py` (PipelineModuleMissingError) is no longer raised by
anything here now that every file is real, but is left in place harmlessly
in case a future replacement file is dropped in before its real
implementation is ready.
"""

from .exceptions import PipelineModuleMissingError  # noqa: F401

