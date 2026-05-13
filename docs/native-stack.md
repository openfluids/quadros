# Native rendering stack

`neksnap` packages the Python CLI and renderer, but production rendering still depends on the native visualization stack available on the target machine.

The checked-in Slurm script is currently written for a Jean Zay job. Treat it as a site-specific template, not as a project limitation: `neksnap` can run locally, on other Slurm clusters, or from any scheduler once the native rendering stack is available.

Verify before rendering:

```bash
neksnap doctor
```

Expected runtime components:

- PyVista and VTK with offscreen rendering support.
- `pymech` for Nek5000 snapshot reads.
- `ffmpeg` for movie encoding.
- A display/offscreen setup suitable for the cluster node (`PYVISTA_OFF_SCREEN=true` by default).

For NekStab omega-R dense videos, rebuild the case after enabling `ifvox = .true.` in the `.usr` file, then run `neksnap render --check` or `neksnap render-many --check` with explicit `field_aliases` in the render config.
