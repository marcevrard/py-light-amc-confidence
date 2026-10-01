# Copyright (c) 2026 Marc Evrard, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
# py-light-amc-confidence: https://github.com/marcevrard/py-light-amc-confidence
# Build a quiz PDF:   make                      (example quiz)
#                     make QUIZ=quizzes/quiz-1  (your own quiz)
# A quiz folder holds meta.tex (title, headers, footer) and questions.md.
# Shuffled copies, one per student: make copies QUIZ=quizzes/quiz-1 N=30
QUIZ ?= examples/simple
PANDOC_FLAGS ?=
PDF  := $(QUIZ)/quiz.pdf
SRC  := defaults.yaml $(wildcard content/*.md) $(wildcard template/*.tex) \
        $(QUIZ)/meta.tex $(QUIZ)/questions.md

$(PDF): $(SRC)
	pandoc $(PANDOC_FLAGS) -d defaults.yaml -H $(QUIZ)/meta.tex \
		content/instructions.md content/questions-begin.md $(QUIZ)/questions.md -o $(PDF)

copies:
	@test -n "$(N)" || { echo "usage: make copies QUIZ=folder N=number-of-copies"; exit 1; }
	python3 build_copies.py $(QUIZ) $(N) --pandoc-flags "$(PANDOC_FLAGS)"

clean:
	rm -f $(PDF)

.PHONY: clean copies
