import argparse
import sys
from pathlib import Path


def _surface_builder(surface_name):
    from ase.build import bcc100, bcc110, bcc111, fcc100, fcc110, fcc111, hcp0001

    builders = {
        "fcc100": fcc100,
        "fcc110": fcc110,
        "fcc111": fcc111,
        "bcc100": bcc100,
        "bcc110": bcc110,
        "bcc111": bcc111,
        "hcp0001": hcp0001,
    }
    if surface_name not in builders:
        raise ValueError(f"Unsupported surface '{surface_name}'. Choose one of: {', '.join(builders)}")
    return builders[surface_name]


def _orient_adsorbate(atoms, orientation):
    if orientation == "upright":
        return atoms
    if orientation == "tilted_x":
        atoms.rotate(45.0, "y", center=atoms.positions[0], rotate_cell=False)
        return atoms
    if orientation == "tilted_y":
        atoms.rotate(45.0, "x", center=atoms.positions[0], rotate_cell=False)
        return atoms
    if orientation == "reverse":
        atoms.rotate(180.0, "x", center=atoms.positions[0], rotate_cell=False)
        return atoms
    raise ValueError("orientation must be one of: upright, tilted_x, tilted_y, reverse")


def main():
    parser = argparse.ArgumentParser(description="Build a slab + adsorbate POSCAR with ASE.")
    parser.add_argument("--element", required=True, help="Slab element, e.g. Pt")
    parser.add_argument("--surface", required=True, help="Surface builder: fcc111, fcc100, bcc110, hcp0001")
    parser.add_argument("--size", nargs=3, type=int, default=[2, 2, 4], metavar=("A", "B", "LAYERS"))
    parser.add_argument("--vacuum", type=float, default=15.0, help="Vacuum thickness in Angstrom")
    parser.add_argument("--adsorbate", required=True, help="ASE molecule name, e.g. CO")
    parser.add_argument("--site", required=True, help="Adsorption site, e.g. ontop, bridge, fcc, hcp")
    parser.add_argument("--height", type=float, default=1.85, help="Adsorption height in Angstrom")
    parser.add_argument("--orientation", default="upright", help="upright, tilted_x, tilted_y, or reverse")
    parser.add_argument("--mol-index", type=int, default=0, help="Adsorbate atom index placed at the site")
    parser.add_argument("--output", default="POSCAR_adsorbed", help="Output POSCAR path")
    parser.add_argument("--sort", action="store_true", help="Sort atoms in VASP output")
    args = parser.parse_args()

    try:
        from ase.build import add_adsorbate, molecule
        from ase.io import write
    except ImportError:
        print("ERROR: ase is not installed. Install requirements.txt first.", file=sys.stderr)
        return 1

    try:
        slab = _surface_builder(args.surface)(args.element, size=tuple(args.size), vacuum=args.vacuum)
        ads = molecule(args.adsorbate)
        ads = _orient_adsorbate(ads, args.orientation)
        add_adsorbate(slab, ads, height=args.height, position=args.site, mol_index=args.mol_index)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write(str(output), slab, format="vasp", direct=True, vasp5=True, sort=args.sort)

    print(f"SUCCESS: wrote {output}")
    print(f"FORMULA: {slab.get_chemical_formula()}")
    print(f"ATOMS: {len(slab)}")
    print(f"SITE: {args.site}")
    print(f"ORIENTATION: {args.orientation}")
    print(f"HEIGHT_A: {args.height:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
