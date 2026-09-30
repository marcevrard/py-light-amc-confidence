# Copyright (c) 2026 Marc Evrard, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
# py-light-amc-confidence: https://github.com/marcevrard/py-light-amc-confidence
# Build a quiz PDF:   make                      (example quiz)
#                     make QUIZ=quizzes/quiz-1  (your own quiz)
# A quiz folder holds meta.tex (title, headers, footer) and questions.md.
QUIZ ?= examples/simple
PANDOC_FLAGS ?=
PDF  := $(QUIZ)/quiz.pdf
SRC  := defaults.yaml $(wildcard content/*.md) $(wildcard template/*.tex) \
        $(QUIZ)/meta.tex $(QUIZ)/questions.md

$(PDF): $(SRC)
	pandoc $(PANDOC_FLAGS) -d defaults.yaml -H $(QUIZ)/meta.tex \
		content/instructions.md content/questions-begin.md $(QUIZ)/questions.md -o $(PDF)

clean:
	rm -f $(PDF)

.PHONY: clean
