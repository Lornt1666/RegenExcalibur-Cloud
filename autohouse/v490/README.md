# AutoHouse Ω v490 — Permit-Ready Construction Documentation Foundry

**Primary directive:** natural-language building brief → canonical coordinated BIM/model → engineering analysis → construction documents covering every trade → professional-authentication-ready permit package.

> Construction Documents (CDs) — a fully coordinated, architected, engineered, permit-ready drawing set covering every trade.

## Scope reset

v490 makes construction documentation the primary AutoHouse product. Portfolio, warranty, capital-planning, and lifecycle intelligence remain optional downstream modules and must never block the core CD compiler.

## Truth / authority boundary

AutoHouse may generate and analyse professional-work-product content, but it must not impersonate a licensed professional or autonomously apply a professional stamp, signature, APEGA digital signature, permit-holder validation, municipal approval, or AHJ acceptance.

The strongest software-only state is:

`PROFESSIONAL_AUTHENTICATION_READY`

A project may reach:

`PERMIT_SUBMISSION_READY`

only after every required external professional authentication/validation, delegated-design/manufacturer record, project-specific survey/geotechnical input, applicable professional schedule, and jurisdiction/AHJ submission prerequisite has been bound and verified.

## Free-first implementation stack

The software pipeline is deliberately FOSS / zero-license-cost wherever technically possible:

- **IFC/BIM + drawings + schedules + sheets + clash coordination:** IfcOpenShell + Bonsai/Blender.
- **Geometry automation:** IfcOpenShell Python.
- **Structural analysis:** OpenSeesPy / Code_Aster / CalculiX, with custom deterministic calculation kernels and verification examples.
- **Meshing:** Gmsh.
- **Energy/building simulation:** EnergyPlus.
- **Water/network analysis where applicable:** EPANET.
- **Storm/drainage analysis where applicable:** EPA SWMM.
- **CFD / advanced airflow where justified:** OpenFOAM.
- **2D vector output:** SVG/DXF/PDF generated from the canonical model; LibreCAD/FreeCAD may be used for manual review/cleanup.
- **Site/geospatial:** QGIS/GDAL where applicable.
- **Specifications/calculation reports:** Markdown/HTML/LaTeX/PDF generation.
- **Rules/tests:** Python + JSON Schema + pytest.

Some referenced engineering standards are copyrighted/licensed even when the software is free. AutoHouse must never invent unavailable standard text. It records the standard/edition/clause basis or an explicit external-review hold.

## Current Alberta baseline

For an Alberta target, the code registry begins with the current official Alberta code set and is project/jurisdiction scoped. The engine must bind the actual applicable code path, municipality/AHJ, site, building classification, Part 9/Part 3 path, and professional-schedule requirements before claiming permit-submission readiness.

## Discipline mesh

### G — General / code / authority
- cover and project data
- complete sheet index
- drawing legend / abbreviations
- code analysis matrix
- occupancy / building classification
- spatial-separation / exposing-building-face matrix
- fire/life-safety summary
- energy-compliance path
- design criteria
- deferred/submittal register
- professional-responsibility matrix
- unresolved/hold register

### C — Civil / site
- legal/site information and survey binding
- site plan
- setbacks / easements / grades
- finished-floor elevations
- drainage and lot grading
- utility servicing
- storm / sanitary / water service coordination
- retaining/site structures when applicable

### A — Architecture
- dimensioned foundation coordination plan
- every floor plan
- reflected ceiling plans where required
- roof plan
- exterior elevations
- building sections
- wall sections
- stair/guard/handrail details
- door/window schedules
- room/finish schedules
- envelope assemblies
- accessibility layouts
- life-safety/egress overlays
- construction details

### S — Structural
- design criteria and loads
- foundation design
- load path
- beams/columns/posts
- floor/roof framing
- shear/braced-wall/lateral system
- diaphragms
- lintels/headers
- tall walls
- point-load transfer
- bearing
- connections/anchors/hold-downs
- openings/penetrations coordination
- structural details and schedules
- calculation package + model receipts

### GTE — Geotechnical dependency
- soil-bearing basis
- frost/foundation assumptions
- groundwater
- fill/compaction
- slope/retaining dependencies
- explicit geotechnical hold when site evidence is absent

### EN — Envelope / energy / building science
- thermal assemblies
- continuous insulation / thermal bridges
- air barrier
- vapour control
- water-management planes
- roofing/wall interfaces
- window/door transitions
- condensation/hygrothermal risk checks
- energy-code compliance calculations

### M — Mechanical / HVAC
- design temperatures and loads
- heat-loss / heat-gain basis
- equipment schedule
- ventilation / HRV/ERV
- outdoor-air/exhaust
- duct sizing / routing
- combustion-air / venting dependencies where applicable
- hydronic systems where applicable
- controls
- mechanical room clearances
- commissioning requirements

### P — Plumbing
- fixture schedule
- water distribution
- developed-length / sizing basis
- drainage/waste/vent
- cleanouts
- service entries
- hot-water system
- backflow / cross-connection dependencies
- sump / sewage ejector / private sewage where applicable

### GAS — Gas / fuel
- connected load
- pipe-sizing basis
- regulators / meters
- appliance connections
- venting / combustion coordination
- code and manufacturer dependencies

### E — Electrical
- service characteristics
- calculated electrical load
- panel schedules
- single-line / riser where required
- branch circuits
- receptacles / lighting / switching
- GFCI/AFCI requirements
- smoke/CO detection
- equipment disconnects
- exterior circuits
- grounding/bonding notes
- low-voltage/data coordination where required

### FP/LS — Fire protection / life safety
- fire separations
- rated assemblies
- closures
- firestopping / penetration matrix
- alarm/detection requirements
- suppression where applicable
- emergency/egress lighting where applicable
- exit/egress geometry

### DD — Delegated / manufactured engineering
- roof/floor trusses
- engineered wood
- proprietary lintels/connectors
- precast/specialty systems
- manufactured stairs/guards where engineered
- shop drawings / delegated-design professional responsibilities

### SP — Specifications / schedules / procurement
- material and assembly specifications
- drawing schedules
- product data requirements
- submittal register
- QA/QC testing requirements
- commissioning/closeout requirements

## Canonical production sequence

1. `BRIEF_INGESTED`
2. `SITE_AND_AUTHORITY_BOUND`
3. `PROGRAM_RESOLVED`
4. `COORDINATED_MODEL_READY`
5. `ENGINEERING_ANALYSIS_COMPLETE`
6. `TRADE_COORDINATION_COMPLETE`
7. `CD_SET_COMPLETE`
8. `INTERNAL_QAQC_PASS`
9. `PROFESSIONAL_AUTHENTICATION_READY`
10. `EXTERNAL_AUTHENTICATION_BOUND`
11. `PERMIT_SUBMISSION_READY`
12. `AHJ_RESPONSE_TRACKING`

## No-silent-omission law

Every required datum must be one of:

`RESOLVED`, `DEFAULTED`, `PROVISIONAL`, `UNRESOLVED`, `DEFERRED`, `NOT_APPLICABLE`, `CONTRADICTORY`, `PROFESSIONAL_HOLD`, `AUTHORITY_HOLD`, `MANUFACTURER_HOLD`, `TESTING_HOLD`.

## Geometry / coordination laws

- no floating doors or windows
- no unhosted openings
- no inaccessible rooms
- no disconnected stairs
- no unsupported structural members
- no orphan point loads
- no MEP element without host/system relationship
- no penetrations without structure/envelope/fire coordination
- no schedule/model disagreement
- no drawing/model disagreement
- no dimension without geometric basis
- no engineering claim without calculation/evidence basis

## Professional-authentication gate

The compiler produces an authentication dossier containing:

- canonical model digest
- drawing-set digest
- calculation-set digest
- applicable-code register
- assumption/unknown register
- discipline calculation receipts
- clash/coordination receipts
- professional-responsibility matrix
- delegated-design register
- external evidence register
- sheet-by-sheet authentication requirements

AutoHouse reserves a visible authentication zone in the final drawing set but does not create or apply a professional credential/stamp/signature. The licensed professional performs the actual authentication using the legally required method.

## Definition of done

The core v490 product is done when a real project can be entered from an English brief and the system can produce a coordinated IFC + drawing/spec/calculation package covering the applicable disciplines, with no silent omissions, deterministic engineering receipts, and an explicit professional/AHJ handoff that can reach genuine permit-submission readiness once the legally required external authorities authenticate/accept their respective work.
