# Native rendering stack

`quadros` packages the Python CLI and renderer, but production rendering still depends on the native visualization stack available on the target machine.

`quadros` is not tied to any specific cluster or scheduler. It can run locally, over SSH on a workstation, inside a container, on any Slurm cluster, or from another scheduler once the native rendering stack is available. The checked-in Slurm script is only a generic starter template; cluster-specific accounts, partitions, modules, and containers belong in local copies. Render outputs default to the case-local `quadros/` directory.

Verify before rendering:

```bash
quadros doctor
```

Expected runtime components:

- PyVista and VTK with offscreen rendering support.
- `pymech` for Nek5000 snapshot reads.
- `ffmpeg` for movie encoding.
- A display/offscreen setup suitable for the cluster node (`PYVISTA_OFF_SCREEN=true` by default).

For NekStab omega-R dense videos, rebuild the case after enabling `ifvox = .true.` in the `.usr` file, then run `quadros render --check` or `quadros render-many --check` with explicit `field_aliases` in the render config.
