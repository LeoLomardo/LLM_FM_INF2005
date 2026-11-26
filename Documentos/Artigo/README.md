# Artigo — reprodução/replicação SPLC'23

Classe `acmart` (`sigconf,nonacm`), a mesma do artigo original. Cada seção fica em `secoes/`,
para que cada pessoa edite o seu arquivo sem conflito de merge.

## Compilar
- **Overleaf:** subir a pasta e compilar `main.tex` (pdfLaTeX). As figuras de `3.results/figures/`
  precisam ser copiadas para `figuras/`.
- **Local:** `make` (pdflatex + bibtex). No Arch, se faltar `acmart`/fontes, sem sudo:
  `tlmgr init-usertree && tlmgr --usermode --repository https://mirrors.ctan.org/systems/texlive/tlnet install acmart libertine newtx inconsolata ncctools xkeyval fontaxes mweights`

## Convenções
- Marcadores: `\todo{...}`, `\felipe{...}`, `\gabriela{...}`, `\leo{...}` — remover antes da entrega.
- Figuras vêm do notebook (`SPLC23_atualizado.ipynb`) em `3.results/figures/`; não editar à mão.
- Referências marcadas `% TODO conferir metadados` no `.bib` precisam ser checadas.
