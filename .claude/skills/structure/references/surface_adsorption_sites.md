# Surface Adsorption Sites

## Common sites on fcc(111)

- `ontop`: adsorbate anchor atom above one surface atom.
- `bridge`: anchor atom between two neighboring surface atoms.
- `fcc`: threefold hollow site above an fcc continuation site.
- `hcp`: threefold hollow site above an hcp continuation site.

## CO/Pt(111) p(2x2)

For one CO on p(2x2) Pt(111), coverage is 1/4 ML because the top surface layer has four Pt atoms per lateral supercell.

Recommended initial structures:

- fcc upright
- fcc tilted_x
- fcc tilted_y
- ontop upright
- ontop tilted_x
- ontop tilted_y

Use C-down CO as the default adsorption anchor. For DREAMS-aligned CO/Pt(111), "orientation" means the molecular-axis geometry (`upright`, `tilted_x`, `tilted_y`) and must not be interpreted as C-down vs O-down. O-down/reverse can be generated only when the user explicitly asks for end-group screening beyond the standard benchmark.
