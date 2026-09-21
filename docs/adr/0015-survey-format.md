# ADR 0015 — Property survey: a raster image with two-point georeferencing

- **Status:** Accepted
- **Date:** 2026-09-21
- **Workstream:** A
- **Resolves:** open decision 3 in ADR 0006 — the last of the five

## Context

The Grounds shows outdoor plants on a property survey. The open question was
what a survey may be: a PDF plat as vector geometry, a CAD file, or a raster
image georeferenced by hand.

## Decision

**A survey is a raster image plus at least two pixel↔world calibration points.**
The maintainer confirmed the default ADR 0006 recorded.

- PNG and JPEG are accepted directly.
- **A PDF plat is rasterised on upload**, and the original is kept. What the map
  needs is pixels and two reference points; the vector geometry inside a plat
  buys nothing the calibration does not already give us.
- **CAD is out of scope.** Parsing DWG/DXF is its own project and no part of the
  plan depends on it.
- Satellite imagery is not the route. It loses property boundaries and anything
  under tree canopy — which, in a garden, is where a good deal of the planting
  is.

This is what Workstream H's brief already assumed, so S7 needs no re-plan.

## Consequences

- One Leaflet component covers both map kinds, as ADR 0002 intended: floor plans
  on `CRS.Simple` with a px→mm scale, the survey as a georeferenced overlay. H
  does not build two.
- Pins stay in **layer pixel coordinates**, so recalibrating moves every pin
  correctly and a floor plan needs no fiction about where on Earth it sits.
- Accuracy is bounded by how carefully the two points are placed. H should let
  a user add more than two and say plainly how much error is implied, rather
  than presenting a hand-calibrated overlay as survey-grade.
- Reversible: PDF vector extraction could be added later as a better calibration
  *source* without changing the stored model, because the model is already
  pixels plus control points.
