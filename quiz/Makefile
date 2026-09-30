PDF = smart-scan-quiz.pdf
SRC = defaults.yaml $(wildcard content/*.md) $(wildcard template/*.tex)

$(PDF): $(SRC)
	pandoc -d defaults.yaml

clean:
	rm -f $(PDF)

.PHONY: clean
