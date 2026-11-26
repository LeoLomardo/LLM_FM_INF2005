MAIN = main

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex secoes/*.tex referencias.bib
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
	bibtex $(MAIN)
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc *.fls *.fdb_latexmk *.synctex.gz secoes/*.aux

.PHONY: all clean
